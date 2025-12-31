"""Configuration management using Pydantic Settings."""
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""
    
    # Environment
    ENVIRONMENT: str = "development"
    
    # API Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "postgresql://stocks_user:stocks_password@postgres:5432/stocks_db"
    POSTGRES_DB: str = "stocks_db"
    POSTGRES_USER: str = "stocks_user"
    POSTGRES_PASSWORD: str = "stocks_password"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379"
    
    # IB Gateway
    IB_GATEWAY_HOST: str = "stocks-ib-gateway"
    IB_GATEWAY_PORT: int = 4003
    IB_CLIENT_ID: int = 1
    IB_ACCOUNT: str = ""
    
    # IBKR Credentials
    STOCKS_TWS_USERID: str = ""
    STOCKS_TWS_PASSWORD: str = ""
    STOCKS_TRADING_MODE: str = "paper"
    STOCKS_ACCOUNT: str = ""
    
    # Security
    STOCKS_JWT_SECRET: str = "change-this-secret"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Container
    CONTAINER_NAME: Optional[str] = "stocks"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
