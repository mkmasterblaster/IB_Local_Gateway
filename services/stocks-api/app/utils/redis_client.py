"""Redis client for caching and session management."""
import redis.asyncio as aioredis
from typing import Optional
import structlog
from app.config import get_settings

logger = structlog.get_logger(__name__)

settings = get_settings()


class RedisClient:
    """Async Redis client wrapper."""
    
    def __init__(self):
        self.client: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Connect to Redis."""
        try:
            self.client = await aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("redis_connected")
        except Exception as e:
            logger.error("redis_connection_failed", error=str(e))
            raise
    
    async def disconnect(self):
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()
            logger.info("redis_disconnected")
    
    async def ping(self) -> bool:
        """Check Redis connection."""
        try:
            if self.client:
                await self.client.ping()
                return True
            return False
        except Exception as e:
            logger.error("redis_ping_failed", error=str(e))
            return False


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """Dependency for getting Redis client."""
    return redis_client
