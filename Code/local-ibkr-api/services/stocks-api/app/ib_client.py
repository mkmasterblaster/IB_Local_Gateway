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


    async def _force_disconnect_stale(self) -> bool:
        """
        Force disconnect any stale connection using our client ID.
        
        When you connect with the same client ID, IB Gateway will automatically
        disconnect the old connection. This cleans up test scripts and old sessions.
        
        Returns:
            bool: True if cleanup successful
        """
        try:
            logger.info(
                "force_disconnect_stale",
                client_id=self.client_id,
                host=self.host,
                port=self.port
            )
            
            # Create temporary IB instance
            temp_ib = IB()
            
            # Try to connect - this will kick off any existing connection with same ID
            try:
                await temp_ib.connectAsync(
                    host=self.host,
                    port=self.port,
                    clientId=self.client_id,
                    timeout=10
                )
                
                # Successfully connected - means we kicked off the old connection
                logger.info("stale_connection_disconnected", client_id=self.client_id)
                
                # Immediately disconnect this temporary connection
                temp_ib.disconnect()
                await asyncio.sleep(1)  # Brief pause for cleanup
                
                return True
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # If "already in use", the stale connection is stubborn
                if "already in use" in error_msg:
                    logger.warning(
                        "stale_connection_persistent",
                        client_id=self.client_id,
                        error=str(e)
                    )
                    return False
                
                # Connection refused means Gateway not ready yet
                if "refused" in error_msg:
                    logger.debug("gateway_not_ready", error=str(e))
                    return False
                    
                # Other errors
                logger.debug("stale_disconnect_error", error=str(e))
                return False
                
        except Exception as e:
            logger.error("force_disconnect_failed", error=str(e))
            return False


    async def connect(self) -> bool:
        """
        Connect to IB Gateway with retry logic and auto client ID selection.

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
                    self.ib.orderStatusEvent += self._on_order_status
                    self.ib.newOrderEvent += self._on_order_status
                    self.ib.fillEvent += self._on_fill

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
            await asyncio.sleep(1)  # Allow order to be acknowledged

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
    async def cancel_order(self, order_id: int) -> bool:
        """
        Cancel an existing order.

        Args:
            order_id: The IB order ID to cancel

        Returns:
            bool: True if cancellation successful

        Raises:
            IBKRConnectionError: If not connected
            IBKROrderError: If cancellation fails
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            logger.info("ibkr_canceling_order", order_id=order_id)
            
            # Get all trades (not just open ones)
            all_trades = self.ib.trades()
            trade_to_cancel = None
            
            for trade in all_trades:
                if trade.order.orderId == order_id:
                    trade_to_cancel = trade
                    break
            
            if not trade_to_cancel:
                logger.warning("order_not_found_in_trades", order_id=order_id)
                # Order might have already been cancelled or filled
                return True  # Return success anyway
            
            self.ib.cancelOrder(trade_to_cancel.order)
            logger.info("ibkr_order_canceled", order_id=order_id)
            return True

        except Exception as e:
            logger.error("ibkr_cancel_error", order_id=order_id, error=str(e))
            raise IBKROrderError(f"Order cancellation failed: {str(e)}") from e

    @ib_operation_duration.labels(operation="get_positions").time()
    async def get_positions(self, account: str = "") -> List[Position]:
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
    async def get_portfolio_items(self, account: str = "") -> List[PortfolioItem]:
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
            # Get account values - pass account only if provided
            if account:
                account_values = self.ib.accountValues(account)
            else:
                account_values = self.ib.accountValues()

            # Convert to dictionary with proper key mapping
            summary = {}
            for av in account_values:
                # Use tag as key, convert value to float if possible
                try:
                    summary[av.tag] = float(av.value)
                except (ValueError, TypeError):
                    summary[av.tag] = av.value

            logger.info(
                "ibkr_account_summary_retrieved",
                account=account or "default",
                keys_found=len(summary)
            )
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

    def _on_order_status(self, trade):
        """
        Handle order status updates from IB Gateway.
        
        Args:
            trade: Trade object with updated status
        """
        logger.info(
            "order_status_update",
            order_id=trade.order.orderId,
            status=trade.orderStatus.status,
            filled=trade.orderStatus.filled,
            remaining=trade.orderStatus.remaining,
            avg_fill_price=trade.orderStatus.avgFillPrice
        )
        
        # TODO: Update database here
        # For now, just log the status change

    def _on_fill(self, trade, fill):
        """
        Handle order fill events.
        
        Args:
            trade: Trade object with order info
            fill: Fill object with execution details
        """
        logger.info(
            "order_filled",
            order_id=trade.order.orderId,
            symbol=trade.contract.symbol,
            shares=fill.execution.shares,
            price=fill.execution.price,
            cumQty=fill.execution.cumQty,
            avgPrice=fill.execution.avgPrice
        )
        
        # TODO: Store fill in database

    @ib_operation_duration.labels(operation="place_bracket_order").time()
    async def place_bracket_order(
        self,
        contract: Contract,
        action: str,
        quantity: float,
        entry_type: str = "MKT",
        entry_price: float = None,
        profit_target: float = None,
        stop_loss: float = None
    ) -> tuple:
        """
        Place a bracket order (entry + profit + stop).

        Args:
            contract: The contract to trade
            action: BUY or SELL
            quantity: Number of shares
            entry_type: MKT or LMT
            entry_price: Entry limit price (if LMT)
            profit_target: Take profit price
            stop_loss: Stop loss price

        Returns:
            Tuple of (parent_trade, profit_trade, stop_trade)
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            from ib_insync import Order, LimitOrder, MarketOrder, StopOrder

            # Create parent order (entry)
            parent = Order()
            parent.orderId = self.ib.client.getReqId()
            parent.action = action
            parent.totalQuantity = quantity
            parent.transmit = False  # Don't send until children attached
            
            if entry_type == "LMT":
                parent.orderType = "LMT"
                parent.lmtPrice = entry_price
            else:
                parent.orderType = "MKT"

            # Child action is opposite of parent
            child_action = "SELL" if action == "BUY" else "BUY"

            # Create profit target order
            profit_order = Order()
            profit_order.orderId = self.ib.client.getReqId()
            profit_order.action = child_action
            profit_order.totalQuantity = quantity
            profit_order.orderType = "LMT"
            profit_order.lmtPrice = profit_target
            profit_order.parentId = parent.orderId
            profit_order.transmit = False

            # Create stop loss order
            stop_order = Order()
            stop_order.orderId = self.ib.client.getReqId()
            stop_order.action = child_action
            stop_order.totalQuantity = quantity
            stop_order.orderType = "STP"
            stop_order.auxPrice = stop_loss
            stop_order.parentId = parent.orderId
            stop_order.transmit = True  # Transmit all together

            logger.info(
                "placing_bracket_order",
                symbol=contract.symbol,
                action=action,
                quantity=quantity,
                entry_type=entry_type,
                entry_price=entry_price,
                profit_target=profit_target,
                stop_loss=stop_loss,
                parent_id=parent.orderId,
                profit_id=profit_order.orderId,
                stop_id=stop_order.orderId
            )

            # Place all three orders
            parent_trade = self.ib.placeOrder(contract, parent)
            profit_trade = self.ib.placeOrder(contract, profit_order)
            stop_trade = self.ib.placeOrder(contract, stop_order)

            # Update metrics
            ib_orders_total.labels(order_type="BRACKET", action=action).inc()

            logger.info(
                "bracket_order_placed",
                parent_id=parent.orderId,
                profit_id=profit_order.orderId,
                stop_id=stop_order.orderId
            )

            return (parent_trade, profit_trade, stop_trade)

        except Exception as e:
            ib_order_errors_total.labels(error_type=type(e).__name__).inc()
            logger.error("bracket_order_error", error=str(e), symbol=contract.symbol)
            raise IBKROrderError(f"Bracket order placement failed: {str(e)}") from e

    @ib_operation_duration.labels(operation="place_trailing_stop").time()
    async def place_trailing_stop(
        self,
        contract: Contract,
        action: str,
        quantity: float,
        trail_stop_price: float = None,
        trail_percent: float = None
    ) -> Trade:
        """
        Place a trailing stop order.

        Args:
            contract: The contract to trade
            action: BUY or SELL
            quantity: Number of shares
            trail_stop_price: Trailing amount in dollars (e.g., 5.00 = trails by $5)
            trail_percent: Trailing percentage (e.g., 2.5 = trails by 2.5%)

        Returns:
            Trade object from IB

        Raises:
            IBKRConnectionError: If not connected
            IBKROrderError: If order placement fails
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            from ib_insync import Order

            # Create trailing stop order
            order = Order()
            order.orderId = self.ib.client.getReqId()
            order.action = action
            order.totalQuantity = quantity
            order.orderType = "TRAIL"
            
            # Set trail amount ($ or %)
            if trail_stop_price:
                order.auxPrice = trail_stop_price  # Dollar amount
                trail_type = f"${trail_stop_price}"
            else:
                order.trailingPercent = trail_percent  # Percentage
                trail_type = f"{trail_percent}%"

            logger.info(
                "placing_trailing_stop",
                symbol=contract.symbol,
                action=action,
                quantity=quantity,
                trail_type=trail_type
            )

            # Place order
            trade = self.ib.placeOrder(contract, order)

            # Update metrics
            ib_orders_total.labels(order_type="TRAILING_STOP", action=action).inc()

            logger.info(
                "trailing_stop_placed",
                order_id=order.orderId,
                trail_type=trail_type
            )

            return trade

        except Exception as e:
            ib_order_errors_total.labels(error_type=type(e).__name__).inc()
            logger.error("trailing_stop_error", error=str(e), symbol=contract.symbol)
            raise IBKROrderError(f"Trailing stop placement failed: {str(e)}") from e

    @ib_operation_duration.labels(operation="modify_order").time()
    async def modify_order(
        self,
        order_id: int,
        quantity: int = None,
        limit_price: float = None,
        stop_price: float = None,
        trail_stop_price: float = None,
        trail_percent: float = None
    ) -> Trade:
        """
        Modify an existing order.

        Args:
            order_id: IB order ID to modify
            quantity: New quantity (optional)
            limit_price: New limit price (optional)
            stop_price: New stop price (optional)
            trail_stop_price: New trailing amount in $ (optional)
            trail_percent: New trailing percent (optional)

        Returns:
            Modified Trade object

        Raises:
            IBKRConnectionError: If not connected
            IBKROrderError: If modification fails
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            # Find the existing trade
            trades = self.ib.trades()
            target_trade = None
            
            for trade in trades:
                if trade.order.orderId == order_id:
                    target_trade = trade
                    break
            
            if not target_trade:
                logger.error("order_not_found_for_modification", order_id=order_id)
                raise IBKROrderError(f"Order {order_id} not found or already filled/cancelled")
            
            # Modify the order object
            modifications = {}
            
            if quantity is not None:
                target_trade.order.totalQuantity = quantity
                modifications['quantity'] = quantity
            
            if limit_price is not None:
                target_trade.order.lmtPrice = limit_price
                modifications['limit_price'] = limit_price
            
            if stop_price is not None:
                target_trade.order.auxPrice = stop_price
                modifications['stop_price'] = stop_price
            
            if trail_stop_price is not None:
                target_trade.order.auxPrice = trail_stop_price
                modifications['trail_stop_price'] = trail_stop_price
            
            if trail_percent is not None:
                target_trade.order.trailingPercent = trail_percent
                modifications['trail_percent'] = trail_percent
            
            logger.info(
                "modifying_order",
                order_id=order_id,
                modifications=modifications
            )

            # Submit the modified order (same order ID = modification)
            modified_trade = self.ib.placeOrder(target_trade.contract, target_trade.order)

            logger.info(
                "order_modified",
                order_id=order_id,
                modifications=modifications
            )

            return modified_trade

        except Exception as e:
            logger.error("order_modification_error", error=str(e), order_id=order_id)
            raise IBKROrderError(f"Order modification failed: {str(e)}") from e

    @ib_operation_duration.labels(operation="place_oco_order").time()
    async def place_oco_order(
        self,
        contract: Contract,
        quantity: float,
        order1_action: str,
        order1_type: str,
        order1_price: float,
        order2_action: str,
        order2_type: str,
        order2_price: float,
        time_in_force: str = "GTC"
    ) -> tuple:
        """
        Place OCO (One-Cancels-Other) orders.

        Args:
            contract: The contract to trade
            quantity: Number of shares for both orders
            order1_action: BUY or SELL for first order
            order1_type: LMT or STP for first order
            order1_price: Price for first order
            order2_action: BUY or SELL for second order
            order2_type: LMT or STP for second order
            order2_price: Price for second order
            time_in_force: DAY or GTC

        Returns:
            Tuple of (trade1, trade2, oca_group)
        """
        if not self.is_connected():
            raise IBKRConnectionError("Not connected to IB Gateway")

        try:
            from ib_insync import Order
            import time
            
            # Create unique OCA group ID
            oca_group = f"OCO_{int(time.time() * 1000)}"

            # Create first order
            order1 = Order()
            order1.orderId = self.ib.client.getReqId()
            order1.action = order1_action
            order1.totalQuantity = quantity
            order1.tif = time_in_force
            order1.ocaGroup = oca_group
            order1.ocaType = 1  # 1 = Cancel all remaining orders with block
            
            if order1_type == "LMT":
                order1.orderType = "LMT"
                order1.lmtPrice = order1_price
            else:  # STP
                order1.orderType = "STP"
                order1.auxPrice = order1_price

            # Create second order
            order2 = Order()
            order2.orderId = self.ib.client.getReqId()
            order2.action = order2_action
            order2.totalQuantity = quantity
            order2.tif = time_in_force
            order2.ocaGroup = oca_group
            order2.ocaType = 1
            
            if order2_type == "LMT":
                order2.orderType = "LMT"
                order2.lmtPrice = order2_price
            else:  # STP
                order2.orderType = "STP"
                order2.auxPrice = order2_price

            logger.info(
                "placing_oco_order",
                symbol=contract.symbol,
                oca_group=oca_group,
                order1_id=order1.orderId,
                order2_id=order2.orderId
            )

            # Place both orders
            trade1 = self.ib.placeOrder(contract, order1)
            trade2 = self.ib.placeOrder(contract, order2)

            # Update metrics
            ib_orders_total.labels(order_type="OCO", action="BOTH").inc()

            logger.info(
                "oco_orders_placed",
                oca_group=oca_group,
                order1_id=order1.orderId,
                order2_id=order2.orderId
            )

            return (trade1, trade2, oca_group)

        except Exception as e:
            ib_order_errors_total.labels(error_type=type(e).__name__).inc()
            logger.error("oco_order_error", error=str(e), symbol=contract.symbol)
            raise IBKROrderError(f"OCO order placement failed: {str(e)}") from e
