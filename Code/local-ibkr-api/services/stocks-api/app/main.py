"""Main FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import structlog
from app.services.threaded_monitor import ThreadedConditionalMonitor
from app.config import get_settings
from app.routers import health, orders, positions, accounts, bulk_orders, conditional_orders
from app.utils.redis_client import redis_client
from app.utils.ib_dependencies import startup_ib_client, shutdown_ib_client

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)

settings = get_settings()
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("application_starting", environment=settings.ENVIRONMENT)
    # Connect to Redis
    try:
        await redis_client.connect()
    except Exception as e:
        logger.error("redis_startup_failed", error=str(e))
    # Initialize IB client
    try:
        await startup_ib_client()
    except Exception as e:
        logger.error("ib_client_startup_failed", error=str(e))
    yield
    # Shutdown
    logger.info("application_shutting_down")
    try:
        await redis_client.disconnect()
    except Exception as e:
        logger.error("redis_shutdown_failed", error=str(e))
    try:
        await shutdown_ib_client()
    except Exception as e:
        logger.error("ib_client_shutdown_failed", error=str(e))

app = FastAPI(
    title="IBKR Local API",
    description="Local IBKR API Integration for Paper Trading",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(orders.router)
app.include_router(bulk_orders.router)
app.include_router(conditional_orders.router)
app.include_router(positions.router)
app.include_router(accounts.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "status": "ok",
        "message": "IBKR Local API",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
        "endpoints": {
            "health": "/health",
            "orders": "/orders",
            "positions": "/positions",
            "accounts": "/accounts/summary",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)





# Algo Orders Router
from app.routers import algo_orders  # TEMPORARILY DISABLED
app.include_router(algo_orders.router)  # TEMPORARILY DISABLED
