"""Order management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import structlog

from app.schemas.trading import OrderRequest, OrderResponse, OrderListResponse, BracketOrderRequest, BracketOrderResponse, TrailingStopRequest, TrailingStopResponse, OrderModificationRequest, OrderModificationResponse, OCOOrderRequest, OCOOrderResponse
from app.models.trading import Order, OrderStatus, OrderType
from app.utils.database import get_db
from app.utils.risk import RiskManager
# Order type mapping
ORDER_TYPE_MAP = {"MKT": "MARKET", "LMT": "LIMIT", "STP": "STOP", "STP LMT": "STOP_LIMIT", "TRAIL": "TRAILING_STOP"}

def map_order_type(order_type: str) -> str:
    return ORDER_TYPE_MAP.get(order_type, order_type)
from app.utils.ib_dependencies import get_ib_client
from app.ib_client import IBKRClient
from app.config import get_settings

settings = get_settings()
from app.ib_protocol import IBKRClientProtocol
from app.config import settings
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
        order_id_value = trade.order.orderId if hasattr(trade, 'order') else 0
        
        # Check if order already exists (from previous attempt)
        existing = db.query(Order).filter(Order.order_id == order_id_value).first()
        if existing:
            logger.info("order_already_exists_returning", order_id=order_id_value)
            return OrderResponse.from_orm(existing)
        
        db_order = Order(
            order_id=order_id_value,
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
        success = await ib_client.cancel_order(order.order_id)
        
        if success:
            order.status = OrderStatus.CANCELLED
            db.commit()
            
            logger.info("order_cancelled", order_id=order_id)
            
            return {"status": "success", "message": f"Order {order_id} cancelled"}
        else:
            raise HTTPException(500, "Failed to cancel order with IBKR")
            
    except Exception as e:
        logger.error("order_cancellation_failed", order_id=order_id, error=str(e))
        raise HTTPException(500, f"Failed to cancel order: {str(e)}")


@router.post("/bracket", response_model=BracketOrderResponse)
async def place_bracket_order(
    request: BracketOrderRequest,
    ib_client: IBKRClient = Depends(get_ib_client),
    db: Session = Depends(get_db)
):
    """
    Place a bracket order (entry + profit target + stop loss).
    
    Example:
        Buy 100 AAPL at market, take profit at $280, stop loss at $260
    """
    try:
        from ib_insync import Stock
        
        # Create contract
        contract = Stock(
            symbol=request.symbol,
            exchange=request.exchange,
            currency=request.currency
        )

        # Place bracket order
        parent_trade, profit_trade, stop_trade = await ib_client.place_bracket_order(
            contract=contract,
            action=request.action,
            quantity=request.quantity,
            entry_type=request.entry_type,
            entry_price=float(request.entry_price) if request.entry_price else None,
            profit_target=float(request.profit_target),
            stop_loss=float(request.stop_loss)
        )

        # Store all three orders in database
        from app.models.trading import Order, OrderStatus, OrderType
        
        # Parent order
        db_parent = Order(
            order_id=parent_trade.order.orderId,
            symbol=request.symbol,
            action=request.action,
            order_type="BRACKET_PARENT",
            total_quantity=request.quantity,
            limit_price=request.entry_price if request.entry_type == "LMT" else None,
            status=OrderStatus.SUBMITTED,
            time_in_force=request.time_in_force,
            client_id=settings.IB_CLIENT_ID,
            sec_type="STK",
            exchange=request.exchange,
            currency=request.currency,
            filled_quantity=0,
            remaining_quantity=request.quantity,
            risk_check_passed=True
        )
        db.add(db_parent)
        
        # Profit order
        db_profit = Order(
            order_id=profit_trade.order.orderId,
            symbol=request.symbol,
            action="SELL" if request.action == "BUY" else "BUY",
            order_type="BRACKET_PROFIT",
            total_quantity=request.quantity,
            limit_price=request.profit_target,
            status=OrderStatus.SUBMITTED,
            time_in_force=request.time_in_force,
            client_id=settings.IB_CLIENT_ID,
            sec_type="STK",
            exchange=request.exchange,
            currency=request.currency,
            filled_quantity=0,
            remaining_quantity=request.quantity,
            risk_check_passed=True
        )
        db.add(db_profit)
        
        # Stop order
        db_stop = Order(
            order_id=stop_trade.order.orderId,
            symbol=request.symbol,
            action="SELL" if request.action == "BUY" else "BUY",
            order_type="BRACKET_STOP",
            total_quantity=request.quantity,
            stop_price=request.stop_loss,
            status=OrderStatus.SUBMITTED,
            time_in_force=request.time_in_force,
            client_id=settings.IB_CLIENT_ID,
            sec_type="STK",
            exchange=request.exchange,
            currency=request.currency,
            filled_quantity=0,
            remaining_quantity=request.quantity,
            risk_check_passed=True
        )
        db.add(db_stop)
        
        db.commit()

        logger.info(
            "bracket_order_created",
            symbol=request.symbol,
            parent_id=parent_trade.order.orderId,
            profit_id=profit_trade.order.orderId,
            stop_id=stop_trade.order.orderId
        )

        return BracketOrderResponse(
            parent_order_id=parent_trade.order.orderId,
            profit_order_id=profit_trade.order.orderId,
            stop_order_id=stop_trade.order.orderId,
            symbol=request.symbol,
            status="submitted",
            message=f"Bracket order placed for {request.symbol}"
        )

    except Exception as e:
        logger.error("bracket_order_endpoint_error", error=str(e))
        raise HTTPException(500, f"Failed to place bracket order: {str(e)}")


@router.post("/trailing-stop", response_model=TrailingStopResponse)
async def place_trailing_stop(
    request: TrailingStopRequest,
    ib_client: IBKRClient = Depends(get_ib_client),
    db: Session = Depends(get_db)
):
    """
    Place a trailing stop order.
    
    Example - Dollar amount:
        SELL 100 AAPL with $5 trailing stop
        
    Example - Percentage:
        SELL 50 TSLA with 2.5% trailing stop
    """
    try:
        from ib_insync import Stock
        from app.models.trading import Order, OrderStatus, OrderType
        
        # Create contract
        contract = Stock(
            symbol=request.symbol,
            exchange=request.exchange,
            currency=request.currency
        )

        # Place trailing stop
        trade = await ib_client.place_trailing_stop(
            contract=contract,
            action=request.action,
            quantity=request.quantity,
            trail_stop_price=float(request.trail_stop_price) if request.trail_stop_price else None,
            trail_percent=float(request.trail_percent) if request.trail_percent else None
        )

        # Store in database
        db_order = Order(
            order_id=trade.order.orderId,
            symbol=request.symbol,
            action=request.action,
            order_type=OrderType.TRAILING_STOP,
            total_quantity=request.quantity,
            status=OrderStatus.SUBMITTED,
            time_in_force=request.time_in_force,
            client_id=settings.IB_CLIENT_ID,
            sec_type="STK",
            exchange=request.exchange,
            currency=request.currency,
            filled_quantity=0,
            remaining_quantity=request.quantity,
            risk_check_passed=True
        )
        db.add(db_order)
        db.commit()

        logger.info(
            "trailing_stop_created",
            symbol=request.symbol,
            order_id=trade.order.orderId
        )

        return TrailingStopResponse(
            order_id=trade.order.orderId,
            symbol=request.symbol,
            trail_amount=str(request.trail_stop_price) if request.trail_stop_price else None,
            trail_percent=str(request.trail_percent) if request.trail_percent else None,
            status="submitted",
            message=f"Trailing stop placed for {request.symbol}"
        )

    except Exception as e:
        logger.error("trailing_stop_endpoint_error", error=str(e))
        raise HTTPException(500, f"Failed to place trailing stop: {str(e)}")


@router.patch("/{order_id}", response_model=OrderModificationResponse)
async def modify_order(
    order_id: int,
    request: OrderModificationRequest,
    ib_client: IBKRClient = Depends(get_ib_client),
    db: Session = Depends(get_db)
):
    """
    Modify an existing order.
    
    Example - Change limit price:
        PATCH /orders/12 {"limit_price": 280.00}
        
    Example - Change quantity and price:
        PATCH /orders/15 {"quantity": 20, "limit_price": 265.00}
    """
    try:
        # Verify order exists in database
        db_order = db.query(Order).filter(Order.order_id == order_id).first()
        if not db_order:
            raise HTTPException(404, f"Order {order_id} not found")
        
        # Check at least one modification provided
        modifications = {}
        if request.quantity:
            modifications['quantity'] = request.quantity
        if request.limit_price:
            modifications['limit_price'] = float(request.limit_price)
        if request.stop_price:
            modifications['stop_price'] = float(request.stop_price)
        if request.trail_stop_price:
            modifications['trail_stop_price'] = float(request.trail_stop_price)
        if request.trail_percent:
            modifications['trail_percent'] = float(request.trail_percent)
        
        if not modifications:
            raise HTTPException(400, "No modifications provided")

        # Modify with IB Gateway
        modified_trade = await ib_client.modify_order(
            order_id=order_id,
            quantity=request.quantity,
            limit_price=float(request.limit_price) if request.limit_price else None,
            stop_price=float(request.stop_price) if request.stop_price else None,
            trail_stop_price=float(request.trail_stop_price) if request.trail_stop_price else None,
            trail_percent=float(request.trail_percent) if request.trail_percent else None
        )

        # Update database
        if request.quantity:
            db_order.total_quantity = request.quantity
            db_order.remaining_quantity = request.quantity
        if request.limit_price:
            db_order.limit_price = request.limit_price
        if request.stop_price:
            db_order.stop_price = request.stop_price
        
        db_order.updated_at = datetime.utcnow()
        db.commit()

        logger.info(
            "order_modified_endpoint",
            order_id=order_id,
            modifications=modifications
        )

        return OrderModificationResponse(
            order_id=order_id,
            symbol=db_order.symbol,
            modifications=modifications,
            status="modified",
            message=f"Order {order_id} modified successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("modify_order_endpoint_error", error=str(e), order_id=order_id)
        raise HTTPException(500, f"Failed to modify order: {str(e)}")


@router.post("/oco", response_model=OCOOrderResponse)
async def place_oco_order(
    request: OCOOrderRequest,
    ib_client: IBKRClient = Depends(get_ib_client),
    db: Session = Depends(get_db)
):
    """
    Place OCO (One-Cancels-Other) orders.
    
    Example - Breakout strategy:
        AAPL at $270: Buy @ $280 (breakout) OR Sell @ $260 (breakdown)
        
    Example - Take profit or stop loss:
        Own 100 TSLA: Sell @ $450 (profit) OR Sell @ $380 (stop)
    """
    try:
        from ib_insync import Stock
        from app.models.trading import Order, OrderStatus
        
        # Create contract
        contract = Stock(
            symbol=request.symbol,
            exchange=request.exchange,
            currency=request.currency
        )

        # Place OCO orders
        trade1, trade2, oca_group = await ib_client.place_oco_order(
            contract=contract,
            quantity=request.quantity,
            order1_action=request.order1_action,
            order1_type=request.order1_type,
            order1_price=float(request.order1_price),
            order2_action=request.order2_action,
            order2_type=request.order2_type,
            order2_price=float(request.order2_price),
            time_in_force=request.time_in_force
        )

        # Store first order in database
        db_order1 = Order(
            order_id=trade1.order.orderId,
            symbol=request.symbol,
            action=request.order1_action,
            order_type=OrderType.LIMIT if request.order1_type == "LMT" else OrderType.STOP,
            total_quantity=request.quantity,
            limit_price=request.order1_price if request.order1_type == "LMT" else None,
            stop_price=request.order1_price if request.order1_type == "STP" else None,
            status=OrderStatus.SUBMITTED,
            time_in_force=request.time_in_force,
            client_id=settings.IB_CLIENT_ID,
            sec_type="STK",
            exchange=request.exchange,
            currency=request.currency,
            filled_quantity=0,
            remaining_quantity=request.quantity,
            risk_check_passed=True
        )
        db.add(db_order1)
        
        # Store second order in database
        db_order2 = Order(
            order_id=trade2.order.orderId,
            symbol=request.symbol,
            action=request.order2_action,
            order_type=OrderType.LIMIT if request.order2_type == "LMT" else OrderType.STOP,
            total_quantity=request.quantity,
            limit_price=request.order2_price if request.order2_type == "LMT" else None,
            stop_price=request.order2_price if request.order2_type == "STP" else None,
            status=OrderStatus.SUBMITTED,
            time_in_force=request.time_in_force,
            client_id=settings.IB_CLIENT_ID,
            sec_type="STK",
            exchange=request.exchange,
            currency=request.currency,
            filled_quantity=0,
            remaining_quantity=request.quantity,
            risk_check_passed=True
        )
        db.add(db_order2)
        
        db.commit()

        logger.info(
            "oco_orders_created",
            symbol=request.symbol,
            order1_id=trade1.order.orderId,
            order2_id=trade2.order.orderId,
            oca_group=oca_group
        )

        return OCOOrderResponse(
            order1_id=trade1.order.orderId,
            order2_id=trade2.order.orderId,
            symbol=request.symbol,
            oca_group=oca_group,
            status="submitted",
            message=f"OCO orders placed for {request.symbol}"
        )

    except Exception as e:
        logger.error("oco_order_endpoint_error", error=str(e))
        raise HTTPException(500, f"Failed to place OCO order: {str(e)}")
