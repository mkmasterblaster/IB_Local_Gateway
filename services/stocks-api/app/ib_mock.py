"""
Mock IBKR Client - Fake implementation for testing without live IB Gateway.

This mock client provides deterministic responses and allows testing of
trading logic without requiring a connection to Interactive Brokers.
"""
import asyncio
from typing import List, Any, Optional
from datetime import datetime
import random
import structlog
from sqlalchemy import create_engine, text
from app.config import get_settings

from ib_insync import (
    Contract,
    Order,
    Trade,
    Fill,
    Position,
    PortfolioItem,
    OrderStatus,
    Execution,
    CommissionReport
)

from app.utils.exceptions import (
    IBKRConnectionError,
    IBKROrderError,
    IBKRMarketDataError
)

logger = structlog.get_logger(__name__)


class MockIBKRClient:
    """
    Mock IBKR client for testing.

    Provides fake but realistic responses to IBKR operations without
    requiring actual IB Gateway connection.
    """

    def __init__(
        self,
        host: str = "mock-gateway",
        port: int = 4003,
        client_id: int = 1101,
        container_name: str = "mock",
        auto_connect: bool = True,
        simulate_delays: bool = False
    ):
        """
        Initialize mock IBKR client.

        Args:
            host: Fake hostname (for compatibility)
            port: Fake port (for compatibility)
            client_id: Fake client ID
            container_name: Container identifier for metrics
            auto_connect: Automatically "connect" on init
            simulate_delays: Add realistic delays to operations
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.container_name = container_name
        self.simulate_delays = simulate_delays

        self.connected = auto_connect
        self._next_order_id = self._get_next_order_id_from_db()
        self._trades: dict[int, Trade] = {}
        self._positions: List[Position] = []
        self._portfolio_items: List[PortfolioItem] = []
        self._fills: List[Fill] = []
        self._market_data_subscriptions: set[int] = set()
        self._account_summary = self._generate_mock_account_summary()

        logger.info(
            "mock_ibkr_client_initialized",
            host=host,
            port=port,
            auto_connect=auto_connect
        )

    async def connect(self) -> bool:
        """Mock connect - always succeeds."""
        if self.simulate_delays:
            await asyncio.sleep(0.1)  # Simulate connection delay

        self.connected = True
        logger.info("mock_ibkr_connected", host=self.host, port=self.port)
        return True

    async def disconnect(self) -> None:
        """Mock disconnect."""
        self.connected = False
        logger.info("mock_ibkr_disconnected")

    def is_connected(self) -> bool:
        """Check mock connection status."""
        return self.connected

    async def place_order(self, contract: Contract, order: Order) -> Trade:
        """
        Mock place order - creates a fake trade.

        Args:
            contract: The contract to trade
            order: The order specifications

        Returns:
            Trade: Mock trade object

        Raises:
            IBKRConnectionError: If not "connected"
            IBKROrderError: If order is invalid
        """
        if not self.connected:
            raise IBKRConnectionError("Mock client not connected")

        # Validate order
        if order.totalQuantity <= 0:
            raise IBKROrderError("Order quantity must be positive")

        if self.simulate_delays:
            await asyncio.sleep(0.05)  # Simulate order processing

        # Create mock trade
        order_id = self._next_order_id
        self._next_order_id += 1

        order.orderId = order_id
        order.permId = order_id * 100

        # Create order status
        status = OrderStatus(
            orderId=order_id,
            status="Submitted",
            filled=0.0,
            remaining=order.totalQuantity,
            avgFillPrice=0.0,
            permId=order.permId,
            parentId=0,
            lastFillPrice=0.0,
            clientId=self.client_id,
            whyHeld="",
            mktCapPrice=0.0
        )

        # Create trade
        trade = Trade(contract=contract, order=order, orderStatus=status, fills=[])
        self._trades[order_id] = trade

        logger.info(
            "mock_order_placed",
            order_id=order_id,
            symbol=contract.symbol,
            action=order.action,
            quantity=order.totalQuantity,
            order_type=order.orderType
        )

        # Simulate order being filled (for demo purposes)
        await self._simulate_fill(trade, contract)

        return trade

    async def cancel_order(self, order: Order) -> bool:
        """
        Mock cancel order.

        Args:
            order: The order to cancel

        Returns:
            bool: True if cancellation successful

        Raises:
            IBKRConnectionError: If not connected
            IBKROrderError: If order not found
        """
        if not self.connected:
            raise IBKRConnectionError("Mock client not connected")

        if order.orderId not in self._trades:
            raise IBKROrderError(f"Order {order.orderId} not found")

        trade = self._trades[order.orderId]
        trade.orderStatus.status = "Cancelled"

        logger.info("mock_order_canceled", order_id=order.orderId)
        return True

    async def get_positions(self, account: str = "") -> List[Position]:
        """Get mock positions."""
        if not self.connected:
            raise IBKRConnectionError("Mock client not connected")

        if self.simulate_delays:
            await asyncio.sleep(0.02)

        return self._positions

    async def get_portfolio_items(self, account: str = "") -> List[PortfolioItem]:
        """Get mock portfolio items."""
        if not self.connected:
            raise IBKRConnectionError("Mock client not connected")

        if self.simulate_delays:
            await asyncio.sleep(0.02)

        return self._portfolio_items

    async def get_account_summary(self, account: str = "") -> dict[str, Any]:
        """Get mock account summary."""
        if not self.connected:
            raise IBKRConnectionError("Mock client not connected")

        if self.simulate_delays:
            await asyncio.sleep(0.02)

        return self._account_summary.copy()

    async def request_market_data(self, contract: Contract) -> bool:
        """Mock market data request."""
        if not self.connected:
            raise IBKRConnectionError("Mock client not connected")

        self._market_data_subscriptions.add(contract.conId or hash(contract.symbol))

        logger.info("mock_market_data_requested", symbol=contract.symbol)
        return True

    async def cancel_market_data(self, contract: Contract) -> bool:
        """Mock cancel market data."""
        if not self.connected:
            raise IBKRConnectionError("Mock client not connected")

        self._market_data_subscriptions.discard(contract.conId or hash(contract.symbol))

        logger.info("mock_market_data_canceled", symbol=contract.symbol)
        return True

    async def get_open_orders(self) -> List[Trade]:
        """Get mock open orders."""
        if not self.connected:
            raise IBKRConnectionError("Mock client not connected")

        # Filter for open orders only
        open_trades = [
            trade for trade in self._trades.values()
            if trade.orderStatus.status in ("Submitted", "PreSubmitted", "PendingSubmit")
        ]

        logger.info("mock_open_orders_retrieved", count=len(open_trades))
        return open_trades

    async def get_fills(self) -> List[Fill]:
        """Get mock fills."""
        if not self.connected:
            raise IBKRConnectionError("Mock client not connected")

        return self._fills

    # Helper methods for testing

    def set_positions(self, positions: List[Position]) -> None:
        """Set mock positions (for testing)."""
        self._positions = positions

    def set_portfolio_items(self, items: List[PortfolioItem]) -> None:
        """Set mock portfolio items (for testing)."""
        self._portfolio_items = items

    def set_account_summary(self, summary: dict[str, Any]) -> None:
        """Set mock account summary (for testing)."""
        self._account_summary = summary

    def simulate_connection_failure(self) -> None:
        """Simulate connection failure (for testing)."""
        self.connected = False

    def get_placed_orders(self) -> List[Trade]:
        """Get all placed orders (for testing verification)."""
        return list(self._trades.values())

    def clear_orders(self) -> None:
        """Clear all orders (for testing cleanup)."""
        self._trades.clear()
        self._fills.clear()
        self._next_order_id = 1

    async def _simulate_fill(self, trade: Trade, contract: Contract) -> None:
        """
        Simulate order being filled (for demo/testing).

        Args:
            trade: The trade to fill
            contract: The contract being traded
        """
        # Simulate a short delay
        await asyncio.sleep(0.1 if self.simulate_delays else 0.0)

        # Create mock execution
        execution = Execution(
            execId=f"EXEC_{trade.order.orderId}",
            time=datetime.now().strftime("%Y%m%d %H:%M:%S"),
            acctNumber="DU123456",
            exchange="SMART",
            side=trade.order.action,
            shares=trade.order.totalQuantity,
            price=self._get_mock_price(contract),
            permId=trade.order.permId,
            clientId=self.client_id,
            orderId=trade.order.orderId,
            liquidation=0,
            cumQty=trade.order.totalQuantity,
            avgPrice=self._get_mock_price(contract),
            orderRef="",
            evRule="",
            evMultiplier=0.0,
            modelCode="",
            lastLiquidity=0
        )

        # Create mock commission
        commission = CommissionReport(
            execId=execution.execId,
            commission=1.0,
            currency="USD",
            realizedPNL=0.0,
            yield_=0.0,
            yieldRedemptionDate=0
        )

        # Create fill
        fill = Fill(contract=contract, execution=execution, commissionReport=commission, time=datetime.now())
        self._fills.append(fill)
        trade.fills.append(fill)

        # Update order status
        trade.orderStatus.status = "Filled"
        trade.orderStatus.filled = trade.order.totalQuantity
        trade.orderStatus.remaining = 0.0
        trade.orderStatus.avgFillPrice = execution.avgPrice

        logger.info(
            "mock_order_filled",
            order_id=trade.order.orderId,
            symbol=contract.symbol,
            quantity=trade.order.totalQuantity,
            price=execution.avgPrice
        )

    def _get_mock_price(self, contract: Contract) -> float:
        """
        Generate a realistic mock price for a contract.

        Args:
            contract: The contract

        Returns:
            float: Mock price
        """
        # Generate prices based on symbol (for consistency in tests)
        base_prices = {
            "AAPL": 175.0,
            "MSFT": 380.0,
            "GOOGL": 140.0,
            "AMZN": 155.0,
            "TSLA": 245.0,
            "SPY": 455.0,
            "QQQ": 385.0,
        }

        base_price = base_prices.get(contract.symbol, 100.0)
        # Add small random variation
        variation = random.uniform(-2.0, 2.0)
        return round(base_price + variation, 2)

    def _get_next_order_id_from_db(self) -> int:
        """Get the next available order_id from database."""
        try:
            settings = get_settings()
            engine = create_engine(settings.DATABASE_URL)
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COALESCE(MAX(order_id), 0) + 1 FROM orders"))
                next_id = result.scalar()
                logger.info("mock_order_id_initialized", next_id=next_id)
                return next_id
        except Exception as e:
            logger.warning("failed_to_get_order_id_from_db", error=str(e))
            return 1

    def _generate_mock_account_summary(self) -> dict[str, Any]:
        """Generate realistic mock account summary."""
        return {
            "NetLiquidation_USD": "100000.00",
            "TotalCashValue_USD": "50000.00",
            "SettledCash_USD": "50000.00",
            "BuyingPower_USD": "100000.00",
            "GrossPositionValue_USD": "50000.00",
            "UnrealizedPnL_USD": "2500.00",
            "RealizedPnL_USD": "1200.00",
            "AvailableFunds_USD": "50000.00",
            "ExcessLiquidity_USD": "50000.00",
            "Cushion": "0.50",
            "FullInitMarginReq_USD": "50000.00",
            "FullMaintMarginReq_USD": "45000.00",
            "DayTradesRemaining": "3",
        }
