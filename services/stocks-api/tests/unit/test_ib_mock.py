"""
Unit tests for Mock IBKR Client.

Tests the MockIBKRClient to ensure it properly simulates IBKR behavior
for testing purposes.
"""
import pytest
from ib_insync import Stock, LimitOrder, MarketOrder

from app.ib_mock import MockIBKRClient
from app.utils.exceptions import IBKRConnectionError, IBKROrderError


@pytest.fixture
def mock_client():
    """Create a MockIBKRClient instance for testing."""
    return MockIBKRClient(
        host="mock-gateway",
        port=4003,
        client_id=999,
        auto_connect=True,
        simulate_delays=False
    )


class TestMockIBKRClientInitialization:
    """Test mock IBKR client initialization."""

    def test_mock_client_initialization(self):
        """Test mock client initializes with correct parameters."""
        client = MockIBKRClient(
            host="test-mock",
            port=4003,
            client_id=100,
            container_name="test",
            auto_connect=False,
            simulate_delays=True
        )

        assert client.host == "test-mock"
        assert client.port == 4003
        assert client.client_id == 100
        assert client.container_name == "test"
        assert client.simulate_delays is True
        assert client.connected is False  # auto_connect=False

    def test_mock_client_auto_connect(self):
        """Test mock client with auto_connect enabled."""
        client = MockIBKRClient(auto_connect=True)

        assert client.connected is True

    def test_mock_client_default_state(self, mock_client):
        """Test mock client initializes with empty state."""
        assert mock_client._next_order_id == 1
        assert len(mock_client._trades) == 0
        assert len(mock_client._positions) == 0
        assert len(mock_client._fills) == 0
        assert len(mock_client._market_data_subscriptions) == 0


class TestMockIBKRClientConnection:
    """Test mock IBKR client connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test mock client connection always succeeds."""
        client = MockIBKRClient(auto_connect=False)

        result = await client.connect()

        assert result is True
        assert client.connected is True

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_client):
        """Test mock client disconnection."""
        assert mock_client.connected is True

        await mock_client.disconnect()

        assert mock_client.connected is False

    def test_is_connected(self, mock_client):
        """Test is_connected returns correct status."""
        assert mock_client.is_connected() is True

        mock_client.connected = False
        assert mock_client.is_connected() is False


class TestMockIBKRClientOrders:
    """Test mock IBKR client order operations."""

    @pytest.mark.asyncio
    async def test_place_order_success(self, mock_client):
        """Test successful mock order placement."""
        contract = Stock("AAPL", "SMART", "USD")
        order = LimitOrder("BUY", 100, 150.0)

        trade = await mock_client.place_order(contract, order)

        assert trade is not None
        assert trade.order.orderId == 1
        assert trade.order.totalQuantity == 100
        assert trade.contract.symbol == "AAPL"
        assert trade.orderStatus.status == "Filled"  # Mock auto-fills

    @pytest.mark.asyncio
    async def test_place_multiple_orders(self, mock_client):
        """Test placing multiple mock orders."""
        contract1 = Stock("AAPL", "SMART", "USD")
        order1 = LimitOrder("BUY", 100, 150.0)

        contract2 = Stock("MSFT", "SMART", "USD")
        order2 = MarketOrder("SELL", 50)

        trade1 = await mock_client.place_order(contract1, order1)
        trade2 = await mock_client.place_order(contract2, order2)

        assert trade1.order.orderId == 1
        assert trade2.order.orderId == 2
        assert len(mock_client._trades) == 2

    @pytest.mark.asyncio
    async def test_place_order_not_connected(self, mock_client):
        """Test order placement when not connected."""
        mock_client.connected = False

        contract = Stock("AAPL", "SMART", "USD")
        order = LimitOrder("BUY", 100, 150.0)

        with pytest.raises(IBKRConnectionError) as exc_info:
            await mock_client.place_order(contract, order)

        assert "not connected" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_place_order_invalid_quantity(self, mock_client):
        """Test order placement with invalid quantity."""
        contract = Stock("AAPL", "SMART", "USD")
        order = LimitOrder("BUY", 0, 150.0)  # Invalid quantity

        with pytest.raises(IBKROrderError) as exc_info:
            await mock_client.place_order(contract, order)

        assert "quantity must be positive" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, mock_client):
        """Test successful mock order cancellation."""
        contract = Stock("AAPL", "SMART", "USD")
        order = LimitOrder("BUY", 100, 150.0)

        trade = await mock_client.place_order(contract, order)
        result = await mock_client.cancel_order(trade.order)

        assert result is True
        assert trade.orderStatus.status == "Cancelled"

    @pytest.mark.asyncio
    async def test_cancel_order_not_found(self, mock_client):
        """Test canceling non-existent order."""
        order = LimitOrder("BUY", 100, 150.0)
        order.orderId = 999  # Non-existent order ID

        with pytest.raises(IBKROrderError) as exc_info:
            await mock_client.cancel_order(order)

        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_cancel_order_not_connected(self, mock_client):
        """Test cancel order when not connected."""
        mock_client.connected = False

        order = LimitOrder("BUY", 100, 150.0)
        order.orderId = 1

        with pytest.raises(IBKRConnectionError):
            await mock_client.cancel_order(order)


