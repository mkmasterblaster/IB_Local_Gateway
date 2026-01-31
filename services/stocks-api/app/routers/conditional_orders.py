"""Conditional order endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import asyncio
import structlog
import time
from app.config import MARKET_DATA_TYPE, CONDITIONAL_CHECK_PRICE_WAIT

from app.schemas.trading import ConditionalOrderRequest, ConditionalOrderResponse
from app.models.trading import ConditionalOrder
from app.utils.database import get_db
from app.ib_client import IBKRClient
from app.utils.ib_dependencies import get_ib_client

router = APIRouter(prefix="/conditional", tags=["conditional-orders"])
logger = structlog.get_logger()


@router.post("/", response_model=ConditionalOrderResponse)
async def create_conditional_order(
    request: ConditionalOrderRequest,
    db: Session = Depends(get_db)
):
    """
    Create a conditional order.
    
    Example - Buy on breakout:
        If AAPL crosses above $300, buy 100 shares at market
        
    Example - Sell on breakdown:
        If TSLA drops below $350, sell 50 shares at $345 limit
    """
    try:
        # Create conditional order
        cond_order = ConditionalOrder(
            condition_type=request.condition_type,
            condition_symbol=request.condition_symbol,
            condition_price=request.condition_price,
            order_symbol=request.order_symbol,
            order_action=request.order_action,
            order_type=request.order_type,
            order_quantity=request.order_quantity,
            order_limit_price=request.order_limit_price,
            time_in_force=request.time_in_force,
            exchange=request.exchange,
            currency=request.currency,
            status="ACTIVE"
        )
        
        db.add(cond_order)
        db.commit()
        db.refresh(cond_order)
        
        logger.info(
            "conditional_order_created",
            condition_id=cond_order.id,
            condition_type=request.condition_type,
            symbol=request.condition_symbol
        )
        
        return ConditionalOrderResponse(
            condition_id=cond_order.id,
            condition_type=request.condition_type,
            condition_symbol=request.condition_symbol,
            condition_price=str(request.condition_price),
            order_symbol=request.order_symbol,
            order_action=request.order_action,
            status="active",
            message=f"Conditional order created - will execute when {request.condition_symbol} {request.condition_type.replace('_', ' ').lower()} ${request.condition_price}"
        )
        
    except Exception as e:
        logger.error("create_conditional_order_error", error=str(e))
        raise HTTPException(500, f"Failed to create conditional order: {str(e)}")


@router.get("/")
async def list_conditional_orders(
    status: str = "ACTIVE",
    db: Session = Depends(get_db)
):
    """List conditional orders by status."""
    orders = db.query(ConditionalOrder).filter(
        ConditionalOrder.status == status
    ).all()
    
    return {"orders": orders, "count": len(orders)}


@router.delete("/{condition_id}")
async def cancel_conditional_order(
    condition_id: int,
    db: Session = Depends(get_db)
):
    """Cancel a conditional order."""
    cond_order = db.query(ConditionalOrder).filter(
        ConditionalOrder.id == condition_id
    ).first()
    
    if not cond_order:
        raise HTTPException(404, f"Conditional order {condition_id} not found")
    
    if cond_order.status != "ACTIVE":
        raise HTTPException(400, f"Cannot cancel order with status: {cond_order.status}")
    
    cond_order.status = "CANCELLED"
    db.commit()
    
    logger.info("conditional_order_cancelled", condition_id=condition_id)
    
    return {"condition_id": condition_id, "status": "cancelled"}


@router.post("/check")
async def check_conditional_orders_manual(
    ib_client: IBKRClient = Depends(get_ib_client),
    db: Session = Depends(get_db)
):
    """
    Manually check all active conditional orders and execute if triggered.
    """
    from ib_insync import Stock
    from app.models.trading import Order, OrderStatus, OrderType
    from decimal import Decimal
    from datetime import datetime
    
    checked = []
    triggered = []
    
    try:
        # Set market data type to DELAYED (3) - change to 1 for real-time when subscribed
        # 1=Live, 2=Frozen, 3=Delayed, 4=Delayed-Frozen
        ib_client.ib.reqMarketDataType(MARKET_DATA_TYPE)
        
        # Get all active conditional orders
        logger.info("checking_for_active_orders")
        active_orders = db.query(ConditionalOrder).filter(
            ConditionalOrder.status == "ACTIVE"
        ).all()
        logger.info("found_active_orders", count=len(active_orders))
        
        for cond_order in active_orders:
            # Use last checked price from database
            current_price = cond_order.last_checked_price
            
            if not current_price:
                continue
            
            # Update last checked
            cond_order.last_checked_price = current_price
            cond_order.last_checked_at = datetime.utcnow()
            db.commit()
            
            checked.append({
                "id": cond_order.id,
                "symbol": cond_order.condition_symbol,
                "current_price": str(current_price),
                "trigger_price": str(cond_order.condition_price)
            })
            
            # Check condition
            condition_met = False
            if cond_order.condition_type == "PRICE_ABOVE":
                condition_met = current_price >= cond_order.condition_price
            elif cond_order.condition_type == "PRICE_BELOW":
                condition_met = current_price <= cond_order.condition_price
            
            if condition_met:
                # Execute order
                from ib_insync import Order as IBOrder
                
                contract = Stock(
                    symbol=cond_order.order_symbol,
                    exchange=cond_order.exchange,
                    currency=cond_order.currency
                )
                
                ib_order = IBOrder()
                ib_order.orderId = ib_client.ib.client.getReqId()
                ib_order.action = cond_order.order_action
                ib_order.totalQuantity = cond_order.order_quantity
                ib_order.tif = cond_order.time_in_force
                
                if cond_order.order_type == "MKT":
                    ib_order.orderType = "MKT"
                else:
                    ib_order.orderType = "LMT"
                    ib_order.lmtPrice = float(cond_order.order_limit_price)
                
                trade = ib_client.ib.placeOrder(contract, ib_order)
                
                # Store executed order
                db_order = Order(
                    order_id=ib_order.orderId,
                    symbol=cond_order.order_symbol,
                    action=cond_order.order_action,
                    order_type=OrderType.MARKET if cond_order.order_type == "MKT" else OrderType.LIMIT,
                    total_quantity=cond_order.order_quantity,
                    limit_price=cond_order.order_limit_price if cond_order.order_type == "LMT" else None,
                    status=OrderStatus.SUBMITTED,
                    time_in_force=cond_order.time_in_force,
                    client_id=999,
                    sec_type="STK",
                    exchange=cond_order.exchange,
                    currency=cond_order.currency,
                    filled_quantity=0,
                    remaining_quantity=cond_order.order_quantity,
                    risk_check_passed=True
                )
                db.add(db_order)
                
                # Update conditional order
                cond_order.status = "TRIGGERED"
                cond_order.triggered_at = datetime.utcnow()
                cond_order.executed_order_id = ib_order.orderId
                db.commit()
                
                triggered.append({
                    "condition_id": cond_order.id,
                    "order_id": ib_order.orderId,
                    "symbol": cond_order.order_symbol,
                    "action": cond_order.order_action
                })
        
        return {
            "checked": checked,
            "triggered": triggered,
            "message": f"Checked {len(checked)} conditional orders, {len(triggered)} triggered"
        }
        
    except Exception as e:
        logger.error("check_conditional_orders_error", error=str(e))
        raise HTTPException(500, f"Failed to check conditional orders: {str(e)}")
