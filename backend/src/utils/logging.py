"""Structured logging configuration using structlog."""

import logging
import sys
import uuid
from typing import Any, Dict

import structlog
from structlog.types import EventDict

from ..config.settings import settings


def add_request_id(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add request ID to log records."""
    if "request_id" not in event_dict:
        event_dict["request_id"] = str(uuid.uuid4())[:8]
    return event_dict


def add_timestamp(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add timestamp to log records."""
    import time
    event_dict["timestamp"] = time.time()
    return event_dict


def setup_logging() -> None:
    """Configure structured logging for the application."""
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level),
    )

    # Configure structlog
    processors = [
        structlog.contextvars.merge_contextvars,
        add_request_id,
        add_timestamp,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
    ]

    if settings.structured_logging:
        # JSON output for production
        processors.extend([
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ])
    else:
        # Pretty output for development
        processors.extend([
            structlog.dev.ConsoleRenderer(colors=True)
        ])

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Set log levels for external libraries
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


def log_function_call(func_name: str, **kwargs: Any) -> None:
    """Log function call with parameters."""
    logger = get_logger("function_call")
    logger.debug("Function called", function=func_name, **kwargs)


def log_error(error: Exception, context: Dict[str, Any] = None) -> None:
    """Log error with context information."""
    logger = get_logger("error")
    logger.error(
        "Error occurred",
        error_type=type(error).__name__,
        error_message=str(error),
        context=context or {},
        exc_info=error
    )


def log_performance(operation: str, duration: float, **kwargs: Any) -> None:
    """Log performance metrics."""
    logger = get_logger("performance")
    logger.info(
        "Performance metric",
        operation=operation,
        duration_seconds=duration,
        **kwargs
    )


def log_business_event(event: str, **kwargs: Any) -> None:
    """Log business events."""
    logger = get_logger("business")
    logger.info(
        "Business event",
        event=event,
        **kwargs
    )