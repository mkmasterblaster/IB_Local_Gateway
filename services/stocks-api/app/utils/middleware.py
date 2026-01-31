"""
Application Middleware.

Provides middleware for request tracking, logging, and correlation IDs.
"""
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from structlog import contextvars

from app.utils.logging import get_logger

logger = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject request IDs into all requests.
    
    Generates a unique request ID for each request and makes it available
    in request.state and response headers.
    """
    
    def __init__(self, app: ASGIApp):
        """
        Initialize middleware.
        
        Args:
            app: ASGI application
        """
        super().__init__(app)
        logger.info("request_id_middleware_initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and inject request ID.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Response with X-Request-ID header
        """
        # Check if request already has an ID (from client)
        request_id = request.headers.get("X-Request-ID")
        
        if not request_id:
            # Generate new request ID
            request_id = str(uuid.uuid4())
        
        # Store in request state
        request.state.request_id = request_id
        
        # Bind to structured logging context
        contextvars.bind_contextvars(request_id=request_id)
        
        try:
            response = await call_next(request)
        finally:
            # Clear context
            contextvars.clear_contextvars()
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all HTTP requests and responses.
    
    Logs request start, completion, and any errors with timing information.
    """
    
    def __init__(self, app: ASGIApp):
        """
        Initialize middleware.
        
        Args:
            app: ASGI application
        """
        super().__init__(app)
        logger.info("request_logging_middleware_initialized")
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and log details.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Response
        """
        # Skip logging for health checks and metrics
        if request.url.path in ["/health", "/health/live", "/health/ready", "/metrics"]:
            return await call_next(request)
        
        request_id = getattr(request.state, "request_id", None)
        start_time = time.time()
        
        # Log request start
        logger.info(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Log successful response
            logger.info(
                "request_completed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2)
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Log error
            logger.error(
                "request_failed",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration * 1000, 2)
            )
            
            raise


class CORSHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add CORS headers to responses.
    
    Allows the React frontend to make requests to the API.
    """
    
    def __init__(self, app: ASGIApp, allow_origins: list[str] | None = None):
        """
        Initialize middleware.
        
        Args:
            app: ASGI application
            allow_origins: List of allowed origins (default: localhost:3001)
        """
        super().__init__(app)
        self.allow_origins = allow_origins or [
            "http://localhost:3001",
            "http://127.0.0.1:3001"
        ]
        logger.info(
            "cors_headers_middleware_initialized",
            allow_origins=self.allow_origins
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and add CORS headers.
        
        Args:
            request: Incoming request
            call_next: Next middleware/endpoint
            
        Returns:
            Response with CORS headers
        """
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, PATCH, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Request-ID"
            response.headers["Access-Control-Max-Age"] = "3600"
            return response
        
        response = await call_next(request)
        
        # Add CORS headers to response
        origin = request.headers.get("origin")
        if origin in self.allow_origins or "*" in self.allow_origins:
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
        
        return response
