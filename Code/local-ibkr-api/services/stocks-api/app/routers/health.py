"""Health check endpoints."""
from fastapi import APIRouter
from typing import Dict, Any
import structlog
from app.utils.database import check_db_health
from app.utils.redis_client import redis_client
from app.utils.ib_dependencies import get_ib_client_singleton

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Overall system health check.
    
    Checks:
    - API service status
    - Database connectivity
    - Redis connectivity
    - IB Gateway connection (if applicable)
    """
    logger.info("health_check_started")
    
    # Check database
    db_healthy = await check_db_health()
    
    # Check Redis
    redis_healthy = await redis_client.ping()
    
    # Check IB Gateway
    try:
        ib_client = get_ib_client_singleton()
        ib_status = "connected" if ib_client.is_connected() else "disconnected"
    except Exception as e:
        logger.error("ib_health_check_failed", error=str(e))
        ib_status = "error"
    
    # Determine overall status
    overall_status = "healthy" if (db_healthy and redis_healthy) else "unhealthy"
    
    result = {
        "status": overall_status,
        "services": {
            "api": "running",
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy",
            "ib_gateway": ib_status
        }
    }
    
    logger.info(
        "health_check_completed",
        overall_status=overall_status,
        database="healthy" if db_healthy else "unhealthy",
        redis="healthy" if redis_healthy else "unhealthy",
        ib_gateway=ib_status
    )
    
    return result


@router.get("/health/live")
async def liveness_probe() -> Dict[str, str]:
    """
    Kubernetes liveness probe.
    Returns OK if the service is running.
    """
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_probe() -> Dict[str, Any]:
    """
    Kubernetes readiness probe.
    Returns OK if the service is ready to accept traffic.
    """
    db_healthy = await check_db_health()
    redis_healthy = await redis_client.ping()
    
    ready = db_healthy and redis_healthy
    
    return {
        "status": "ready" if ready else "not_ready",
        "checks": {
            "database": db_healthy,
            "redis": redis_healthy
        }
    }
