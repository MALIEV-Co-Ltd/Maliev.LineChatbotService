"""Admin management endpoints."""

from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ...config.settings import settings
from ...database.redis_client import redis_client

router = APIRouter()
logger = structlog.get_logger("admin")


class SystemStatus(BaseModel):
    """System status model."""
    status: str
    version: str
    environment: str
    uptime: float
    redis_status: str
    active_sessions: int
    cache_entries: int


class ConfigUpdate(BaseModel):
    """Configuration update model."""
    key: str
    value: Any
    section: str = "general"


@router.get("/status", response_model=SystemStatus)
async def get_system_status() -> SystemStatus:
    """Get comprehensive system status."""

    logger.info("System status requested")

    try:
        # Check Redis status
        redis_healthy = await redis_client.health_check()
        redis_status = "healthy" if redis_healthy else "unhealthy"

        # Get cache statistics
        cache_entries = 0
        active_sessions = 0

        if redis_healthy:
            try:
                cache_entries = await redis_client.dbsize()
                # Count active sessions (example pattern)
                session_keys = await redis_client.keys("session:*")
                active_sessions = len(session_keys)
            except Exception as e:
                logger.warning("Failed to get cache statistics", error=str(e))

        return SystemStatus(
            status="healthy" if redis_healthy else "degraded",
            version=settings.version,
            environment=settings.environment,
            uptime=0.0,  # TODO: Calculate actual uptime
            redis_status=redis_status,
            active_sessions=active_sessions,
            cache_entries=cache_entries
        )

    except Exception as e:
        logger.error("Failed to get system status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve system status"
        )


@router.get("/logs")
async def get_recent_logs(limit: int = 100) -> dict[str, Any]:
    """Get recent application logs."""

    logger.info("Recent logs requested", limit=limit)

    try:
        # TODO: Implement log retrieval from structured logging system
        # This would typically read from a log aggregation system

        return {
            "logs": [],
            "total": 0,
            "limit": limit,
            "message": "Log retrieval not yet implemented"
        }

    except Exception as e:
        logger.error("Failed to retrieve logs", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve logs"
        )


@router.put("/config")
async def update_configuration(config: ConfigUpdate) -> dict[str, Any]:
    """Update application configuration."""

    logger.info("Configuration update requested", key=config.key, section=config.section)

    try:
        # Store configuration in Redis
        config_key = f"config:{config.section}:{config.key}"
        await redis_client.set(config_key, str(config.value))

        # TODO: Implement configuration validation and hot-reload

        logger.info("Configuration updated", key=config.key, value=config.value)

        return {
            "success": True,
            "message": f"Configuration {config.key} updated successfully",
            "key": config.key,
            "value": config.value,
            "section": config.section
        }

    except Exception as e:
        logger.error("Failed to update configuration", error=str(e), key=config.key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update configuration"
        )


@router.get("/config")
async def get_configuration(section: str = "general") -> dict[str, Any]:
    """Get current configuration."""

    logger.info("Configuration requested", section=section)

    try:
        # Get configuration from Redis
        pattern = f"config:{section}:*"
        config_keys = await redis_client.keys(pattern)

        configuration = {}
        for key in config_keys:
            value = await redis_client.get(key)
            # Extract the actual config key name
            config_name = key.split(":")[-1]
            configuration[config_name] = value

        return {
            "section": section,
            "configuration": configuration,
            "count": len(configuration)
        }

    except Exception as e:
        logger.error("Failed to get configuration", error=str(e), section=section)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve configuration"
        )


@router.delete("/cache")
async def clear_cache(pattern: str = "*") -> dict[str, Any]:
    """Clear application cache."""

    logger.info("Cache clear requested", pattern=pattern)

    try:
        if pattern == "*":
            # Clear entire database
            await redis_client.flushdb()
            cleared_count = "all"
        else:
            # Clear specific pattern
            keys = await redis_client.keys(pattern)
            if keys:
                cleared_count = await redis_client.delete(*keys)
            else:
                cleared_count = 0

        logger.info("Cache cleared", pattern=pattern, cleared_count=cleared_count)

        return {
            "success": True,
            "message": f"Cache cleared for pattern: {pattern}",
            "cleared_count": cleared_count
        }

    except Exception as e:
        logger.error("Failed to clear cache", error=str(e), pattern=pattern)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )
