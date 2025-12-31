"""
IBKR Client Implementation - Wrapper around ib_insync for IB Gateway connectivity.

This module provides a robust client for interacting with Interactive Brokers Gateway,
including connection management, retry logic, and comprehensive error handling.
"""
import asyncio
from typing import Optional, List, Any
from datetime import datetime
import structlog

from ib_insync import IB, Contract, Order, Trade, Fill, Position, PortfolioItem, util
from prometheus_client import Gauge, Counter, Histogram

from app.utils.exceptions import (
    IBKRConnectionError,
    IBKROrderError,
    IBKRMarketDataError,
    IBKRAuthenticationError
)

logger = structlog.get_logger(__name__)

# Prometheus metrics
ib_connection_status = Gauge(
    'ib_connection_status',
    'IB Gateway connection status (1=connected, 0=disconnected)',
    ['container']
)
ib_orders_total = Counter(
    'ib_orders_total',
    'Total orders submitted to IBKR',
    ['order_type', 'action']
)
ib_order_errors_total = Counter(
    'ib_order_errors_total',
    'Total IBKR order errors',
    ['error_type']
)
ib_market_data_subscriptions = Gauge(
    'ib_market_data_subscriptions',
    'Active market data subscriptions'
)
ib_reconnect_attempts = Counter(
    'ib_reconnect_attempts_total',
    'Total reconnection attempts'
)
ib_operation_duration = Histogram(
    'ib_operation_duration_seconds',
    'Duration of IBKR operations',
    ['operation']
)


