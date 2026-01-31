"""Bulk order schemas."""
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal, List
from decimal import Decimal

class BulkOrderInput(BaseModel):
    """Standard order input format."""
    order_type: Literal["MKT", "LMT", "STP"] = Field(..., description="Order type")
    symbol: str = Field(..., description="Stock symbol")
    action: Literal["BUY", "SELL"] = Field(..., description="Order action")
    quantity: int = Field(..., gt=0, description="Number of shares")
    limit_price: Optional[Decimal] = Field(None, description="Limit price")
    stop_price: Optional[Decimal] = Field(None, description="Stop price")
    time_in_force: Literal["DAY", "GTC", "IOC", "FOK"] = Field("DAY")
    exchange: str = Field("SMART")
    currency: str = Field("USD")
    client_order_id: Optional[str] = None
    notes: Optional[str] = None

class BulkOrderResponse(BaseModel):
    """Response for bulk order submission."""
    total_orders: int
    successful: int
    failed: int
    results: List[dict]
