"""
Pydantic schemas for API request/response validation.

Defines data validation schemas for orders, positions, accounts, and errors.
"""
from typing import Optional, Literal, List
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ============================================================================
# Order Schemas
# ============================================================================

class OrderRequest(BaseModel):
    """Schema for creating a new order."""
    symbol: str = Field(..., min_length=1, max_length=20, description="Trading symbol")
    action: str = Field(..., pattern="^(BUY|SELL)$", description="Order action")
    quantity: float = Field(..., gt=0, description="Order quantity")
    order_type: str = Field(
        ...,
        pattern="^(MKT|LMT|STP|STP LMT|TRAIL)$",
        description="Order type"
    )
    limit_price: Optional[float] = Field(None, gt=0, description="Limit price (for limit orders)")
    stop_price: Optional[float] = Field(None, gt=0, description="Stop price (for stop orders)")
    time_in_force: str = Field(
        "DAY",
        pattern="^(DAY|GTC|IOC|GTD|OPG|FOK)$",
        description="Time in force"
    )
    sec_type: str = Field("STK", description="Security type")
    exchange: str = Field("SMART", description="Exchange")
    currency: str = Field("USD", description="Currency")

    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format."""
        return v.upper().strip()

    @field_validator('limit_price')
    @classmethod
    def validate_limit_price(cls, v: Optional[float], info) -> Optional[float]:
        """Validate limit price is provided for limit orders."""
        order_type = info.data.get('order_type')
        if order_type in ['LMT', 'STP LMT'] and v is None:
            raise ValueError('limit_price required for limit orders')
        return v

    @field_validator('stop_price')
    @classmethod
    def validate_stop_price(cls, v: Optional[float], info) -> Optional[float]:
        """Validate stop price is provided for stop orders."""
        order_type = info.data.get('order_type')
        if order_type in ['STP', 'STP LMT', 'TRAIL'] and v is None:
            raise ValueError('stop_price required for stop orders')
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "AAPL",
                "action": "BUY",
                "quantity": 100,
                "order_type": "LMT",
                "limit_price": 150.50,
                "time_in_force": "DAY",
                "sec_type": "STK",
                "exchange": "SMART",
                "currency": "USD"
            }
        }
    )


class OrderResponse(BaseModel):
    """Schema for order response."""
    id: int
    order_id: int
    perm_id: Optional[int] = None
    symbol: str
    sec_type: str
    action: str
    order_type: str
    total_quantity: float
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    status: str
    filled_quantity: float
    remaining_quantity: float
    avg_fill_price: Optional[Decimal] = None
    account: Optional[str] = None
    risk_check_passed: bool
    created_at: datetime
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrderListResponse(BaseModel):
    """Schema for list of orders."""
    orders: List[OrderResponse]
    total: int
    page: int
    page_size: int


class OrderCancelRequest(BaseModel):
    """Schema for canceling an order."""
    order_id: int = Field(..., gt=0, description="IBKR order ID to cancel")


# ============================================================================
# Fill Schemas
# ============================================================================

class FillResponse(BaseModel):
    """Schema for fill/execution response."""
    id: int
    exec_id: str
    order_id: int
    symbol: str
    side: str
    shares: float
    price: Decimal
    exchange: str
    cum_qty: float
    avg_price: Decimal
    commission: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    execution_time: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Position Schemas
# ============================================================================

class PositionResponse(BaseModel):
    """Schema for position response."""
    id: int
    account: str
    symbol: str
    sec_type: str
    position_size: float
    avg_cost: Decimal
    market_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None
    snapshot_time: datetime

    model_config = ConfigDict(from_attributes=True)


class PositionListResponse(BaseModel):
    """Schema for list of positions."""
    positions: List[PositionResponse]
    total: int


# ============================================================================
# Account Schemas
# ============================================================================

class AccountSummaryResponse(BaseModel):
    """Schema for account summary response."""
    account: str
    net_liquidation: Decimal
    total_cash_value: Decimal
    buying_power: Decimal
    gross_position_value: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    daily_pnl: Optional[Decimal] = None
    available_funds: Decimal
    excess_liquidity: Decimal
    cushion: Optional[Decimal] = None
    snapshot_time: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountPnLResponse(BaseModel):
    """Schema for account P&L response."""
    account: str
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    daily_pnl: Optional[Decimal] = None
    timestamp: datetime


# ============================================================================
# Risk Check Schemas
# ============================================================================

class RiskCheckResult(BaseModel):
    """Schema for risk check result."""
    passed: bool
    reason: Optional[str] = None
    checks_performed: List[str]
    warnings: List[str] = []


class RiskLimits(BaseModel):
    """Schema for risk limit configuration."""
    max_order_value: float = Field(..., gt=0, description="Maximum single order value")
    max_position_value: float = Field(..., gt=0, description="Maximum position value")
    max_daily_loss: float = Field(..., gt=0, description="Maximum daily loss")
    max_leverage: float = Field(..., gt=0, le=10.0, description="Maximum leverage")
    allowed_symbols: Optional[List[str]] = Field(None, description="Whitelist of symbols")
    blocked_symbols: Optional[List[str]] = Field(None, description="Blacklist of symbols")


# ============================================================================
# Error Schemas
# ============================================================================

class ErrorDetail(BaseModel):
    """Schema for error detail."""
    field: Optional[str] = None
    message: str
    error_code: Optional[str] = None


class ErrorResponse(BaseModel):
    """Schema for error response."""
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = Field(None, description="Request correlation ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error_code": "ORDER_VALIDATION_FAILED",
                "message": "Order quantity exceeds position limit",
                "details": {
                    "field": "quantity",
                    "limit": 1000,
                    "requested": 1500
                },
                "timestamp": "2024-01-15T10:30:00.123Z",
                "request_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }
    )


# ============================================================================
# Status Schemas
# ============================================================================

class HealthStatus(BaseModel):
    """Schema for health check status."""
    status: str = Field(..., pattern="^(ok|degraded|error)$")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ServiceStatus(BaseModel):
    """Schema for individual service status."""
    name: str
    status: str
    details: Optional[dict] = None


class SystemStatus(BaseModel):
    """Schema for overall system status."""
    status: str
    services: List[ServiceStatus]
    timestamp: datetime


# ============================================================================
# Statistics Schemas
# ============================================================================

class OrderStatistics(BaseModel):
    """Schema for order statistics."""
    total_orders: int
    filled_orders: int
    cancelled_orders: int
    pending_orders: int
    total_volume: float
    avg_fill_price: Optional[Decimal] = None
    period_start: datetime
    period_end: datetime


class TradingMetrics(BaseModel):
    """Schema for trading metrics."""
    total_pnl: Decimal
    win_rate: float
    avg_win: Decimal
    avg_loss: Decimal
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    total_trades: int
    period_start: datetime
    period_end: datetime


# ============================================================================
# Pagination Schemas
# ============================================================================

class PaginationParams(BaseModel):
    """Schema for pagination parameters."""
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=1000, description="Items per page")


class PaginatedResponse(BaseModel):
    """Schema for paginated response."""
    items: List[dict]
    total: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        """Check if there's a next page."""
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        """Check if there's a previous page."""
        return self.page > 1