class TestMockIBKRClientPositions:
    """Test mock IBKR client position operations."""

    @pytest.mark.asyncio
    async def test_get_positions_empty(self, mock_client):
        """Test getting positions when none exist."""
        positions = await mock_client.get_positions()

        assert isinstance(positions, list)
        assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_get_positions_with_data(self, mock_client):
        """Test getting positions with mock data."""
        from unittest.mock import Mock

        mock_positions = [Mock(), Mock()]
        mock_client.set_positions(mock_positions)

        positions = await mock_client.get_positions()

        assert positions == mock_positions
        assert len(positions) == 2

    @pytest.mark.asyncio
    async def test_get_positions_not_connected(self, mock_client):
        """Test get positions when not connected."""
        mock_client.connected = False

        with pytest.raises(IBKRConnectionError):
            await mock_client.get_positions()

    @pytest.mark.asyncio
    async def test_get_portfolio_items(self, mock_client):
        """Test getting portfolio items."""
        from unittest.mock import Mock

        mock_items = [Mock(), Mock(), Mock()]
        mock_client.set_portfolio_items(mock_items)

        items = await mock_client.get_portfolio_items()

        assert items == mock_items
        assert len(items) == 3


class TestMockIBKRClientAccount:
    """Test mock IBKR client account operations."""

    @pytest.mark.asyncio
    async def test_get_account_summary(self, mock_client):
        """Test getting mock account summary."""
        summary = await mock_client.get_account_summary()

        assert isinstance(summary, dict)
        assert "NetLiquidation_USD" in summary
        assert "TotalCashValue_USD" in summary
        assert "BuyingPower_USD" in summary
        assert float(summary["NetLiquidation_USD"]) > 0

    @pytest.mark.asyncio
    async def test_set_custom_account_summary(self, mock_client):
        """Test setting custom account summary."""
        custom_summary = {
            "NetLiquidation_USD": "200000.00",
            "CustomField": "CustomValue"
        }
        mock_client.set_account_summary(custom_summary)

        summary = await mock_client.get_account_summary()

        assert summary == custom_summary
        assert summary["NetLiquidation_USD"] == "200000.00"


class TestMockIBKRClientMarketData:
    """Test mock IBKR client market data operations."""

    @pytest.mark.asyncio
    async def test_request_market_data(self, mock_client):
        """Test requesting mock market data."""
        contract = Stock("AAPL", "SMART", "USD")
        contract.conId = 12345

        result = await mock_client.request_market_data(contract)

        assert result is True
        assert 12345 in mock_client._market_data_subscriptions

    @pytest.mark.asyncio
    async def test_cancel_market_data(self, mock_client):
        """Test canceling mock market data."""
        contract = Stock("AAPL", "SMART", "USD")
        contract.conId = 12345

        await mock_client.request_market_data(contract)
        assert 12345 in mock_client._market_data_subscriptions

        result = await mock_client.cancel_market_data(contract)

        assert result is True
        assert 12345 not in mock_client._market_data_subscriptions


