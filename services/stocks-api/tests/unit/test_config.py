"""
Unit Tests for Configuration Module.

Tests configuration loading, validation, and helper properties.
"""
import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import Settings, get_config, get_settings


class TestSettings:
    """Test cases for Settings class."""
    
    def test_settings_requires_jwt_secret(self):
        """Test that Settings requires JWT_SECRET."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                database_url="postgresql://user:pass@localhost/db",
                redis_url="redis://localhost:6379"
            )
        
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("jwt_secret",) for error in errors)
    
    def test_settings_with_valid_config(self):
        """Test Settings creation with valid configuration."""
        settings = Settings(
            jwt_secret="this_is_a_very_long_secret_key_for_testing_purposes_1234",
            database_url="postgresql://user:pass@localhost/db",
            redis_url="redis://localhost:6379"
        )
        
        assert settings.jwt_secret == "this_is_a_very_long_secret_key_for_testing_purposes_1234"
        assert str(settings.database_url) == "postgresql://user:pass@localhost/db"
        assert str(settings.redis_url) == "redis://localhost:6379/"
    
    def test_settings_default_values(self):
        """Test that default values are applied correctly."""
        settings = Settings(
            jwt_secret="this_is_a_very_long_secret_key_for_testing_purposes_1234",
            database_url="postgresql://user:pass@localhost/db",
            redis_url="redis://localhost:6379"
        )
        
        assert settings.environment == "development"
        assert settings.log_level == "INFO"
        assert settings.log_format == "json"
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.trading_mode == "paper"
    
    def test_settings_environment_validation(self):
        """Test environment validation."""
        settings = Settings(
            jwt_secret="this_is_a_very_long_secret_key_for_testing_purposes_1234",
            database_url="postgresql://user:pass@localhost/db",
            redis_url="redis://localhost:6379",
            environment="production"
        )
        
        assert settings.environment == "production"
        assert settings.is_production is True
        assert settings.is_development is False
    
    def test_settings_jwt_secret_min_length(self):
        """Test JWT secret minimum length validation."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                jwt_secret="short",
                database_url="postgresql://user:pass@localhost/db",
                redis_url="redis://localhost:6379"
            )
        
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("jwt_secret",) and "at least 32 characters" in error["msg"].lower()
            for error in errors
        )
    
    def test_settings_database_url_validation(self):
        """Test database URL validation."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                jwt_secret="this_is_a_very_long_secret_key_for_testing_purposes_1234",
                database_url="mysql://user:pass@localhost/db",  # Wrong scheme
                redis_url="redis://localhost:6379"
            )
        
        errors = exc_info.value.errors()
        assert any("postgresql" in str(error).lower() for error in errors)
    
    def test_settings_redis_url_validation(self):
        """Test Redis URL validation."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                jwt_secret="this_is_a_very_long_secret_key_for_testing_purposes_1234",
                database_url="postgresql://user:pass@localhost/db",
                redis_url="http://localhost:6379"  # Wrong scheme
            )
        
        errors = exc_info.value.errors()
        assert any("redis" in str(error).lower() for error in errors)
    
    def test_settings_api_port_range(self):
        """Test API port range validation."""
        with pytest.raises(ValidationError):
            Settings(
                jwt_secret="this_is_a_very_long_secret_key_for_testing_purposes_1234",
                database_url="postgresql://user:pass@localhost/db",
                redis_url="redis://localhost:6379",
                api_port=100  # Too low
            )
        
        with pytest.raises(ValidationError):
            Settings(
                jwt_secret="this_is_a_very_long_secret_key_for_testing_purposes_1234",
                database_url="postgresql://user:pass@localhost/db",
                redis_url="redis://localhost:6379",
                api_port=70000  # Too high
            )
    
    def test_settings_is_paper_trading(self):
        """Test is_paper_trading property."""
        settings = Settings(
            jwt_secret="this_is_a_very_long_secret_key_for_testing_purposes_1234",
            database_url="postgresql://user:pass@localhost/db",
            redis_url="redis://localhost:6379",
            trading_mode="paper"
        )
        
        assert settings.is_paper_trading is True
        
        settings.trading_mode = "live"
        assert settings.is_paper_trading is False
    
    def test_settings_ib_gateway_config(self):
        """Test IB Gateway configuration."""
        settings = Settings(
            jwt_secret="this_is_a_very_long_secret_key_for_testing_purposes_1234",
            database_url="postgresql://user:pass@localhost/db",
            redis_url="redis://localhost:6379",
            ib_gateway_host="custom-gateway",
            ib_gateway_port=4001,
            ib_gateway_client_id=5
        )
        
        assert settings.ib_gateway_host == "custom-gateway"
        assert settings.ib_gateway_port == 4001
        assert settings.ib_gateway_client_id == 5


class TestGetSettings:
    """Test cases for get_settings function."""
    
    def test_get_settings_returns_singleton(self):
        """Test that get_settings returns the same instance."""
        with patch.dict(os.environ, {
            "JWT_SECRET": "this_is_a_very_long_secret_key_for_testing_purposes_1234",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379"
        }):
            settings1 = get_settings()
            settings2 = get_settings()
            
            assert settings1 is settings2
    
    def test_get_config_dependency(self):
        """Test get_config FastAPI dependency."""
        with patch.dict(os.environ, {
            "JWT_SECRET": "this_is_a_very_long_secret_key_for_testing_purposes_1234",
            "DATABASE_URL": "postgresql://user:pass@localhost/db",
            "REDIS_URL": "redis://localhost:6379"
        }):
            config = get_config()
            
            assert isinstance(config, Settings)
            assert config.jwt_secret == "this_is_a_very_long_secret_key_for_testing_purposes_1234"


@pytest.mark.unit
class TestConfigIntegration:
    """Integration tests for configuration module."""
    
    def test_settings_from_environment(self):
        """Test loading settings from environment variables."""
        with patch.dict(os.environ, {
            "JWT_SECRET": "test_secret_key_1234567890_abcdefghijklmnopqrstuvwxyz",
            "DATABASE_URL": "postgresql://testuser:testpass@testhost:5432/testdb",
            "REDIS_URL": "redis://testhost:6379",
            "ENVIRONMENT": "staging",
            "LOG_LEVEL": "DEBUG",
            "API_PORT": "9000"
        }):
            # Clear cache to force reload
            get_settings.cache_clear()
            
            settings = get_settings()
            
            assert settings.environment == "staging"
            assert settings.log_level == "DEBUG"
            assert settings.api_port == 9000
            assert "testhost" in str(settings.database_url)