class BracketOrderRequest(BaseModel):
    """Bracket order: entry + profit target + stop loss."""
    symbol: str = Field(..., description="Stock symbol")
    action: Literal["BUY", "SELL"] = Field(..., description="Order action")
    quantity: int = Field(..., gt=0, description="Number of shares")
    
    # Entry order
    entry_type: Literal["MKT", "LMT"] = Field("MKT", description="Entry order type")
    entry_price: Optional[Decimal] = Field(None, description="Entry limit price (required if LMT)")
    
    # Exit orders
    profit_target: Decimal = Field(..., description="Take profit price")
    stop_loss: Decimal = Field(..., description="Stop loss price")
    
    # Optional
    time_in_force: Literal["DAY", "GTC"] = Field("DAY")
    exchange: str = Field("SMART")
    currency: str = Field("USD")
    
    @field_validator('entry_price')
    def validate_entry_price(cls, v, info):
        """Ensure entry_price provided if entry_type is LMT."""
        if info.data.get('entry_type') == 'LMT' and not v:
            raise ValueError("entry_price required when entry_type=LMT")
        return v
    
    @field_validator('stop_loss')
    def validate_bracket_prices(cls, stop_loss, info):
        """Ensure profit/stop make sense for BUY/SELL."""
        action = info.data.get('action')
        profit = info.data.get('profit_target')
        entry = info.data.get('entry_price')
        
        if not action or not profit:
            return stop_loss
            
        if action == "BUY":
            # For BUY: stop < entry/market < profit
            if stop_loss >= profit:
                raise ValueError("For BUY: stop_loss must be < profit_target")
            if entry and stop_loss >= entry:
                raise ValueError("For BUY: stop_loss must be < entry_price")
        else:  # SELL
            # For SELL: profit < entry/market < stop
            if stop_loss <= profit:
                raise ValueError("For SELL: stop_loss must be > profit_target")
            if entry and stop_loss <= entry:
                raise ValueError("For SELL: stop_loss must be > entry_price")
        
        return stop_loss


class BracketOrderResponse(BaseModel):
    """Response for bracket order placement."""
    parent_order_id: int
    profit_order_id: int
    stop_order_id: int
    symbol: str
    status: str
    message: str


