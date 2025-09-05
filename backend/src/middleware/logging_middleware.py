"""Logging middleware for request/response tracking."""

import time
import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils.logging import log_performance


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""
    
    def __init__(self, app, logger_name: str = "http"):
        super().__init__(app)
        self.logger = structlog.get_logger(logger_name)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details."""
        
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        
        # Log request
        start_time = time.time()
        
        # Add request context to structlog
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            url=str(request.url),
            path=request.url.path,
            user_agent=request.headers.get("user-agent", ""),
            client_ip=request.client.host if request.client else "unknown",
        )
        
        self.logger.info("Request started")
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate response time
            process_time = time.time() - start_time
            
            # Log response
            self.logger.info(
                "Request completed",
                status_code=response.status_code,
                process_time=process_time
            )
            
            # Log performance metrics
            log_performance(
                operation="http_request",
                duration=process_time,
                method=request.method,
                path=request.url.path,
                status_code=response.status_code
            )
            
            # Add headers to response
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            
            self.logger.error(
                "Request failed",
                error=str(e),
                error_type=type(e).__name__,
                process_time=process_time,
                exc_info=e
            )
            
            raise
        
        finally:
            # Clear context
            structlog.contextvars.clear_contextvars()