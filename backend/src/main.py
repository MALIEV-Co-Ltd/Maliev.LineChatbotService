"""
Main FastAPI application for Maliev LINE Chatbot Service.

A comprehensive LINE chatbot service for 3D printing business with multi-provider AI integration,
dynamic system instructions, intelligent caching, and customer management.
"""

from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from .api.v1 import router as api_v1_router
from .config.settings import settings
from .database.redis_client import redis_client
from .middleware.auth_middleware import AuthMiddleware
from .middleware.logging_middleware import LoggingMiddleware
from .utils.logging import setup_logging

# Setup structured logging
setup_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown events."""
    logger.info("Starting Maliev LINE Chatbot Service", version=settings.version)

    try:
        # Initialize Redis connection
        await redis_client.connect()
        logger.info("Redis connection established")

        # TODO: Initialize other services
        # - AI providers
        # - Secret Manager
        # - Cache system
        # - Customer service
        # - Instruction system

        logger.info("All services initialized successfully")

        yield  # Application is running

    except Exception as e:
        logger.error("Failed to initialize services", error=str(e))
        raise
    finally:
        # Cleanup on shutdown
        logger.info("Shutting down services")

        try:
            await redis_client.disconnect()
            logger.info("Redis connection closed")

        except Exception as e:
            logger.error("Error during shutdown", error=str(e))

        logger.info("Shutdown completed")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    # Create FastAPI app
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Comprehensive LINE chatbot service for 3D printing business",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # Add middleware
    setup_middleware(app)

    # Add routes
    setup_routes(app)

    # Add exception handlers
    setup_exception_handlers(app)

    return app


def setup_middleware(app: FastAPI) -> None:
    """Configure application middleware."""

    # Trusted host middleware (security)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]  # Configure with actual hosts in production
        )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        **settings.get_cors_config()
    )

    # Custom logging middleware
    app.add_middleware(LoggingMiddleware)

    # Authentication middleware for admin routes
    app.add_middleware(AuthMiddleware)


def setup_routes(app: FastAPI) -> None:
    """Configure application routes."""

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, Any]:
        """Application health check."""
        health_status = {
            "status": "healthy",
            "version": settings.version,
            "environment": settings.environment,
            "redis": "disconnected"
        }

        # Check Redis connection
        try:
            redis_healthy = await redis_client.health_check()
            health_status["redis"] = "healthy" if redis_healthy else "unhealthy"
        except Exception as e:
            health_status["redis"] = f"error: {str(e)}"

        return health_status

    # Redis health check endpoint
    @app.get("/health/redis", tags=["Health"])
    async def redis_health_check() -> dict[str, Any]:
        """Redis connection health check."""
        try:
            redis_healthy = await redis_client.health_check()
            if redis_healthy:
                redis_info = await redis_client.info("server")
                return {
                    "status": "healthy",
                    "redis_version": redis_info.get("redis_version", "unknown"),
                    "connected_clients": redis_info.get("connected_clients", 0),
                    "used_memory_human": redis_info.get("used_memory_human", "unknown")
                }
            else:
                return {"status": "unhealthy", "error": "Connection test failed"}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    # Root endpoint
    @app.get("/", tags=["Root"])
    async def root() -> dict[str, str]:
        """Root endpoint with basic information."""
        return {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.version,
            "environment": settings.environment,
            "docs_url": "/docs",
            "health_url": "/health"
        }

    # Include API routes
    app.include_router(
        api_v1_router,
        prefix="/api/v1",
        tags=["API v1"]
    )

    # LINE webhook endpoint
    @app.post("/webhook", tags=["LINE"])
    async def line_webhook(request: Request) -> Response:
        """LINE webhook endpoint with signature verification."""
        from .line import line_webhook_handler

        try:
            result = await line_webhook_handler.handle_webhook(request)
            return JSONResponse(result)
        except Exception as e:
            logger.error("LINE webhook processing failed", error=str(e), exc_info=e)
            return JSONResponse(
                status_code=500,
                content={"error": "Webhook processing failed"}
            )


def setup_exception_handlers(app: FastAPI) -> None:
    """Configure global exception handlers."""

    @app.exception_handler(500)
    async def internal_server_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle internal server errors."""
        logger.error(
            "Internal server error",
            path=str(request.url),
            method=request.method,
            error=str(exc),
            exc_info=exc
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "request_id": getattr(request.state, "request_id", None)
            }
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle not found errors."""
        logger.warning(
            "Resource not found",
            path=str(request.url),
            method=request.method
        )

        return JSONResponse(
            status_code=404,
            content={
                "error": "Not Found",
                "message": "The requested resource was not found",
                "path": str(request.url.path)
            }
        )


# Create the FastAPI app
app = create_app()


# Development server entry point
if __name__ == "__main__":
    import uvicorn

    logger.info(
        "Starting development server",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )

    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
        access_log=True
    )
