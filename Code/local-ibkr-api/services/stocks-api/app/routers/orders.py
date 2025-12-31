"""Order management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import structlog

from app.schemas.trading import OrderRequest, OrderResponse, OrderListResponse
from app.models.trading import Order
from app.utils.database import get_db
from app.utils.risk import RiskManager
# Order type mapping
ORDER_TYPE_MAP = {"MKT": "MARKET", "LMT": "LIMIT", "STP": "STOP", "STP LMT": "STOP_LIMIT", "TRAIL": "TRAILING_STOP"}

def map_order_type(order_type: str) -> str:
    return ORDER_TYPE_MAP.get(order_type, order_type)
from app.utils.ib_dependencies import get_ib_client
from app.config import get_settings

settings = get_settings()
from app.ib_protocol import IBKRClientProtocol
from ib_insync import Stock, MarketOrder, LimitOrder, StopOrder

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/", response_model=OrderResponse)
async def place_order(
    order_request: OrderRequest,
    db: Session = Depends(get_db),
    ib_client: IBKRClientProtocol = Depends(get_ib_client)
):
    """
    Place a new order.
    
    - Validates the order request
    - Performs pre-trade risk checks
    - Submits order to IBKR
    - Stores order in database
    """
    logger.info(
        "order_placement_requested",
        symbol=order_request.symbol,
        action=order_request.action,
        quantity=order_request.quantity,
        order_type=order_request.order_type
    )
    
    # Risk checks
    risk_manager = RiskManager(db)
    risk_result = risk_manager.check_order(order_request)
    
    if not risk_result.passed:
        logger.warning(
            "order_rejected_risk_check",
            symbol=order_request.symbol,
            reason=risk_result.reason
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Risk check failed",
                "reason": risk_result.reason,
                "checks": risk_result.checks_performed
            }
        )
    
    # Create contract
    contract = Stock(
        symbol=order_request.symbol,
        exchange=order_request.exchange,
        currency=order_request.currency
    )
    
    # Create order based on type
    if order_request.order_type == "MKT":
        ib_order = MarketOrder(
            action=order_request.action,
            totalQuantity=order_request.quantity
        )
    elif order_request.order_type == "LMT":
        if not order_request.limit_price:
            raise HTTPException(400, "Limit price required for limit orders")
        ib_order = LimitOrder(
            action=order_request.action,
            totalQuantity=order_request.quantity,
            lmtPrice=order_request.limit_price
        )
    elif order_request.order_type == "STP":
        if not order_request.stop_price:
            raise HTTPException(400, "Stop price required for stop orders")
        ib_order = StopOrder(
            action=order_request.action,
            totalQuantity=order_request.quantity,
            stopPrice=order_request.stop_price
        )
    else:
        raise HTTPException(400, f"Unsupported order type: {order_request.order_type}")
    
    # Place order with IBKR
    try:
        trade = await ib_client.place_order(contract, ib_order)
        
        # Store in database
        db_order = Order(
            order_id=trade.order.orderId if hasattr(trade, 'order') else 0,
            client_id=1,
            symbol=order_request.symbol,
            sec_type=order_request.sec_type,
            exchange=order_request.exchange,
            currency=order_request.currency,
            action=order_request.action,
            order_type=map_order_type(order_request.order_type),
            total_quantity=order_request.quantity,
            limit_price=order_request.limit_price,
            stop_price=order_request.stop_price,
            time_in_force=order_request.time_in_force,
            status="SUBMITTED",
	    filled_quantity=0.0,
	    remaining_quantity=order_request.quantity,
            risk_check_passed=True
        )
        
        db.add(db_order)
        db.commit()
        db.refresh(db_order)
        
        logger.info(
            "order_placed_successfully",
            order_id=db_order.order_id,
            symbol=order_request.symbol
        )
        
        return OrderResponse.from_orm(db_order)
        
    except Exception as e:
        logger.error("order_placement_failed", error=str(e))
        raise HTTPException(500, f"Failed to place order: {str(e)}")


@router.get("/", response_model=OrderListResponse)
async def list_orders(
    symbol: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    days: int = Query(7, ge=1, le=90),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List orders with optional filtering.
    
    - Filter by symbol, status
    - Pagination support
    - Returns last N days of orders
    """
    query = db.query(Order)
    
    # Apply filters
    if symbol:
        query = query.filter(Order.symbol == symbol.upper())
    if status:
        query = query.filter(Order.status == status)
    
    # Date filter
    since = datetime.utcnow() - timedelta(days=days)
    query = query.filter(Order.created_at >= since)
    
    # Count total
    total = query.count()
    
    # Pagination
    offset = (page - 1) * page_size
    orders = query.order_by(Order.created_at.desc()).offset(offset).limit(page_size).all()
    
    return OrderListResponse(
        orders=[OrderResponse.from_orm(o) for o in orders],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    db: Session = Depends(get_db)
):
    """Get order details by ID."""
    order = db.query(Order).filter(Order.order_id == order_id).first()
    
    if not order:
        raise HTTPException(404, f"Order {order_id} not found")
    
    return OrderResponse.from_orm(order)


@router.delete("/{order_id}")
async def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    ib_client: IBKRClientProtocol = Depends(get_ib_client)
):
    """
    Cancel an order.
    
    - Cancels with IBKR
    - Updates database status
    """
    order = db.query(Order).filter(Order.order_id == order_id).first()
    
    if not order:
        raise HTTPException(404, f"Order {order_id} not found")
    
    if order.status in ["Filled", "Cancelled"]:
        raise HTTPException(400, f"Cannot cancel order with status: {order.status}")
    
    try:
        # Cancel with IBKR
        success = await ib_client.cancel_order(order)
        
        if success:
            order.status = "Cancelled"
            db.commit()
            
            logger.info("order_cancelled", order_id=order_id)
            
            return {"status": "success", "message": f"Order {order_id} cancelled"}
        else:
            raise HTTPException(500, "Failed to cancel order with IBKR")
            
    except Exception as e:
        logger.error("order_cancellation_failed", order_id=order_id, error=str(e))
        raise HTTPException(500, f"Failed to cancel order: {str(e)}")
