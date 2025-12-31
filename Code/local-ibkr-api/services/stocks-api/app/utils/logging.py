"""
Structured Logging Configuration for IBKR Local API.

Provides JSON-structured logging with correlation IDs, request context,
and consistent formatting across the application.
"""
import logging
import sys
from typing import Any, Dict

import structlog
from structlog.types import EventDict, Processor

from app.config import get_settings


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add application context to log entries.
    
    Args:
        logger: Logger instance
        method_name: Method name
        event_dict: Event dictionary
        
    Returns:
        Updated event dictionary
    """
    settings = get_settings()
    event_dict["environment"] = settings.environment
    event_dict["application"] = "ibkr-local-api"
    return event_dict


def add_severity_level(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add GCP-compatible severity level.
    
    Args:
        logger: Logger instance
        method_name: Method name
        event_dict: Event dictionary
        
    Returns:
        Updated event dictionary with severity
    """
    if "level" in event_dict:
        event_dict["severity"] = event_dict["level"].upper()
    return event_dict


def drop_color_message_key(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Remove colored message key from logs.
    
    Structlog adds a color_message key which we don't need in JSON output.
    
    Args:
        logger: Logger instance
        method_name: Method name
        event_dict: Event dictionary
        
    Returns:
        Updated event dictionary
    """
    event_dict.pop("color_message", None)
    return event_dict


def setup_logging() -> None:
    """
    Configure structured logging for the application.
    
    Sets up both structlog and standard library logging to work together
    with consistent JSON output and proper formatting.
    """
    settings = get_settings()
    
    # Determine log level
    log_level = getattr(logging, settings.log_level.upper())
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    
    # Define processors based on format
    if settings.log_format == "json":
        processors: list[Processor] = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_app_context,
            add_severity_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            drop_color_message_key,
            structlog.processors.JSONRenderer()
        ]
    else:
        # Console/development format
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            add_app_context,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Set log levels for noisy libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    if settings.is_development:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def log_request_context(
    request_id: str,
    method: str,
    path: str,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Create request context dictionary for logging.
    
    Args:
        request_id: Unique request ID
        method: HTTP method
        path: Request path
        **kwargs: Additional context
        
    Returns:
        Context dictionary
    """
    context = {
        "request_id": request_id,
        "method": method,
        "path": path,
    }
    context.update(kwargs)
    return context


def log_error_context(
    error: Exception,
    request_id: str | None = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Create error context dictionary for logging.
    
    Args:
        error: Exception instance
        request_id: Optional request ID
        **kwargs: Additional context
        
    Returns:
        Error context dictionary
    """
    context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    
    if request_id:
        context["request_id"] = request_id
    
    context.update(kwargs)
    return context


def log_trading_context(
    symbol: str,
    order_id: str | None = None,
    action: str | None = None,
    quantity: int | None = None,
    **kwargs: Any
) -> Dict[str, Any]:
    """
    Create trading context dictionary for logging.
    
    Args:
        symbol: Trading symbol
        order_id: Optional order ID
        action: Optional order action (buy/sell)
        quantity: Optional order quantity
        **kwargs: Additional context
        
    Returns:
        Trading context dictionary
    """
    context = {
        "symbol": symbol,
        "trading_event": True,
    }
    
    if order_id:
        context["order_id"] = order_id
    if action:
        context["action"] = action
    if quantity:
        context["quantity"] = quantity
    
    context.update(kwargs)
    return context
