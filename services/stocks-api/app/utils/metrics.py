"""
Prometheus Metrics Collection.

Provides metrics for system monitoring, API performance, and business intelligence.
"""
import time
from typing import Callable

from fastapi import Request, Response
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.utils.logging import get_logger

logger = get_logger(__name__)

# ==========================================
# System Metrics
# ==========================================

# API Request Metrics
api_requests_total = Counter(
    "api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status_code"]
)

api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0)
)

api_requests_in_progress = Gauge(
    "api_requests_in_progress",
    "Number of API requests currently being processed",
    ["method", "endpoint"]
)

# Connection Status Metrics
ib_connection_status = Gauge(
    "ib_connection_status",
    "IB Gateway connection status (1=connected, 0=disconnected)",
    ["container"]
)

database_connection_status = Gauge(
    "database_connection_status",
    "Database connection status (1=connected, 0=disconnected)"
)

redis_connection_status = Gauge(
    "redis_connection_status",
    "Redis connection status (1=connected, 0=disconnected)"
)

# ==========================================
# Business Metrics
# ==========================================

# Order Metrics
orders_total = Counter(
    "orders_total",
    "Total number of orders placed",
    ["container", "order_type", "action", "status"]
)

order_latency_seconds = Histogram(
    "order_latency_seconds",
    "Order placement latency in seconds",
    ["order_type"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0)
)

order_rejections_total = Counter(
    "order_rejections_total",
    "Total number of rejected orders",
    ["reason"]
)

# Position Metrics
active_positions_total = Gauge(
    "active_positions_total",
    "Number of active positions",
    ["container"]
)

position_pnl_unrealized_total = Gauge(
    "position_pnl_unrealized_total",
    "Unrealized P&L across all positions",
    ["account", "container"]
)

position_pnl_realized_total = Gauge(
    "position_pnl_realized_total",
    "Realized P&L (daily)",
    ["account", "container"]
)

# Account Metrics
account_balance = Gauge(
    "account_balance",
    "Account balance",
    ["account", "currency"]
)

account_buying_power = Gauge(
    "account_buying_power",
    "Account buying power",
    ["account"]
)

# Risk Metrics
risk_limit_breaches_total = Counter(
    "risk_limit_breaches_total",
    "Total number of risk limit breaches",
    ["limit_type"]
)

circuit_breaker_triggered_total = Counter(
    "circuit_breaker_triggered_total",
    "Total number of circuit breaker triggers",
    ["reason"]
)

# Market Data Metrics
market_data_subscriptions = Gauge(
    "market_data_subscriptions",
    "Number of active market data subscriptions"
)

market_data_latency_seconds = Histogram(
    "market_data_latency_seconds",
    "Market data update latency in seconds",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0)
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """
    Middleware for collecting Prometheus metrics on API requests.
    
    Records request count, duration, and status codes.
    """
    
    def __init__(self, app: ASGIApp):
        """
        Initialize middleware.
        
        Args:
            app: ASGI application
        """
        super().__init__(app)
        logger.info("prometheus_middleware_initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and collect metrics.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Response
        """
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)
        
        method = request.method
        endpoint = request.url.path
        
        # Track in-progress requests
        api_requests_in_progress.labels(method=method, endpoint=endpoint).inc()
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            # Record error
            logger.error(
                "request_processing_error",
                method=method,
                endpoint=endpoint,
                error=str(e)
            )
            status_code = 500
            raise
        finally:
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            api_requests_total.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code
            ).inc()
            
            api_request_duration_seconds.labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
            
            # Decrement in-progress
            api_requests_in_progress.labels(method=method, endpoint=endpoint).dec()
        
        return response


def get_metrics() -> bytes:
    """
    Generate Prometheus metrics output.
    
    Returns:
        Prometheus metrics in text format
    """
    return generate_latest()


# Helper functions for business metrics

def record_order(
    order_type: str,
    action: str,
    status: str,
    container: str = "stocks",
    latency: float | None = None
):
    """
    Record order placement metrics.
    
    Args:
        order_type: Type of order (market, limit, etc.)
        action: Order action (buy, sell)
        status: Order status (submitted, filled, rejected, etc.)
        container: Container name
        latency: Optional order latency in seconds
    """
    orders_total.labels(
        container=container,
        order_type=order_type,
        action=action,
        status=status
    ).inc()
    
    if latency is not None:
        order_latency_seconds.labels(order_type=order_type).observe(latency)


def record_order_rejection(reason: str):
    """
    Record order rejection.
    
    Args:
        reason: Rejection reason
    """
    order_rejections_total.labels(reason=reason).inc()


def update_position_metrics(
    position_count: int,
    unrealized_pnl: float,
    realized_pnl: float,
    account: str,
    container: str = "stocks"
):
    """
    Update position-related metrics.
    
    Args:
        position_count: Number of active positions
        unrealized_pnl: Total unrealized P&L
        realized_pnl: Total realized P&L (daily)
        account: Account identifier
        container: Container name
    """
    active_positions_total.labels(container=container).set(position_count)
    position_pnl_unrealized_total.labels(account=account, container=container).set(unrealized_pnl)
    position_pnl_realized_total.labels(account=account, container=container).set(realized_pnl)


def update_account_metrics(
    balance: float,
    buying_power: float,
    account: str,
    currency: str = "USD"
):
    """
    Update account-related metrics.
    
    Args:
        balance: Account balance
        buying_power: Available buying power
        account: Account identifier
        currency: Currency code
    """
    account_balance.labels(account=account, currency=currency).set(balance)
    account_buying_power.labels(account=account).set(buying_power)


def record_risk_breach(limit_type: str):
    """
    Record risk limit breach.
    
    Args:
        limit_type: Type of limit breached
    """
    risk_limit_breaches_total.labels(limit_type=limit_type).inc()


def record_circuit_breaker(reason: str):
    """
    Record circuit breaker trigger.
    
    Args:
        reason: Reason for circuit breaker
    """
    circuit_breaker_triggered_total.labels(reason=reason).inc()


def set_ib_connection_status(connected: bool, container: str = "stocks"):
    """
    Set IB Gateway connection status.
    
    Args:
        connected: True if connected
        container: Container name
    """
    ib_connection_status.labels(container=container).set(1 if connected else 0)


def set_database_connection_status(connected: bool):
    """
    Set database connection status.
    
    Args:
        connected: True if connected
    """
    database_connection_status.set(1 if connected else 0)


def set_redis_connection_status(connected: bool):
    """
    Set Redis connection status.
    
    Args:
        connected: True if connected
    """
    redis_connection_status.set(1 if connected else 0)
