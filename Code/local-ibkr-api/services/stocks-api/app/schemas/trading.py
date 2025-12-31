"""
Pydantic schemas for API request/response validation.

Defines data validation schemas for orders, positions, accounts, and errors.
"""
from typing import Optional, List
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
