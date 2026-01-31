"""
IBKR Client Dependency Provider.

Provides dependency injection for IBKR client in FastAPI routes,
allowing easy swapping between real and mock implementations.
"""
from typing import AsyncGenerator, Optional
import structlog
import asyncio

from app.ib_client import IBKRClient
from app.ib_mock import MockIBKRClient
from app.ib_protocol import IBKRClientProtocol
from app.config import get_settings

logger = structlog.get_logger(__name__)

# Global client instance (singleton)
_ib_client_instance: IBKRClientProtocol | None = None
_ib_background_task: Optional[asyncio.Task] = None

def peek_ib_client_singleton() -> IBKRClientProtocol | None:
    """
    Return the existing IB client instance WITHOUT creating it.
    Safe for health/readiness checks.
    """
    return _ib_client_instance



def create_ib_client() -> IBKRClientProtocol:
    """
    Create IBKR client instance based on configuration.

    Returns:
        IBKRClientProtocol: Real or mock IBKR client

    The client type is determined by the ENVIRONMENT setting:
    - "testing": Uses MockIBKRClient
    - "development" or "production": Uses real IBKRClient
    """
    settings = get_settings()

    # Use mock client in testing environment
    if settings.ENVIRONMENT == "testing":
        logger.info("creating_mock_ibkr_client")
        return MockIBKRClient(
            host=settings.IB_GATEWAY_HOST,
            port=settings.IB_GATEWAY_PORT,
            client_id=settings.IB_CLIENT_ID,
            container_name=settings.CONTAINER_NAME or "stocks",
            auto_connect=True,
            simulate_delays=False
        )

    # Use real client for development and production
    logger.info("creating_real_ibkr_client", host=settings.IB_GATEWAY_HOST, port=settings.IB_GATEWAY_PORT)
    return IBKRClient(
        host=settings.IB_GATEWAY_HOST,
        port=settings.IB_GATEWAY_PORT,
        client_id=settings.IB_CLIENT_ID,
        container_name=settings.CONTAINER_NAME or "stocks",
        max_retries=3,
        retry_delay=2.0
    )


def get_ib_client_singleton() -> IBKRClientProtocol:
    """
    Get or create singleton IBKR client instance.

    Returns:
        IBKRClientProtocol: The IBKR client instance
    """
    global _ib_client_instance

    if _ib_client_instance is None:
        _ib_client_instance = create_ib_client()

    return _ib_client_instance


async def _ib_message_loop(client: IBKRClientProtocol) -> None:
    """
    Background task that continuously processes IB messages to keep connection alive.
    
    This is CRITICAL for maintaining the IB Gateway connection. Without this,
    the connection will disconnect immediately after connecting.
    """
    logger.info("ib_message_loop_started")
    
    while True:
        try:
            if hasattr(client, 'ib') and client.ib and client.ib.isConnected():
                # Process messages - this keeps the connection alive
                await asyncio.sleep(1)
            else:
                logger.warning("ib_not_connected_in_loop")
                await asyncio.sleep(5)  # Wait before checking again
        except asyncio.CancelledError:
            logger.info("ib_message_loop_cancelled")
            break
        except Exception as e:
            logger.error("ib_message_loop_error", error=str(e), error_type=type(e).__name__)
            await asyncio.sleep(5)  # Brief pause on error


async def startup_ib_client() -> None:
    """
    Initialize and connect IBKR client with persistent background task.
    """
    global _ib_background_task
    
    logger.info("starting_up_ib_client")

    try:
        # No need for util.startLoop() - FastAPI/uvloop already has an event loop
        client = get_ib_client_singleton()
        logger.info("got_client_singleton", client_type=type(client).__name__)
        
        # START BACKGROUND TASK FIRST (before connecting)
        _ib_background_task = asyncio.create_task(_ib_message_loop(client))
        logger.info("ib_background_task_started")
        
        # Give the task a moment to start
        await asyncio.sleep(0.1)
        
        # Then connect to IB Gateway
        if not client.is_connected():
            logger.info("client_not_connected_attempting_connection")
            success = await client.connect()
            logger.info("connection_attempt_completed", success=success, is_connected=client.is_connected())
            
            if client.is_connected():
                logger.info("ib_client_connected_on_startup")
            else:
                logger.error("connection_succeeded_but_not_connected")
        else:
            logger.info("client_already_connected")

    except Exception as e:
        logger.error("ib_client_startup_failed", error=str(e), error_type=type(e).__name__)


async def shutdown_ib_client() -> None:
    """
    Disconnect IBKR client and stop background task.
    """
    global _ib_background_task
    
    logger.info("shutting_down_ib_client")

    # Cancel background task first
    try:
        if _ib_background_task:
            _ib_background_task.cancel()

            try:
                await _ib_background_task
            except asyncio.CancelledError:
                pass
        
        client = get_ib_client_singleton()
        if client.is_connected():
            await client.disconnect()
            logger.info("ib_client_disconnected")
    except Exception as e:
        logger.error("ib_client_shutdown_failed", error=str(e))


async def get_ib_client() -> AsyncGenerator[IBKRClientProtocol, None]:
    """
    FastAPI dependency provider for IBKR client.

    Yields:
        IBKRClientProtocol: The IBKR client instance

    Usage in FastAPI routes:
        @router.get("/example")
        async def example(ib_client: IBKRClientProtocol = Depends(get_ib_client)):
            await ib_client.connect()
            # ... use client
    """
    client = get_ib_client_singleton()

    # Ensure client is connected
    if not client.is_connected():
        try:
            await client.connect()
        except Exception as e:
            logger.error("failed_to_connect_ib_client", error=str(e))
            # Continue anyway - routes can handle connection errors

    yield client


def reset_ib_client() -> None:
    """
    Reset the singleton IBKR client instance.

    Useful for testing when you need to recreate the client with
    different settings or state.
    """
    global _ib_client_instance
    _ib_client_instance = None
    logger.info("ib_client_reset")
