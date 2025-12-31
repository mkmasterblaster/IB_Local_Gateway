"""
Unit Tests for Health Check Router.

Tests health check endpoints and service status monitoring.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import create_application


@pytest.fixture
def client():
    """Create test client."""
    app = create_application()
    return TestClient(app)


@pytest.fixture
def mock_db_manager():
    """Mock database manager."""
    with patch("app.routers.health.get_db_manager") as mock:
        manager = MagicMock()
        manager.check_connection = AsyncMock()
        mock.return_value = manager
        yield manager


@pytest.fixture
def mock_redis_manager():
    """Mock Redis manager."""
    with patch("app.routers.health.get_redis_manager") as mock:
        manager = MagicMock()
        manager.check_connection = AsyncMock()
        mock.return_value = manager
        yield manager


class TestHealthEndpoint:
    """Test cases for /health endpoint."""
    
    def test_health_endpoint_exists(self, client):
        """Test that health endpoint exists and returns 200."""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
    
    def test_health_endpoint_response_structure(self, client):
        """Test health endpoint response structure."""
        response = client.get("/health")
        data = response.json()
        
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "environment" in data
        assert "services" in data
        
        assert isinstance(data["services"], dict)
        assert "database" in data["services"]
        assert "redis" in data["services"]
        assert "ib_gateway" in data["services"]
    
    def test_health_all_services_healthy(self, client, mock_db_manager, mock_redis_manager):
        """Test health response when all services are healthy."""
        # Mock healthy responses
        mock_db_manager.check_connection.return_value = True
        mock_redis_manager.check_connection.return_value = True
        
        response = client.get("/health")
        data = response.json()
        
        assert data["status"] == "degraded"  # IB Gateway is still degraded (stub)
        assert data["services"]["database"]["status"] == "healthy"
        assert data["services"]["redis"]["status"] == "healthy"
    
    def test_health_database_unhealthy(self, client, mock_db_manager, mock_redis_manager):
        """Test health response when database is unhealthy."""
        # Mock unhealthy database
        mock_db_manager.check_connection.return_value = False
        mock_redis_manager.check_connection.return_value = True
        
        response = client.get("/health")
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["services"]["database"]["status"] == "unhealthy"
    
    def test_health_redis_unhealthy(self, client, mock_db_manager, mock_redis_manager):
        """Test health response when Redis is unhealthy."""
        # Mock unhealthy Redis
        mock_db_manager.check_connection.return_value = True
        mock_redis_manager.check_connection.return_value = False
        
        response = client.get("/health")
        data = response.json()
        
        assert data["status"] == "unhealthy"
        assert data["services"]["redis"]["status"] == "unhealthy"
    
    def test_health_includes_latency(self, client, mock_db_manager, mock_redis_manager):
        """Test that health response includes latency measurements."""
        mock_db_manager.check_connection.return_value = True
        mock_redis_manager.check_connection.return_value = True
        
        response = client.get("/health")
        data = response.json()
        
        assert "latency_ms" in data["services"]["database"]
        assert "latency_ms" in data["services"]["redis"]
        
        # Latency should be a number
        db_latency = data["services"]["database"]["latency_ms"]
        redis_latency = data["services"]["redis"]["latency_ms"]
        
        assert isinstance(db_latency, (int, float))
        assert isinstance(redis_latency, (int, float))
        assert db_latency >= 0
        assert redis_latency >= 0


class TestLivenessEndpoint:
    """Test cases for /health/live endpoint."""
    
    def test_liveness_endpoint_exists(self, client):
        """Test that liveness endpoint exists."""
        response = client.get("/health/live")
        assert response.status_code == status.HTTP_200_OK
    
    def test_liveness_always_returns_alive(self, client):
        """Test that liveness always returns alive status."""
        response = client.get("/health/live")
        data = response.json()
        
        assert data["status"] == "alive"
    
    def test_liveness_no_dependency_checks(self, client, mock_db_manager, mock_redis_manager):
        """Test that liveness doesn't check dependencies."""
        # Make dependencies unhealthy
        mock_db_manager.check_connection.return_value = False
        mock_redis_manager.check_connection.return_value = False
        
        # Liveness should still pass
        response = client.get("/health/live")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "alive"


class TestReadinessEndpoint:
    """Test cases for /health/ready endpoint."""
    
    def test_readiness_endpoint_exists(self, client):
        """Test that readiness endpoint exists."""
        response = client.get("/health/ready")
        assert response.status_code == status.HTTP_200_OK
    
    def test_readiness_healthy_services(self, client, mock_db_manager, mock_redis_manager):
        """Test readiness when services are healthy."""
        mock_db_manager.check_connection.return_value = True
        mock_redis_manager.check_connection.return_value = True
        
        response = client.get("/health/ready")
        data = response.json()
        
        assert data["status"] == "ready"
    
    def test_readiness_unhealthy_database(self, client, mock_db_manager, mock_redis_manager):
        """Test readiness when database is unhealthy."""
        mock_db_manager.check_connection.return_value = False
        mock_redis_manager.check_connection.return_value = True
        
        response = client.get("/health/ready")
        data = response.json()
        
        assert data["status"] == "not_ready"
    
    def test_readiness_unhealthy_redis(self, client, mock_db_manager, mock_redis_manager):
        """Test readiness when Redis is unhealthy."""
        mock_db_manager.check_connection.return_value = True
        mock_redis_manager.check_connection.return_value = False
        
        response = client.get("/health/ready")
        data = response.json()
        
        assert data["status"] == "not_ready"


@pytest.mark.unit
class TestHealthCheckLogic:
    """Test health check logic and status determination."""
    
    def test_overall_status_all_healthy(self, client, mock_db_manager, mock_redis_manager):
        """Test overall status calculation with all services healthy."""
        mock_db_manager.check_connection.return_value = True
        mock_redis_manager.check_connection.return_value = True
        
        response = client.get("/health")
        data = response.json()
        
        # Should be degraded because IB Gateway is stubbed
        assert data["status"] in ["healthy", "degraded"]
    
    def test_overall_status_one_unhealthy(self, client, mock_db_manager, mock_redis_manager):
        """Test overall status with one unhealthy service."""
        mock_db_manager.check_connection.return_value = False
        mock_redis_manager.check_connection.return_value = True
        
        response = client.get("/health")
        data = response.json()
        
        assert data["status"] == "unhealthy"
    
    def test_health_response_includes_version(self, client):
        """Test that health response includes version."""
        response = client.get("/health")
        data = response.json()
        
        assert "version" in data
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0
    
    def test_health_response_includes_environment(self, client):
        """Test that health response includes environment."""
        response = client.get("/health")
        data = response.json()
        
        assert "environment" in data
        assert data["environment"] in ["development", "staging", "production"]
