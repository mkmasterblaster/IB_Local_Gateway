"""
Unit tests for IBKR Client.

Tests the IBKRClient wrapper including connection management,
error handling, and retry logic.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from ib_insync import IB, Contract, Order, Trade, OrderStatus, Stock, LimitOrder
import asyncio

from app.ib_client import IBKRClient
from app.utils.exceptions import IBKRConnectionError, IBKROrderError


@pytest.fixture
def mock_ib():
    """Create a mock IB instance."""
    mock = Mock(spec=IB)
    mock.isConnected.return_value = False
    mock.connectAsync = AsyncMock(return_value=None)
    mock.disconnect = Mock()
    mock.placeOrder = Mock()
    mock.cancelOrder = Mock()
    mock.positions = Mock(return_value=[])
    mock.portfolio = Mock(return_value=[])
    mock.accountValues = Mock(return_value=[])
    mock.reqMktData = Mock()
    mock.cancelMktData = Mock()
    mock.openTrades = Mock(return_value=[])
    mock.fills = Mock(return_value=[])
    mock.sleep = AsyncMock()
    return mock


@pytest.fixture
def ib_client():
    """Create an IBKRClient instance for testing."""
    return IBKRClient(
        host="test-gateway",
        port=4003,
        client_id=1,
        container_name="test",
        max_retries=2,
        retry_delay=0.1
    )


class TestIBKRClientInitialization:
    """Test IBKR client initialization."""

    def test_client_initialization(self):
        """Test client initializes with correct parameters."""
        client = IBKRClient(
            host="localhost",
            port=4003,
            client_id=5,
            container_name="test",
            max_retries=3,
            retry_delay=2.0
        )

        assert client.host == "localhost"
        assert client.port == 4003
        assert client.client_id == 5
        assert client.container_name == "test"
        assert client.max_retries == 3
        assert client.retry_delay == 2.0
        assert client.ib is None
        assert client.connected is False

    def test_client_default_values(self):
        """Test client uses default values."""
        client = IBKRClient()

        assert client.host == "stocks-ib-gateway"
        assert client.port == 4003
        assert client.client_id == 1
        assert client.max_retries == 3
        assert client.retry_delay == 2.0


class TestIBKRClientConnection:
    """Test IBKR client connection management."""

    @pytest.mark.asyncio
    async def test_successful_connection(self, ib_client, mock_ib):
        """Test successful connection to IB Gateway."""
        mock_ib.isConnected.return_value = True
        ib_client.ib = mock_ib

        result = await ib_client.connect()

        assert result is True
        assert ib_client.connected is True
        mock_ib.connectAsync.assert_called_once()

    @pytest.mark.asyncio
    async def test_already_connected(self, ib_client, mock_ib):
        """Test connecting when already connected."""
        mock_ib.isConnected.return_value = True
        ib_client.ib = mock_ib
        ib_client.connected = True

        result = await ib_client.connect()

        assert result is True
        # Should not attempt new connection
        mock_ib.connectAsync.assert_not_called()

    @pytest.mark.asyncio
    async def test_connection_with_retry(self, ib_client):
        """Test connection retry logic on failure."""
        with patch.object(IB, 'connectAsync', new_callable=AsyncMock) as mock_connect:
            # First attempt fails, second succeeds
            mock_connect.side_effect = [
                ConnectionRefusedError("Connection refused"),
                None
            ]

            mock_ib = Mock(spec=IB)
            mock_ib.isConnected.side_effect = [False, True]
            mock_ib.connectAsync = mock_connect
            mock_ib.errorEvent = Mock()
            mock_ib.disconnectedEvent = Mock()

            ib_client.ib = mock_ib

            result = await ib_client.connect()

            assert result is True
            assert mock_connect.call_count == 2

    @pytest.mark.asyncio
    async def test_connection_max_retries_exceeded(self, ib_client):
        """Test connection failure after max retries."""
        with patch.object(IB, 'connectAsync', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError("Connection refused")

            mock_ib = Mock(spec=IB)
            mock_ib.isConnected.return_value = False
            mock_ib.connectAsync = mock_connect

            ib_client.ib = mock_ib

            with pytest.raises(IBKRConnectionError) as exc_info:
                await ib_client.connect()

            assert "Failed to connect" in str(exc_info.value)
            assert mock_connect.call_count == ib_client.max_retries

    @pytest.mark.asyncio
    async def test_disconnect(self, ib_client, mock_ib):
        """Test disconnection from IB Gateway."""
        mock_ib.isConnected.return_value = True
        ib_client.ib = mock_ib
        ib_client.connected = True

        await ib_client.disconnect()

        assert ib_client.connected is False
        mock_ib.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, ib_client):
        """Test disconnect when not connected."""
        ib_client.ib = None

        # Should not raise error
        await ib_client.disconnect()

    def test_is_connected_true(self, ib_client, mock_ib):
        """Test is_connected returns True when connected."""
        mock_ib.isConnected.return_value = True
        ib_client.ib = mock_ib

        assert ib_client.is_connected() is True
        assert ib_client.connected is True

    def test_is_connected_false(self, ib_client, mock_ib):
        """Test is_connected returns False when not connected."""
        mock_ib.isConnected.return_value = False
        ib_client.ib = mock_ib

        assert ib_client.is_connected() is False
        assert ib_client.connected is False

    def test_is_connected_no_ib_instance(self, ib_client):
        """Test is_connected returns False when IB instance is None."""
        ib_client.ib = None

        assert ib_client.is_connected() is False


class TestIBKRClientOrders:
    """Test IBKR client order operations."""

    @pytest.mark.asyncio
    async def test_place_order_success(self, ib_client, mock_ib):
        """Test successful order placement."""
        mock_ib.isConnected.return_value = True
        ib_client.ib = mock_ib
        ib_client.connected = True

        # Create test contract and order
        contract = Stock("AAPL", "SMART", "USD")
        order = LimitOrder("BUY", 100, 150.0)

        # Create mock trade
        mock_trade = Trade(
            contract=contract,
            order=order,
            orderStatus=OrderStatus(status="Submitted"),
            fills=[]
        )
        mock_ib.placeOrder.return_value = mock_trade

        result = await ib_client.place_order(contract, order)

        assert result == mock_trade
        mock_ib.placeOrder.assert_called_once_with(contract, order)
        mock_ib.sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_place_order_not_connected(self, ib_client):
        """Test order placement when not connected."""
        ib_client.connected = False

        contract = Stock("AAPL", "SMART", "USD")
        order = LimitOrder("BUY", 100, 150.0)

        with pytest.raises(IBKRConnectionError) as exc_info:
            await ib_client.place_order(contract, order)

        assert "Not connected" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_place_order_error(self, ib_client, mock_ib):
        """Test order placement error handling."""
        mock_ib.isConnected.return_value = True
        mock_ib.placeOrder.side_effect = Exception("Order rejected")
        ib_client.ib = mock_ib
        ib_client.connected = True

        contract = Stock("AAPL", "SMART", "USD")
        order = LimitOrder("BUY", 100, 150.0)

        with pytest.raises(IBKROrderError) as exc_info:
            await ib_client.place_order(contract, order)

        assert "Order placement failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancel_order_success(self, ib_client, mock_ib):
        """Test successful order cancellation."""
        mock_ib.isConnected.return_value = True
        ib_client.ib = mock_ib
        ib_client.connected = True

        order = Order()
        order.orderId = 123

        result = await ib_client.cancel_order(order)

        assert result is True
        mock_ib.cancelOrder.assert_called_once_with(order)

    @pytest.mark.asyncio
    async def test_cancel_order_not_connected(self, ib_client):
        """Test order cancellation when not connected."""
        ib_client.connected = False

        order = Order()
        order.orderId = 123

        with pytest.raises(IBKRConnectionError):
            await ib_client.cancel_order(order)


class TestIBKRClientPositions:
    """Test IBKR client position operations."""

    @pytest.mark.asyncio
    async def test_get_positions_success(self, ib_client, mock_ib):
        """Test successful retrieval of positions."""
        mock_ib.isConnected.return_value = True
        mock_positions = [Mock(), Mock()]
        mock_ib.positions.return_value = mock_positions
        ib_client.ib = mock_ib
        ib_client.connected = True

        result = await ib_client.get_positions()

        assert result == mock_positions
        mock_ib.positions.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_positions_not_connected(self, ib_client):
        """Test get positions when not connected."""
        ib_client.connected = False

        with pytest.raises(IBKRConnectionError):
            await ib_client.get_positions()

    @pytest.mark.asyncio
    async def test_get_portfolio_items_success(self, ib_client, mock_ib):
        """Test successful retrieval of portfolio items."""
        mock_ib.isConnected.return_value = True
        mock_portfolio = [Mock(), Mock(), Mock()]
        mock_ib.portfolio.return_value = mock_portfolio
        ib_client.ib = mock_ib
        ib_client.connected = True

        result = await ib_client.get_portfolio_items()

        assert result == mock_portfolio
        mock_ib.portfolio.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_account_summary_success(self, ib_client, mock_ib):
        """Test successful retrieval of account summary."""
        mock_ib.isConnected.return_value = True

        # Create mock account values
        mock_av1 = Mock()
        mock_av1.tag = "NetLiquidation"
        mock_av1.value = "100000.00"
        mock_av1.currency = "USD"

        mock_av2 = Mock()
        mock_av2.tag = "TotalCashValue"
        mock_av2.value = "50000.00"
        mock_av2.currency = "USD"

        mock_ib.accountValues.return_value = [mock_av1, mock_av2]
        ib_client.ib = mock_ib
        ib_client.connected = True

        result = await ib_client.get_account_summary()

        assert isinstance(result, dict)
        assert "NetLiquidation_USD" in result
        assert "TotalCashValue_USD" in result
        assert result["NetLiquidation_USD"] == "100000.00"


class TestIBKRClientMarketData:
    """Test IBKR client market data operations."""

    @pytest.mark.asyncio
    async def test_request_market_data_success(self, ib_client, mock_ib):
        """Test successful market data request."""
        mock_ib.isConnected.return_value = True
        ib_client.ib = mock_ib
        ib_client.connected = True

        contract = Stock("AAPL", "SMART", "USD")
        contract.conId = 12345

        result = await ib_client.request_market_data(contract)

        assert result is True
        mock_ib.reqMktData.assert_called_once()
        assert 12345 in ib_client._market_data_subscriptions

    @pytest.mark.asyncio
    async def test_cancel_market_data_success(self, ib_client, mock_ib):
        """Test successful market data cancellation."""
        mock_ib.isConnected.return_value = True
        ib_client.ib = mock_ib
        ib_client.connected = True

        contract = Stock("AAPL", "SMART", "USD")
        contract.conId = 12345
        ib_client._market_data_subscriptions.add(12345)

        result = await ib_client.cancel_market_data(contract)

        assert result is True
        mock_ib.cancelMktData.assert_called_once()
        assert 12345 not in ib_client._market_data_subscriptions


class TestIBKRClientTrades:
    """Test IBKR client trade operations."""

    @pytest.mark.asyncio
    async def test_get_open_orders_success(self, ib_client, mock_ib):
        """Test successful retrieval of open orders."""
        mock_ib.isConnected.return_value = True
        mock_trades = [Mock(), Mock()]
        mock_ib.openTrades.return_value = mock_trades
        ib_client.ib = mock_ib
        ib_client.connected = True

        result = await ib_client.get_open_orders()

        assert result == mock_trades
        mock_ib.openTrades.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_fills_success(self, ib_client, mock_ib):
        """Test successful retrieval of fills."""
        mock_ib.isConnected.return_value = True
        mock_fills = [Mock(), Mock(), Mock()]
        mock_ib.fills.return_value = mock_fills
        ib_client.ib = mock_ib
        ib_client.connected = True

        result = await ib_client.get_fills()

        assert result == mock_fills
        mock_ib.fills.assert_called_once()


class TestIBKRClientEventHandlers:
    """Test IBKR client event handlers."""

    def test_on_error_handler(self, ib_client):
        """Test error event handler."""
        # Should not raise exception
        ib_client._on_error(
            reqId=1,
            errorCode=202,
            errorString="Order canceled",
            contract=None
        )

    def test_on_disconnected_handler(self, ib_client):
        """Test disconnected event handler."""
        ib_client.connected = True

        ib_client._on_disconnected()

        assert ib_client.connected is False
