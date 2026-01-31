"""
Global Exception Handlers for FastAPI.

Provides consistent error responses and logging for all exceptions.
"""
import traceback
from datetime import datetime
from typing import Any, Dict

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.utils.logging import get_logger

logger = get_logger(__name__)


class ErrorDetail(BaseModel):
    """Detailed error information."""
    
    field: str | None = Field(
        default=None,
        description="Field that caused the error (for validation errors)"
    )
    message: str = Field(
        description="Error message"
    )
    type: str | None = Field(
        default=None,
        description="Error type"
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    error_code: str = Field(
        description="Machine-readable error code"
    )
    message: str = Field(
        description="Human-readable error message"
    )
    details: Dict[str, Any] | list[ErrorDetail] | None = Field(
        default=None,
        description="Additional error details"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Error timestamp"
    )
    request_id: str | None = Field(
        default=None,
        description="Request correlation ID"
    )
    path: str | None = Field(
        default=None,
        description="Request path"
    )


def get_request_id(request: Request) -> str | None:
    """
    Extract request ID from request state.
    
    Args:
        request: FastAPI request
        
    Returns:
        Request ID if available
    """
    return getattr(request.state, "request_id", None)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTP exceptions.
    
    Args:
        request: FastAPI request
        exc: HTTP exception
        
    Returns:
        JSON error response
    """
    request_id = get_request_id(request)
    
    # Map HTTP status codes to error codes
    error_code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }
    
    error_code = error_code_map.get(exc.status_code, "HTTP_ERROR")
    
    logger.warning(
        "http_exception",
        request_id=request_id,
        status_code=exc.status_code,
        error_code=error_code,
        path=request.url.path,
        detail=exc.detail
    )
    
    error_response = ErrorResponse(
        error_code=error_code,
        message=exc.detail if isinstance(exc.detail, str) else "HTTP error occurred",
        details=exc.detail if isinstance(exc.detail, dict) else None,
        request_id=request_id,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(mode="json")
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
) -> JSONResponse:
    """
    Handle request validation errors.
    
    Args:
        request: FastAPI request
        exc: Validation exception
        
    Returns:
        JSON error response
    """
    request_id = get_request_id(request)
    
    # Convert Pydantic errors to our format
    error_details = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        error_details.append(
            ErrorDetail(
                field=field,
                message=error["msg"],
                type=error["type"]
            )
        )
    
    logger.warning(
        "validation_error",
        request_id=request_id,
        path=request.url.path,
        errors=len(error_details)
    )
    
    error_response = ErrorResponse(
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        details=[detail.model_dump() for detail in error_details],
        request_id=request_id,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_response.model_dump(mode="json")
    )


async def database_exception_handler(
    request: Request,
    exc: SQLAlchemyError
) -> JSONResponse:
    """
    Handle database exceptions.
    
    Args:
        request: FastAPI request
        exc: SQLAlchemy exception
        
    Returns:
        JSON error response
    """
    request_id = get_request_id(request)
    
    logger.error(
        "database_error",
        request_id=request_id,
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__
    )
    
    error_response = ErrorResponse(
        error_code="DATABASE_ERROR",
        message="A database error occurred",
        details={
            "error_type": type(exc).__name__
        },
        request_id=request_id,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(mode="json")
    )


async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """
    Handle all other unhandled exceptions.
    
    Args:
        request: FastAPI request
        exc: Any exception
        
    Returns:
        JSON error response
    """
    request_id = get_request_id(request)
    
    # Get stack trace
    stack_trace = traceback.format_exc()
    
    logger.error(
        "unhandled_exception",
        request_id=request_id,
        path=request.url.path,
        error=str(exc),
        error_type=type(exc).__name__,
        stack_trace=stack_trace
    )
    
    error_response = ErrorResponse(
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
        details={
            "error_type": type(exc).__name__
        },
        request_id=request_id,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(mode="json")
    )


def register_exception_handlers(app) -> None:
    """
    Register all exception handlers with the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
    
    logger.info("exception_handlers_registered")


# Custom application exceptions

class IBKRError(Exception):
    """Base exception for IBKR-related errors."""
    pass


class IBKRConnectionError(IBKRError):
    """Exception raised when IBKR connection fails."""
    pass


class IBKROrderError(IBKRError):
    """Exception raised when order placement fails."""
    pass


class IBKRMarketDataError(IBKRError):
    """Exception raised when market data subscription fails."""
    pass


class RiskLimitError(Exception):
    """Exception raised when risk limits are breached."""
    pass


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is triggered."""
    pass


# IBKR-specific exceptions
class IBKRException(Exception):
    """Base exception for IBKR-related errors."""
    pass


class IBKRConnectionError(IBKRException):
    """Raised when connection to IB Gateway fails."""
    pass


class IBKRAuthenticationError(IBKRException):
    """Raised when authentication with IB Gateway fails."""
    pass


class IBKROrderError(IBKRException):
    """Raised when order placement fails."""
    pass


class IBKRMarketDataError(IBKRException):
    """Raised when market data request fails."""
    pass


class IBKRPositionError(IBKRException):
    """Raised when position retrieval fails."""
    pass


class IBKRAccountError(IBKRException):
    """Raised when account data retrieval fails."""
    pass


# Database exceptions
class DatabaseError(Exception):
    """Base exception for database errors."""
    pass


# Risk management exceptions
class RiskCheckError(Exception):
    """Raised when risk check fails."""
    pass