class IBKRClient:
    """
    IBKR Client wrapper providing robust connection management and trading operations.

    Attributes:
        host: IB Gateway hostname
        port: IB Gateway port
        client_id: Unique client ID for this connection
        ib: The ib_insync IB instance
        connected: Connection status flag
        container_name: Container identifier for metrics
    """

    def __init__(
        self,
        host: str = "stocks-ib-gateway",
        port: int = 4003,
        client_id: int = 1,
        container_name: str = "stocks",
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        """
        Initialize IBKR Client.

        Args:
            host: IB Gateway hostname
            port: IB Gateway port (4003 for paper, 4001 for live)
            client_id: Unique client ID (1-32)
            container_name: Container identifier for metrics labeling
            max_retries: Maximum connection retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.host = host
        self.port = port
        self.client_id = client_id
        self.container_name = container_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.ib: Optional[IB] = None
        self.connected = False
        self._market_data_subscriptions: set[int] = set()

        logger.info(
            "ibkr_client_initialized",
            host=host,
            port=port,
            client_id=client_id,
            container=container_name
        )

    async def connect(self) -> bool:
        """
        Connect to IB Gateway with retry logic using ib_insync's util.


        Returns:
            bool: True if connection successful

        Raises:
            IBKRConnectionError: If connection fails after all retries
            IBKRAuthenticationError: If authentication fails
        """
        if self.connected and self.ib and self.ib.isConnected():
            logger.info("ibkr_already_connected", host=self.host, port=self.port)
            return True

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "ibkr_connecting",
                    attempt=attempt,
                    max_retries=self.max_retries,
                    host=self.host,
                    port=self.port,
                    client_id=self.client_id
                )
                ib_reconnect_attempts.inc()

                # Create new IB instance if needed
                if self.ib is None:
                    self.ib = IB()

                # Attempt connection (longer timeout for paper account sync)
                await self.ib.connectAsync(
                    host=self.host,
                    port=self.port,
                    clientId=self.client_id,
                    timeout=60,  # Increased for initial sync
                    readonly=False  # Explicitly writable for paper trading
                )

		# Wait for IB Gateway handshake to complete
                #await asyncio.sleep(2) #Remove_This_It_Causes_Hangs

                await self.ib.waitOnUpdate(timeout=5)

                # Verify connection
                if self.ib.isConnected():
                    self.connected = True
                    ib_connection_status.labels(container=self.container_name).set(1)

                    # Set up event handlers
                    self.ib.errorEvent += self._on_error
                    self.ib.disconnectedEvent += self._on_disconnected

                    logger.info(
                        "ibkr_connected",
                        host=self.host,
                        port=self.port,
                        client_id=self.client_id,
                        attempt=attempt
                    )
                    return True

            except ConnectionRefusedError as e:
                logger.warning(
                    "ibkr_connection_refused",
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(e)
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
                else:
                    ib_connection_status.labels(container=self.container_name).set(0)
                    raise IBKRConnectionError(
                        f"Failed to connect to IB Gateway at {self.host}:{self.port} "
                        f"after {self.max_retries} attempts"
                    ) from e

            except Exception as e:
                logger.error(
                    "ibkr_connection_error",
                    attempt=attempt,
                    error=str(e),
                    error_type=type(e).__name__
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * attempt)
                else:
                    ib_connection_status.labels(container=self.container_name).set(0)
                    raise IBKRConnectionError(f"Connection failed: {str(e)}") from e

        return False

    async def disconnect(self) -> None:
        """Disconnect from IB Gateway gracefully."""
        if self.ib and self.ib.isConnected():
            try:
                logger.info("ibkr_disconnecting", host=self.host, port=self.port)
                self.ib.disconnect()
                self.connected = False
                ib_connection_status.labels(container=self.container_name).set(0)
                logger.info("ibkr_disconnected")
            except Exception as e:
                logger.error("ibkr_disconnect_error", error=str(e))
                raise IBKRConnectionError(f"Disconnect failed: {str(e)}") from e

    def is_connected(self) -> bool:
        """
        Check current connection status.

        Returns:
            bool: True if connected to IB Gateway
        """
        is_conn = self.ib is not None and self.ib.isConnected()
        self.connected = is_conn
        ib_connection_status.labels(container=self.container_name).set(1 if is_conn else 0)
        return is_conn

    @ib_operation_duration.labels(operation="place_order").time()
    async def place_order(self, contract: Contract, order: Order) -> Trade:
        """
        Place an order with IBKR.

        Args:
            contract: The contract to trade
            order: The order specifications

        Returns:
            Trade: The trade object

        Raises:
            IBKRConnectionError: If not connected
            IBKROrderError: If order placement fails
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            logger.info(
                "ibkr_placing_order",
                symbol=contract.symbol,
                sec_type=contract.secType,
                action=order.action,
                quantity=order.totalQuantity,
                order_type=order.orderType
            )

            trade = self.ib.placeOrder(contract, order)
            await self.ib.sleep(1)  # Allow order to be acknowledged

            # Update metrics
            ib_orders_total.labels(
                order_type=order.orderType,
                action=order.action
            ).inc()

            logger.info(
                "ibkr_order_placed",
                order_id=trade.order.orderId,
                symbol=contract.symbol,
                status=trade.orderStatus.status
            )

            return trade

        except Exception as e:
            ib_order_errors_total.labels(error_type=type(e).__name__).inc()
            logger.error(
                "ibkr_order_error",
                error=str(e),
                error_type=type(e).__name__,
                symbol=contract.symbol
            )
            raise IBKROrderError(f"Order placement failed: {str(e)}") from e

    @ib_operation_duration.labels(operation="cancel_order").time()
    async def cancel_order(self, order: Order) -> bool:
        """
        Cancel an existing order.

        Args:
            order: The order to cancel

        Returns:
            bool: True if cancellation successful

        Raises:
            IBKRConnectionError: If not connected
            IBKROrderError: If cancellation fails
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            logger.info("ibkr_canceling_order", order_id=order.orderId)
            self.ib.cancelOrder(order)
            await self.ib.sleep(1)  # Allow cancellation to process
            logger.info("ibkr_order_canceled", order_id=order.orderId)
            return True

        except Exception as e:
            logger.error("ibkr_cancel_error", order_id=order.orderId, error=str(e))
            raise IBKROrderError(f"Order cancellation failed: {str(e)}") from e

    @ib_operation_duration.labels(operation="get_positions").time()
    async def get_positions(self) -> List[Position]:
        """
        Get all current positions.

        Returns:
            List of Position objects

        Raises:
            IBKRConnectionError: If not connected
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            positions = self.ib.positions()
            logger.info("ibkr_positions_retrieved", count=len(positions))
            return positions

        except Exception as e:
            logger.error("ibkr_positions_error", error=str(e))
            raise IBKRConnectionError(f"Failed to get positions: {str(e)}") from e

    @ib_operation_duration.labels(operation="get_portfolio").time()
    async def get_portfolio_items(self) -> List[PortfolioItem]:
        """
        Get all portfolio items with P&L information.

        Returns:
            List of PortfolioItem objects

        Raises:
            IBKRConnectionError: If not connected
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            portfolio = self.ib.portfolio()
            logger.info("ibkr_portfolio_retrieved", count=len(portfolio))
            return portfolio

        except Exception as e:
            logger.error("ibkr_portfolio_error", error=str(e))
            raise IBKRConnectionError(f"Failed to get portfolio: {str(e)}") from e

    @ib_operation_duration.labels(operation="get_account_summary").time()
    async def get_account_summary(self, account: str = "") -> dict[str, Any]:
        """
        Get account summary information.

        Args:
            account: Account ID (empty for default)

        Returns:
            Dictionary with account summary data

        Raises:
            IBKRConnectionError: If not connected
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            account_values = self.ib.accountValues(account)

            # Convert to dictionary
            summary = {}
            for av in account_values:
                key = f"{av.tag}_{av.currency}" if av.currency else av.tag
                summary[key] = av.value

            logger.info("ibkr_account_summary_retrieved", account=account or "default")
            return summary

        except Exception as e:
            logger.error("ibkr_account_summary_error", error=str(e))
            raise IBKRConnectionError(f"Failed to get account summary: {str(e)}") from e

    @ib_operation_duration.labels(operation="request_market_data").time()
    async def request_market_data(self, contract: Contract) -> bool:
        """
        Request real-time market data for a contract.

        Args:
            contract: The contract to subscribe to

        Returns:
            bool: True if subscription successful

        Raises:
            IBKRConnectionError: If not connected
            IBKRMarketDataError: If subscription fails
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            self.ib.reqMktData(contract, "", False, False)
            self._market_data_subscriptions.add(contract.conId)
            ib_market_data_subscriptions.set(len(self._market_data_subscriptions))

            logger.info(
                "ibkr_market_data_requested",
                symbol=contract.symbol,
                con_id=contract.conId
            )
            return True

        except Exception as e:
            logger.error("ibkr_market_data_error", error=str(e), symbol=contract.symbol)
            raise IBKRMarketDataError(f"Market data request failed: {str(e)}") from e

    async def cancel_market_data(self, contract: Contract) -> bool:
        """
        Cancel market data subscription.

        Args:
            contract: The contract to unsubscribe from

        Returns:
            bool: True if cancellation successful

        Raises:
            IBKRConnectionError: If not connected
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            self.ib.cancelMktData(contract)
            self._market_data_subscriptions.discard(contract.conId)
            ib_market_data_subscriptions.set(len(self._market_data_subscriptions))

            logger.info(
                "ibkr_market_data_canceled",
                symbol=contract.symbol,
                con_id=contract.conId
            )
            return True

        except Exception as e:
            logger.error("ibkr_market_data_cancel_error", error=str(e))
            return False

    async def get_open_orders(self) -> List[Trade]:
        """
        Get all open orders.

        Returns:
            List of Trade objects for open orders

        Raises:
            IBKRConnectionError: If not connected
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            trades = self.ib.openTrades()
            logger.info("ibkr_open_orders_retrieved", count=len(trades))
            return trades

        except Exception as e:
            logger.error("ibkr_open_orders_error", error=str(e))
            raise IBKRConnectionError(f"Failed to get open orders: {str(e)}") from e

    async def get_fills(self) -> List[Fill]:
        """
        Get all fills for the current session.

        Returns:
            List of Fill objects

        Raises:
            IBKRConnectionError: If not connected
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            fills = self.ib.fills()
            logger.info("ibkr_fills_retrieved", count=len(fills))
            return fills

        except Exception as e:
            logger.error("ibkr_fills_error", error=str(e))
            raise IBKRConnectionError(f"Failed to get fills: {str(e)}") from e

    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract: Contract):
        """
        Handle IBKR error events.

        Args:
            reqId: Request ID
            errorCode: IBKR error code
            errorString: Error message
            contract: Contract related to error (if any)
        """
        logger.warning(
            "ibkr_error_event",
            req_id=reqId,
            error_code=errorCode,
            error_string=errorString,
            contract=contract.symbol if contract else None
        )

        # Track specific error types
        if errorCode >= 2100:  # System errors
            ib_order_errors_total.labels(error_type="system").inc()
        elif 100 <= errorCode < 200:  # Order related errors
            ib_order_errors_total.labels(error_type="order").inc()
        elif 300 <= errorCode < 400:  # Market data errors
            ib_order_errors_total.labels(error_type="market_data").inc()

    def _on_disconnected(self):
        """Handle disconnection events."""
        self.connected = False
        ib_connection_status.labels(container=self.container_name).set(0)
        logger.warning("ibkr_disconnected_event", host=self.host, port=self.port)
