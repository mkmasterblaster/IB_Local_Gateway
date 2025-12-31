"""
IBKR Client Protocol - Interface definition for IBKR client implementations.

This protocol allows for easy swapping between real and mock IBKR clients
during testing and development.
"""
from typing import Protocol, Optional, List, Any
from ib_insync import Contract, Order, Trade, Fill, Position, PortfolioItem


class IBKRClientProtocol(Protocol):
    """Protocol defining the interface for IBKR client implementations."""

    async def connect(self) -> bool:
        """
        Connect to IB Gateway.

        Returns:
            bool: True if connection successful, False otherwise
        """
        ...

    async def disconnect(self) -> None:
        """Disconnect from IB Gateway."""
        ...

    def is_connected(self) -> bool:
        """
        Check if currently connected to IB Gateway.

        Returns:
            bool: Connection status
        """
        ...

    async def place_order(self, contract: Contract, order: Order) -> Trade:
        """
        Place an order with IBKR.

        Args:
            contract: The contract to trade
            order: The order details

        Returns:
            Trade: The trade object representing the placed order

        Raises:
            IBKRConnectionError: If not connected to Gateway
            IBKROrderError: If order placement fails
        """
        ...

    async def cancel_order(self, order: Order) -> bool:
        """
        Cancel an existing order.

        Args:
            order: The order to cancel

        Returns:
            bool: True if cancellation successful

        Raises:
            IBKRConnectionError: If not connected to Gateway
            IBKROrderError: If cancellation fails
        """
        ...

    async def get_positions(self) -> List[Position]:
        """
        Get all current positions.

        Returns:
            List of Position objects

        Raises:
            IBKRConnectionError: If not connected to Gateway
        """
        ...

    async def get_portfolio_items(self) -> List[PortfolioItem]:
        """
        Get all portfolio items with P&L information.

        Returns:
            List of PortfolioItem objects

        Raises:
            IBKRConnectionError: If not connected to Gateway
        """
        ...

    async def get_account_summary(self, account: str = "") -> dict[str, Any]:
        """
        Get account summary information.

        Args:
            account: Account ID (empty string for default)

        Returns:
            Dictionary with account summary data

        Raises:
            IBKRConnectionError: If not connected to Gateway
        """
        ...

    async def request_market_data(self, contract: Contract) -> bool:
        """
        Request real-time market data for a contract.

        Args:
            contract: The contract to subscribe to

        Returns:
            bool: True if subscription successful

        Raises:
            IBKRConnectionError: If not connected to Gateway
            IBKRMarketDataError: If subscription fails
        """
        ...

    async def cancel_market_data(self, contract: Contract) -> bool:
        """
        Cancel market data subscription.

        Args:
            contract: The contract to unsubscribe from

        Returns:
            bool: True if cancellation successful

        Raises:
            IBKRConnectionError: If not connected to Gateway
        """
        ...

    async def get_open_orders(self) -> List[Trade]:
        """
        Get all open orders.

        Returns:
            List of Trade objects for open orders

        Raises:
            IBKRConnectionError: If not connected to Gateway
        """
        ...

    async def get_fills(self) -> List[Fill]:
        """
        Get all fills for the current session.

        Returns:
            List of Fill objects

        Raises:
            IBKRConnectionError: If not connected to Gateway
        """
        ...