class BracketOrderRequest(BaseModel):
    """Bracket order: entry + profit target + stop loss."""
    symbol: str = Field(..., description="Stock symbol")
    action: Literal["BUY", "SELL"] = Field(..., description="Order action")
    quantity: int = Field(..., gt=0, description="Number of shares")
    
    # Entry order
    entry_type: Literal["MKT", "LMT"] = Field("MKT", description="Entry order type")
    entry_price: Optional[Decimal] = Field(None, description="Entry limit price (required if LMT)")
    
    # Exit orders
    profit_target: Decimal = Field(..., description="Take profit price")
    stop_loss: Decimal = Field(..., description="Stop loss price")
    
    # Optional
    time_in_force: Literal["DAY", "GTC"] = Field("DAY")
    exchange: str = Field("SMART")
    currency: str = Field("USD")
    
    @field_validator('entry_price')
    def validate_entry_price(cls, v, info):
        """Ensure entry_price provided if entry_type is LMT."""
        if info.data.get('entry_type') == 'LMT' and not v:
            raise ValueError("entry_price required when entry_type=LMT")
        return v
    
    @field_validator('stop_loss')
    def validate_bracket_prices(cls, stop_loss, info):
        """Ensure profit/stop make sense for BUY/SELL."""
        action = info.data.get('action')
        profit = info.data.get('profit_target')
        entry = info.data.get('entry_price')
        
        if not action or not profit:
            return stop_loss
            
        if action == "BUY":
            # For BUY: stop < entry/market < profit
            if stop_loss >= profit:
                raise ValueError("For BUY: stop_loss must be < profit_target")
            if entry and stop_loss >= entry:
                raise ValueError("For BUY: stop_loss must be < entry_price")
        else:  # SELL
            # For SELL: profit < entry/market < stop
            if stop_loss <= profit:
                raise ValueError("For SELL: stop_loss must be > profit_target")
            if entry and stop_loss <= entry:
                raise ValueError("For SELL: stop_loss must be > entry_price")
        
        return stop_loss


class BracketOrderResponse(BaseModel):
    """Response for bracket order placement."""
    parent_order_id: int
    profit_order_id: int
    stop_order_id: int
    symbol: str
    status: str
    message: str


class TrailingStopRequest(BaseModel):
    """Trailing stop order request."""
    symbol: str = Field(..., description="Stock symbol")
    action: Literal["BUY", "SELL"] = Field(..., description="Order action")
    quantity: int = Field(..., gt=0, description="Number of shares")
    
    # Trail settings (must provide ONE)
    trail_stop_price: Optional[Decimal] = Field(None, description="Trailing amount in dollars")
    trail_percent: Optional[Decimal] = Field(None, description="Trailing percentage")
    
    # Optional
    time_in_force: Literal["DAY", "GTC"] = Field("GTC", description="Trailing stops typically GTC")
    exchange: str = Field("SMART")
    currency: str = Field("USD")
    
    @field_validator('trail_percent')
    def validate_trail_params(cls, trail_percent, info):
        """Ensure either trail_stop_price OR trail_percent is provided."""
        trail_stop_price = info.data.get('trail_stop_price')
        
        if not trail_stop_price and not trail_percent:
            raise ValueError("Must provide either trail_stop_price OR trail_percent")
        
        if trail_stop_price and trail_percent:
            raise ValueError("Provide either trail_stop_price OR trail_percent, not both")
        
        if trail_percent and (trail_percent <= 0 or trail_percent >= 100):
            raise ValueError("trail_percent must be between 0 and 100")
        
        return trail_percent


class TrailingStopResponse(BaseModel):
    """Response for trailing stop placement."""
    order_id: int
    symbol: str
    trail_amount: Optional[str] = None
    trail_percent: Optional[str] = None
    status: str
    message: str


class OrderModificationRequest(BaseModel):
    """Request to modify an existing order."""
    # Optional modifications (provide what you want to change)
    quantity: Optional[int] = Field(None, gt=0, description="New quantity")
    limit_price: Optional[Decimal] = Field(None, description="New limit price")
    stop_price: Optional[Decimal] = Field(None, description="New stop price")
    trail_stop_price: Optional[Decimal] = Field(None, description="New trailing amount ($)")
    trail_percent: Optional[Decimal] = Field(None, description="New trailing percent")
    
    @field_validator('quantity', 'limit_price', 'stop_price', 'trail_stop_price', 'trail_percent')
    def at_least_one_modification(cls, v, info):
        """Ensure at least one field is being modified."""
        # This runs for each field - we'll check in the endpoint
        return v


class OrderModificationResponse(BaseModel):
    """Response for order modification."""
    order_id: int
    symbol: str
    modifications: dict
    status: str
    message: str


