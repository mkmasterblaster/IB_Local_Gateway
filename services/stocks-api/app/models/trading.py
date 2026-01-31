from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Numeric, ForeignKey, Text, Index, Enum as SQLEnum, text
"""
Database models for trading operations.

SQLAlchemy models for orders, fills, positions, and account snapshots.
"""
from datetime import datetime
from typing import Optional
from decimal import Decimal
from sqlalchemy.schema import FetchedValue
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class OrderType(enum.Enum):
    """Order type enumeration."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TRAILING_STOP = "TRAILING_STOP"
    BRACKET_PARENT = "BRACKET_PARENT"
    BRACKET_PROFIT = "BRACKET_PROFIT"
    BRACKET_STOP = "BRACKET_STOP"


class OrderAction(enum.Enum):
    """Order action enumeration."""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(enum.Enum):
    """Order status enumeration."""
    PENDING_SUBMIT = "PendingSubmit"
    PENDING_CANCEL = "PendingCancel"
    PRE_SUBMITTED = "PreSubmitted"
    SUBMITTED = "Submitted"
    API_CANCELLED = "ApiCancelled"
    CANCELLED = "Cancelled"
    FILLED = "Filled"
    INACTIVE = "Inactive"
    PARTIALLY_FILLED = "PartiallyFilled"
    API_PENDING = "ApiPending"
    PENDING_NEW = "PendingNew"


class TimeInForce(enum.Enum):
    """Time in force enumeration."""
    DAY = "DAY"
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate or Cancel
    GTD = "GTD"  # Good Till Date
    OPG = "OPG"  # Market on Open
    FOK = "FOK"  # Fill or Kill


class Order(Base):
    """
    Order model - represents trading orders.

    Tracks all orders submitted to IBKR including their current status,
    fills, and execution details.
    """
    __tablename__ = "orders"

    # Primary identifiers
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(
        Integer,
        nullable=False, unique=True, index=True,
        server_default=text("nextval('orders_order_id_seq'::regclass)")
    )
    ib_order_id = Column(Integer, nullable=True, index=True)  # IBKR's order ID (can be reused by IB)
    perm_id = Column(Integer, nullable=True, index=True)  # IBKR permanent ID
    client_id = Column(Integer, nullable=False)

    # Order details
    symbol = Column(String(20), nullable=False, index=True)
    sec_type = Column(String(10), nullable=False, default="STK")  # STK, OPT, FUT, etc.
    exchange = Column(String(20), nullable=False, default="SMART")
    currency = Column(String(3), nullable=False, default="USD")

    # Order specifications
    action = Column(SQLEnum(OrderAction), nullable=False, index=True)
    order_type = Column(SQLEnum(OrderType), nullable=False, index=True)
    total_quantity = Column(Float, nullable=False)
    limit_price = Column(Numeric(10, 2), nullable=True)
    stop_price = Column(Numeric(10, 2), nullable=True)
    time_in_force = Column(SQLEnum(TimeInForce), nullable=False, default=TimeInForce.DAY)

    # Order status
    status = Column(SQLEnum(OrderStatus), nullable=False, index=True)
    filled_quantity = Column(Float, nullable=False, default=0.0)
    remaining_quantity = Column(Float, nullable=False)
    avg_fill_price = Column(Numeric(10, 4), nullable=True)
    last_fill_price = Column(Numeric(10, 4), nullable=True)

    # Additional details
    account = Column(String(50), nullable=True)
    why_held = Column(String(200), nullable=True)
    warning_text = Column(Text, nullable=True)

    # Risk check flags
    risk_check_passed = Column(Boolean, nullable=False, default=False)
    risk_check_reason = Column(String(200), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    submitted_at = Column(DateTime, nullable=True)
    filled_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    fills = relationship("Fill", back_populates="order", cascade="all, delete-orphan")

    # Indexes for common queries


    def __repr__(self):
        return (
            f"<Fill(id={self.id}, exec_id={self.exec_id}, "
            f"order_id={self.order_id}, shares={self.shares}, price={self.price})>"
        )




class Fill(Base):
    """
    Fill model - represents executions/fills.
    Matches DB table: public.fills
    FK: fills.order_id -> orders.order_id
    """
    __tablename__ = "fills"

    id = Column(Integer, primary_key=True, index=True)
    exec_id = Column(String(50), nullable=False, unique=True, index=True)

    # IMPORTANT: FK target is orders.order_id (per \d fills)
    order_id = Column(Integer, ForeignKey("orders.order_id"), nullable=False, index=True)

    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(4), nullable=False)
    shares = Column(Float, nullable=False)
    price = Column(Numeric(10, 4), nullable=False)
    exchange = Column(String(20), nullable=False)

    cum_qty = Column(Float, nullable=False)
    avg_price = Column(Numeric(10, 4), nullable=False)

    commission = Column(Numeric(10, 2), nullable=True)
    commission_currency = Column(String(3), nullable=True)
    realized_pnl = Column(Numeric(10, 2), nullable=True)

    execution_time = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # backref to Order.fills
    order = relationship("Order", back_populates="fills")

    def __repr__(self):
        return (
            f"<Fill(id={self.id}, exec_id={self.exec_id}, "
            f"order_id={self.order_id}, shares={self.shares}, price={self.price})>"
        )

class Position(Base):
    """
    Position model - represents current positions.

    Snapshot of positions at different times for tracking and analysis.
    """
    __tablename__ = "positions"

    # Primary identifiers
    id = Column(Integer, primary_key=True, index=True)
    account = Column(String(50), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    sec_type = Column(String(10), nullable=False, default="STK")
    exchange = Column(String(20), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")

    # Position details
    position_size = Column(Float, nullable=False)
    avg_cost = Column(Numeric(10, 4), nullable=False)
    market_price = Column(Numeric(10, 4), nullable=True)
    market_value = Column(Numeric(12, 2), nullable=True)

    # P&L information
    unrealized_pnl = Column(Numeric(12, 2), nullable=True)
    realized_pnl = Column(Numeric(12, 2), nullable=True)

    # Timestamps
    snapshot_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = ()
    def __repr__(self):
        return (
            f"<Position(id={self.id}, account={self.account}, "
            f"symbol={self.symbol}, size={self.position_size})>"
        )


class AccountSnapshot(Base):
    """
    Account snapshot model - represents account state at a point in time.

    Tracks key account metrics for monitoring and analysis.
    """
    __tablename__ = "account_snapshots"

    # Primary identifiers
    id = Column(Integer, primary_key=True, index=True)
    account = Column(String(50), nullable=False, index=True)

    # Account values
    net_liquidation = Column(Numeric(15, 2), nullable=False)
    total_cash_value = Column(Numeric(15, 2), nullable=False)
    settled_cash = Column(Numeric(15, 2), nullable=False)
    buying_power = Column(Numeric(15, 2), nullable=False)
    gross_position_value = Column(Numeric(15, 2), nullable=False)

    # P&L
    unrealized_pnl = Column(Numeric(12, 2), nullable=False)
    realized_pnl = Column(Numeric(12, 2), nullable=False)
    daily_pnl = Column(Numeric(12, 2), nullable=True)

    # Margins
    available_funds = Column(Numeric(15, 2), nullable=False)
    excess_liquidity = Column(Numeric(15, 2), nullable=False)
    cushion = Column(Numeric(5, 4), nullable=True)

    # Timestamps
    snapshot_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Indexes
    __table_args__ = ()
    def __repr__(self):
        return (
            f"<AccountSnapshot(id={self.id}, account={self.account}, "
            f"net_liq={self.net_liquidation}, snapshot_time={self.snapshot_time})>"
        )


class TradingSession(Base):
    """
    Trading session model - tracks trading sessions for audit and analysis.

    Records when trading starts/stops, connection status, and session metrics.
    """
    __tablename__ = "trading_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(50), unique=True, nullable=False, index=True)

    # Session details
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    # Connection info
    ib_gateway_host = Column(String(100), nullable=False)
    ib_gateway_port = Column(Integer, nullable=False)
    client_id = Column(Integer, nullable=False)

    # Session metrics
    orders_placed = Column(Integer, nullable=False, default=0)
    orders_filled = Column(Integer, nullable=False, default=0)
    orders_cancelled = Column(Integer, nullable=False, default=0)
    total_volume = Column(Float, nullable=False, default=0.0)

    # Notes
    notes = Column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<TradingSession(id={self.id}, session_id={self.session_id}, "
            f"start={self.start_time}, active={self.is_active})>"
        )


class ConditionalOrder(Base):
    """Conditional orders - execute when condition is met."""
    __tablename__ = "conditional_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Condition
    condition_type = Column(String, nullable=False)  # PRICE_ABOVE, PRICE_BELOW
    condition_symbol = Column(String, nullable=False, index=True)
    condition_price = Column(Numeric(precision=10, scale=2), nullable=False)
    
    # Order to execute
    order_symbol = Column(String, nullable=False)
    order_action = Column(String, nullable=False)  # BUY, SELL
    order_type = Column(String, nullable=False)  # MKT, LMT
    order_quantity = Column(Integer, nullable=False)
    order_limit_price = Column(Numeric(precision=10, scale=2), nullable=True)
    
    # Metadata
    time_in_force = Column(String, default="DAY")
    exchange = Column(String, default="SMART")
    currency = Column(String, default="USD")
    
    # Status tracking
    status = Column(String, default="ACTIVE", index=True)  # ACTIVE, TRIGGERED, CANCELLED
    created_at = Column(DateTime, default=datetime.utcnow)
    triggered_at = Column(DateTime, nullable=True)
    executed_order_id = Column(Integer, nullable=True)  # Order ID when triggered
    
    # Tracking
    last_checked_price = Column(Numeric(precision=10, scale=2), nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
