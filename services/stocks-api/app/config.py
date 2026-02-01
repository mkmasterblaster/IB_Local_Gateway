"""Configuration settings for the trading API."""
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Environment
    ENVIRONMENT: str = "development"
    CONTAINER_NAME: str = "stocks"
    
    # Database
    DATABASE_URL: str = "postgresql://stocks_user:stocks_password@postgres:5432/stocks_db"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # IB Gateway
    IB_GATEWAY_HOST: str = "stocks-ib-gateway"
    IB_GATEWAY_PORT: int = 4002
    IB_CLIENT_ID: int = Field(
        ...,  # Required, no default
        description="IBKR clientId - must be unique per running client"
    )
    
    # Market Data Configuration
    # When you have real-time market data subscription, change to 1
    # 1 = Real-time (requires subscription)
    # 2 = Frozen (for testing)
    # 3 = Delayed (15-20 min delay, no subscription needed)
    # 4 = Delayed-Frozen
    MARKET_DATA_TYPE: int = 3  # Change to 1 when you have real-time subscription
    
    # Conditional Order Check Settings
    CONDITIONAL_CHECK_PRICE_WAIT: int = 2  # seconds to wait for price data
    

    @field_validator("IB_CLIENT_ID")
    @classmethod
    def validate_client_id(cls, v: int) -> int:
        """Validate client ID is not banned and is positive."""
        banned = {999}  # Known problematic IDs
        
        if v in banned:
            raise ValueError(
                f"IB_CLIENT_ID {v} is banned. "
                f"Use stocks range 1101+ (e.g., 1101, 1102, ...)"
            )
        
        if v < 1:
            raise ValueError("IB_CLIENT_ID must be >= 1")
        
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


# Export market data settings for easy import
settings = get_settings()
MARKET_DATA_TYPE = settings.MARKET_DATA_TYPE
CONDITIONAL_CHECK_PRICE_WAIT = settings.CONDITIONAL_CHECK_PRICE_WAIT