class OCOOrderRequest(BaseModel):
    """One-Cancels-Other order request (two linked orders)."""
    symbol: str = Field(..., description="Stock symbol")
    quantity: int = Field(..., gt=0, description="Number of shares for both orders")
    
    # First order (typically breakout above)
    order1_action: Literal["BUY", "SELL"] = Field(..., description="Action for first order")
    order1_type: Literal["LMT", "STP"] = Field(..., description="Order type for first order")
    order1_price: Decimal = Field(..., description="Trigger/limit price for first order")
    
    # Second order (typically breakdown below)
    order2_action: Literal["BUY", "SELL"] = Field(..., description="Action for second order")
    order2_type: Literal["LMT", "STP"] = Field(..., description="Order type for second order")
    order2_price: Decimal = Field(..., description="Trigger/limit price for second order")
    
    # Optional
    time_in_force: Literal["DAY", "GTC"] = Field("GTC", description="Time in force for both orders")
    exchange: str = Field("SMART")
    currency: str = Field("USD")
    
    @field_validator('order2_action')
    def validate_opposite_actions(cls, order2_action, info):
        """Typically OCO orders have opposite actions (BUY/SELL)."""
        order1_action = info.data.get('order1_action')
        
        # Just a warning - we allow same actions too
        if order1_action == order2_action:
            logger = __import__('structlog').get_logger()
            logger.warning(
                "oco_same_actions",
                msg="OCO orders typically have opposite actions (BUY vs SELL)"
            )
        
        return order2_action


class OCOOrderResponse(BaseModel):
    """Response for OCO order placement."""
    order1_id: int
    order2_id: int
    symbol: str
    oca_group: str
    status: str
    message: str


class ConditionalOrderRequest(BaseModel):
    """Conditional order - executes when condition is met."""
    # Condition
    condition_type: Literal["PRICE_ABOVE", "PRICE_BELOW"] = Field(
        ..., 
        description="Type of condition"
    )
    condition_symbol: str = Field(..., description="Symbol to watch for condition")
    condition_price: Decimal = Field(..., description="Trigger price")
    
    # Order to execute when condition met
    order_symbol: str = Field(..., description="Symbol to trade")
    order_action: Literal["BUY", "SELL"] = Field(..., description="Order action")
    order_type: Literal["MKT", "LMT"] = Field("MKT", description="Order type to place")
    order_quantity: int = Field(..., gt=0, description="Number of shares")
    order_limit_price: Optional[Decimal] = Field(None, description="Limit price if LMT order")
    
    # Optional
    time_in_force: Literal["DAY", "GTC"] = Field("DAY")
    exchange: str = Field("SMART")
    currency: str = Field("USD")
    
    @field_validator('order_limit_price')
    def validate_limit_price_if_lmt(cls, order_limit_price, info):
        """Ensure limit price provided if order type is LMT."""
        order_type = info.data.get('order_type')
        if order_type == 'LMT' and not order_limit_price:
            raise ValueError("order_limit_price required when order_type=LMT")
        return order_limit_price


class ConditionalOrderResponse(BaseModel):
    """Response for conditional order creation."""
    condition_id: int
    condition_type: str
    condition_symbol: str
    condition_price: str
    order_symbol: str
    order_action: str
    status: str
    message: str


# Algo Order Schemas
class AlgoOrderRequest(BaseModel):
    """Request schema for algo orders."""
    symbol: str
    action: str  # BUY or SELL
    quantity: int
    algo_strategy: str  # VWAP, TWAP, Adaptive
    
    # Time parameters
    start_time: Optional[str] = None  # HH:MM:SS format
    end_time: Optional[str] = None    # HH:MM:SS format
    
    # Strategy-specific parameters
    max_pct_volume: Optional[float] = 0.1  # For VWAP: max % of volume (default 10%)
    time_between_orders: Optional[int] = 60  # For TWAP: seconds between orders
    urgency: Optional[str] = "Normal"  # For Adaptive: Urgent, Normal, Patient
    
    # Optional limit price
    limit_price: Optional[float] = None
    
    # Standard fields
    exchange: str = "SMART"
    currency: str = "USD"
    time_in_force: str = "DAY"
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "AAPL",
                "action": "BUY",
                "quantity": 1000,
                "algo_strategy": "VWAP",
                "start_time": "09:30:00",
                "end_time": "16:00:00",
                "max_pct_volume": 0.1
            }
        }


class AlgoOrderResponse(BaseModel):
    """Response schema for algo orders."""
    order_id: int
    symbol: str
    action: str
    quantity: int
    algo_strategy: str
    status: str
    message: str
    
    class Config:
        from_attributes = True