class TestMockIBKRClientTrades:
    """Test mock IBKR client trade operations."""

    @pytest.mark.asyncio
    async def test_get_open_orders_empty(self, mock_client):
        """Test getting open orders when none exist."""
        orders = await mock_client.get_open_orders()

        assert isinstance(orders, list)
        assert len(orders) == 0

    @pytest.mark.asyncio
    async def test_get_open_orders_with_orders(self, mock_client):
        """Test getting open orders after placing orders."""
        # Place an order but cancel it before fill completes
        contract = Stock("AAPL", "SMART", "USD")
        order = LimitOrder("BUY", 100, 150.0)

        # Place order - it will auto-fill in mock
        await mock_client.place_order(contract, order)

        # Since mock auto-fills, open orders will be empty
        orders = await mock_client.get_open_orders()

        # All orders are filled in mock, so no open orders
        assert len(orders) == 0

    @pytest.mark.asyncio
    async def test_get_fills(self, mock_client):
        """Test getting fills after orders are filled."""
        contract = Stock("AAPL", "SMART", "USD")
        order = LimitOrder("BUY", 100, 150.0)

        await mock_client.place_order(contract, order)

        fills = await mock_client.get_fills()

        assert len(fills) >= 1
        assert fills[0].execution.shares == 100


class TestMockIBKRClientHelpers:
    """Test mock IBKR client helper methods."""

    def test_simulate_connection_failure(self, mock_client):
        """Test simulating connection failure."""
        assert mock_client.connected is True

        mock_client.simulate_connection_failure()

        assert mock_client.connected is False

    @pytest.mark.asyncio
    async def test_get_placed_orders(self, mock_client):
        """Test getting all placed orders."""
        contract1 = Stock("AAPL", "SMART", "USD")
        order1 = LimitOrder("BUY", 100, 150.0)

        contract2 = Stock("MSFT", "SMART", "USD")
        order2 = MarketOrder("SELL", 50)

        await mock_client.place_order(contract1, order1)
        await mock_client.place_order(contract2, order2)

        placed_orders = mock_client.get_placed_orders()

        assert len(placed_orders) == 2
        assert placed_orders[0].order.orderId == 1
        assert placed_orders[1].order.orderId == 2

    def test_clear_orders(self, mock_client):
        """Test clearing all orders."""
        # Manually add some trades
        from unittest.mock import Mock
        mock_client._trades[1] = Mock()
        mock_client._trades[2] = Mock()
        mock_client._fills = [Mock(), Mock()]
        mock_client._next_order_id = 10

        mock_client.clear_orders()

        assert len(mock_client._trades) == 0
        assert len(mock_client._fills) == 0
        assert mock_client._next_order_id == 1

    def test_get_mock_price_consistency(self, mock_client):
        """Test mock price generation is consistent for same symbol."""
        contract = Stock("AAPL", "SMART", "USD")

        price1 = mock_client._get_mock_price(contract)
        price2 = mock_client._get_mock_price(contract)

        # Prices should be in a reasonable range (with small variation)
        assert 170.0 < price1 < 180.0
        assert 170.0 < price2 < 180.0

    def test_get_mock_price_different_symbols(self, mock_client):
        """Test mock prices differ by symbol."""
        contract_aapl = Stock("AAPL", "SMART", "USD")
        contract_msft = Stock("MSFT", "SMART", "USD")

        price_aapl = mock_client._get_mock_price(contract_aapl)
        price_msft = mock_client._get_mock_price(contract_msft)

        # Prices should be significantly different
        assert abs(price_aapl - price_msft) > 100.0


class TestMockIBKRClientIntegration:
    """Integration tests for mock IBKR client workflows."""

    @pytest.mark.asyncio
    async def test_complete_order_workflow(self, mock_client):
        """Test complete order lifecycle."""
        # Connect
        await mock_client.connect()
        assert mock_client.is_connected()

        # Place order
        contract = Stock("AAPL", "SMART", "USD")
        order = LimitOrder("BUY", 100, 150.0)
        trade = await mock_client.place_order(contract, order)

        assert trade.order.orderId == 1
        assert trade.orderStatus.status == "Filled"

        # Get fills
        fills = await mock_client.get_fills()
        assert len(fills) == 1
        assert fills[0].execution.orderId == 1

        # Disconnect
        await mock_client.disconnect()
        assert not mock_client.is_connected()

    @pytest.mark.asyncio
    async def test_multiple_orders_workflow(self, mock_client):
        """Test placing multiple orders."""
        contracts = [
            Stock("AAPL", "SMART", "USD"),
            Stock("MSFT", "SMART", "USD"),
            Stock("GOOGL", "SMART", "USD"),
        ]

        for i, contract in enumerate(contracts):
            order = LimitOrder("BUY", 100 * (i + 1), 150.0)
            trade = await mock_client.place_order(contract, order)
            assert trade.order.orderId == i + 1

        placed_orders = mock_client.get_placed_orders()
        assert len(placed_orders) == 3
