"""
Risk management module for pre-trade validation.

Implements comprehensive risk checks before orders are submitted to IBKR,
including position limits, notional limits, and symbol restrictions.
"""
from typing import Optional, List, Tuple
from decimal import Decimal
from datetime import datetime, timedelta
import structlog

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.trading import Order, Position, AccountSnapshot, OrderStatus
from app.schemas.trading import OrderRequest, RiskCheckResult, RiskLimits
from app.config import get_settings

logger = structlog.get_logger(__name__)


class RiskManager:
    """
    Risk manager for pre-trade validation.

    Performs comprehensive checks before orders are submitted to IBKR
    to ensure compliance with risk limits and trading rules.
    """

    def __init__(self, db: Session, config: Optional[RiskLimits] = None):
        """
        Initialize risk manager.

        Args:
            db: Database session
            config: Risk limit configuration (uses defaults if None)
        """
        self.db = db
        self.settings = get_settings()

        # Use provided config or defaults
        self.config = config or self._get_default_limits()

        logger.info(
            "risk_manager_initialized",
            max_order_value=self.config.max_order_value,
            max_position_value=self.config.max_position_value
        )

    def check_order(
        self,
        order_request: OrderRequest,
        current_price: Optional[float] = None
    ) -> RiskCheckResult:
        """
        Perform comprehensive risk check on order.

        Args:
            order_request: The order to validate
            current_price: Current market price (used for market orders)

        Returns:
            RiskCheckResult: Result of risk checks with pass/fail and reasons
        """
        checks_performed = []
        warnings = []
        failed_check = None

        logger.info(
            "performing_risk_check",
            symbol=order_request.symbol,
            action=order_request.action,
            quantity=order_request.quantity
        )

        # 1. Symbol whitelist/blacklist check
        check_name = "symbol_restrictions"
        checks_performed.append(check_name)
        symbol_ok, symbol_reason = self._check_symbol_allowed(order_request.symbol)
        if not symbol_ok:
            failed_check = (check_name, symbol_reason)

        # 2. Order value check
        if failed_check is None:
            check_name = "order_value_limit"
            checks_performed.append(check_name)
            order_value_ok, order_value_reason = self._check_order_value(
                order_request, current_price
            )
            if not order_value_ok:
                failed_check = (check_name, order_value_reason)

        # 3. Position size check
        if failed_check is None:
            check_name = "position_size_limit"
            checks_performed.append(check_name)
            position_ok, position_reason = self._check_position_limit(
                order_request, current_price
            )
            if not position_ok:
                failed_check = (check_name, position_reason)

        # 4. Daily loss check
        if failed_check is None:
            check_name = "daily_loss_limit"
            checks_performed.append(check_name)
            daily_loss_ok, daily_loss_reason = self._check_daily_loss()
            if not daily_loss_ok:
                failed_check = (check_name, daily_loss_reason)
            elif daily_loss_reason:
                warnings.append(daily_loss_reason)

        # 5. Leverage check
        if failed_check is None:
            check_name = "leverage_limit"
            checks_performed.append(check_name)
            leverage_ok, leverage_reason = self._check_leverage(
                order_request, current_price
            )
            if not leverage_ok:
                failed_check = (check_name, leverage_reason)
            elif leverage_reason:
                warnings.append(leverage_reason)

        # 6. Order count/rate limit check
        if failed_check is None:
            check_name = "order_rate_limit"
            checks_performed.append(check_name)
            rate_ok, rate_reason = self._check_order_rate()
            if not rate_ok:
                failed_check = (check_name, rate_reason)

        # Log result
        if failed_check:
            logger.warning(
                "risk_check_failed",
                symbol=order_request.symbol,
                failed_check=failed_check[0],
                reason=failed_check[1]
            )
            return RiskCheckResult(
                passed=False,
                reason=failed_check[1],
                checks_performed=checks_performed,
                warnings=warnings
            )
        else:
            logger.info(
                "risk_check_passed",
                symbol=order_request.symbol,
                checks_performed=checks_performed,
                warnings_count=len(warnings)
            )
            return RiskCheckResult(
                passed=True,
                reason=None,
                checks_performed=checks_performed,
                warnings=warnings
            )

    def _check_symbol_allowed(self, symbol: str) -> Tuple[bool, Optional[str]]:
        """
        Check if symbol is allowed to trade.

        Args:
            symbol: Trading symbol

        Returns:
            Tuple of (is_allowed, reason)
        """
        # Check blacklist
        if self.config.blocked_symbols and symbol in self.config.blocked_symbols:
            return False, f"Symbol {symbol} is on the blocked list"

        # Check whitelist (if configured)
        if self.config.allowed_symbols and symbol not in self.config.allowed_symbols:
            return False, f"Symbol {symbol} is not on the allowed list"

        return True, None

    def _check_order_value(
        self,
        order_request: OrderRequest,
        current_price: Optional[float]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if order value is within limits.

        Args:
            order_request: The order to check
            current_price: Current market price

        Returns:
            Tuple of (is_ok, reason)
        """
        # Determine price to use for calculation
        if order_request.order_type == "MKT":
            if current_price is None:
                # Can't validate market orders without current price
                logger.warning(
                    "market_order_without_price",
                    symbol=order_request.symbol
                )
                return True, None
            price = current_price
        else:
            # Use limit price for limit orders
            price = float(order_request.limit_price or 0)

        order_value = order_request.quantity * price

        if order_value > self.config.max_order_value:
            return False, (
                f"Order value ${order_value:,.2f} exceeds limit "
                f"of ${self.config.max_order_value:,.2f}"
            )

        return True, None

    def _check_position_limit(
        self,
        order_request: OrderRequest,
        current_price: Optional[float]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if resulting position would exceed limits.

        Args:
            order_request: The order to check
            current_price: Current market price

        Returns:
            Tuple of (is_ok, reason)
        """
        # Get current position
        current_position = self.db.query(Position).filter(
            Position.symbol == order_request.symbol
        ).order_by(Position.snapshot_time.desc()).first()

        current_size = current_position.position_size if current_position else 0.0

        # Calculate new position size
        if order_request.action == "BUY":
            new_size = current_size + order_request.quantity
        else:  # SELL
            new_size = current_size - order_request.quantity

        # Get price for value calculation
        if current_price:
            price = current_price
        elif current_position and current_position.market_price:
            price = float(current_position.market_price)
        elif order_request.limit_price:
            price = float(order_request.limit_price)
        else:
            # Can't validate without price
            return True, None

        position_value = abs(new_size * price)

        if position_value > self.config.max_position_value:
            return False, (
                f"Position value ${position_value:,.2f} would exceed limit "
                f"of ${self.config.max_position_value:,.2f}"
            )

        return True, None

    def _check_daily_loss(self) -> Tuple[bool, Optional[str]]:
        """
        Check if daily loss limit has been reached.

        Returns:
            Tuple of (is_ok, reason/warning)
        """
        # Get today's start
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        # Get most recent account snapshot
        latest_snapshot = self.db.query(AccountSnapshot).filter(
            AccountSnapshot.snapshot_time >= today_start
        ).order_by(AccountSnapshot.snapshot_time.desc()).first()

        if not latest_snapshot:
            # No snapshot today, can't check
            return True, None

        daily_pnl = float(latest_snapshot.daily_pnl or 0)

        # Check if loss exceeds limit
        if daily_pnl < -self.config.max_daily_loss:
            return False, (
                f"Daily loss ${abs(daily_pnl):,.2f} exceeds limit "
                f"of ${self.config.max_daily_loss:,.2f}"
            )

        # Warning if approaching limit (80% of limit)
        if daily_pnl < -(self.config.max_daily_loss * 0.8):
            return True, (
                f"Warning: Daily loss ${abs(daily_pnl):,.2f} approaching limit "
                f"of ${self.config.max_daily_loss:,.2f}"
            )

        return True, None

    def _check_leverage(
        self,
        order_request: OrderRequest,
        current_price: Optional[float]
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if leverage is within limits.

        Args:
            order_request: The order to check
            current_price: Current market price

        Returns:
            Tuple of (is_ok, reason/warning)
        """
        # Get latest account snapshot
        latest_snapshot = self.db.query(AccountSnapshot).order_by(
            AccountSnapshot.snapshot_time.desc()
        ).first()

        if not latest_snapshot:
            # No account data, can't check
            return True, None

        net_liquidation = float(latest_snapshot.net_liquidation)

        # Calculate current total position value
        current_positions = self.db.query(
            func.sum(Position.market_value)
        ).filter(
            Position.snapshot_time >= datetime.utcnow() - timedelta(minutes=15)
        ).scalar() or 0

        # Estimate new position value
        if current_price and order_request.order_type == "MKT":
            order_value = order_request.quantity * current_price
        elif order_request.limit_price:
            order_value = order_request.quantity * float(order_request.limit_price)
        else:
            order_value = 0

        if order_request.action == "BUY":
            total_position_value = float(current_positions) + order_value
        else:
            total_position_value = float(current_positions)

        # Calculate leverage
        leverage = total_position_value / net_liquidation if net_liquidation > 0 else 0

        if leverage > self.config.max_leverage:
            return False, (
                f"Leverage {leverage:.2f}x exceeds limit "
                f"of {self.config.max_leverage:.2f}x"
            )

        # Warning if approaching limit (90% of limit)
        if leverage > (self.config.max_leverage * 0.9):
            return True, (
                f"Warning: Leverage {leverage:.2f}x approaching limit "
                f"of {self.config.max_leverage:.2f}x"
            )

        return True, None

    def _check_order_rate(self) -> Tuple[bool, Optional[str]]:
        """
        Check if order rate is within limits.

        Prevents excessive order submission that could violate IBKR rate limits.

        Returns:
            Tuple of (is_ok, reason)
        """
        # Check orders in last minute
        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)

        recent_orders = self.db.query(func.count(Order.id)).filter(
            Order.created_at >= one_minute_ago
        ).scalar()

        # IBKR has a 50 messages/second limit, we'll be conservative
        # and limit to 30 orders per minute
        max_orders_per_minute = 30

        if recent_orders >= max_orders_per_minute:
            return False, (
                f"Order rate limit exceeded: {recent_orders} orders in last minute "
                f"(limit: {max_orders_per_minute})"
            )

        return True, None

    def _get_default_limits(self) -> RiskLimits:
        """
        Get default risk limits from configuration.

        Returns:
            RiskLimits: Default risk limit configuration
        """
        return RiskLimits(
            max_order_value=50000.0,  # $50k per order
            max_position_value=100000.0,  # $100k per position
            max_daily_loss=5000.0,  # $5k daily loss limit
            max_leverage=2.0,  # 2x leverage
            allowed_symbols=None,  # No whitelist by default
            blocked_symbols=None  # No blacklist by default
        )

    def update_config(self, config: RiskLimits) -> None:
        """
        Update risk limit configuration.

        Args:
            config: New risk limit configuration
        """
        self.config = config
        logger.info(
            "risk_limits_updated",
            max_order_value=config.max_order_value,
            max_position_value=config.max_position_value,
            max_daily_loss=config.max_daily_loss
        )
