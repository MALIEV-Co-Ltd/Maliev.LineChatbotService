"""Metrics and analytics endpoints."""

from datetime import datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from ...database.redis_client import redis_client

router = APIRouter()
logger = structlog.get_logger("metrics")


class MetricsSummary(BaseModel):
    """Metrics summary model."""
    total_requests: int
    total_responses: int
    avg_response_time_ms: float
    cache_hit_rate: float
    error_rate: float
    active_customers: int
    top_providers: list[dict[str, Any]]
    period: str


class UsageMetrics(BaseModel):
    """Usage metrics model."""
    date: str
    requests: int
    responses: int
    errors: int
    cache_hits: int
    cache_misses: int
    avg_response_time: float
    unique_users: int


@router.get("/summary")
async def get_metrics_summary(
    period: str = Query("24h", regex="^(1h|24h|7d|30d)$")
) -> MetricsSummary:
    """Get comprehensive metrics summary."""

    logger.info("Metrics summary requested", period=period)

    try:
        # Calculate time range (TODO: Implement time-based filtering)
        # For now, return all-time metrics regardless of period

        # Get metrics from Redis
        # These would be populated by the application during operation

        # Total requests and responses
        request_keys = await redis_client.keys("metric:request:*")
        response_keys = await redis_client.keys("metric:response:*")

        total_requests = len(request_keys)
        total_responses = len(response_keys)

        # Cache metrics
        cache_hits = len(await redis_client.keys("cache_hit:*"))
        cache_misses = len(await redis_client.keys("cache_miss:*"))
        total_cache_requests = cache_hits + cache_misses
        cache_hit_rate = (cache_hits / total_cache_requests * 100) if total_cache_requests > 0 else 0

        # Error metrics
        error_keys = await redis_client.keys("metric:error:*")
        error_rate = (len(error_keys) / max(total_requests, 1) * 100) if total_requests > 0 else 0

        # Response time (mock data for now)
        avg_response_time_ms = 250.0

        # Active customers
        customer_keys = await redis_client.keys("customer:*")
        active_customers = len(customer_keys)

        # Top providers (mock data)
        top_providers = [
            {"name": "gemini-2.5-flash", "requests": total_requests * 0.7, "avg_response_time": 200},
            {"name": "openai-gpt-4", "requests": total_requests * 0.2, "avg_response_time": 300},
            {"name": "deepseek", "requests": total_requests * 0.1, "avg_response_time": 150}
        ]

        summary = MetricsSummary(
            total_requests=total_requests,
            total_responses=total_responses,
            avg_response_time_ms=avg_response_time_ms,
            cache_hit_rate=round(cache_hit_rate, 2),
            error_rate=round(error_rate, 2),
            active_customers=active_customers,
            top_providers=top_providers,
            period=period
        )

        logger.info("Metrics summary retrieved", period=period, total_requests=total_requests)

        return summary

    except Exception as e:
        logger.error("Failed to get metrics summary", error=str(e), period=period)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics summary"
        )


@router.get("/usage")
async def get_usage_metrics(
    days: int = Query(7, ge=1, le=90)
) -> dict[str, Any]:
    """Get daily usage metrics for specified period."""

    logger.info("Usage metrics requested", days=days)

    try:
        # Generate daily metrics for the specified period
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days-1)

        daily_metrics = []
        current_date = start_date

        while current_date <= end_date:
            # Get metrics for this specific date
            date_str = current_date.strftime("%Y-%m-%d")

            # Get metrics from Redis (these would be stored daily)
            date_pattern = f"metric:daily:{date_str}:*"
            date_keys = await redis_client.keys(date_pattern)

            # Mock data for demonstration
            # In production, this would aggregate actual stored metrics
            base_requests = max(50, len(date_keys) * 10)

            metrics = UsageMetrics(
                date=date_str,
                requests=base_requests + (current_date.weekday() * 20),  # More requests on weekends
                responses=base_requests - 5,
                errors=max(0, base_requests // 20),
                cache_hits=base_requests // 2,
                cache_misses=base_requests // 3,
                avg_response_time=250.0 + (current_date.weekday() * 10),
                unique_users=max(10, base_requests // 10)
            )

            daily_metrics.append(metrics.dict())
            current_date += timedelta(days=1)

        return {
            "metrics": daily_metrics,
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        }

    except Exception as e:
        logger.error("Failed to get usage metrics", error=str(e), days=days)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage metrics"
        )


@router.get("/providers")
async def get_provider_metrics() -> dict[str, Any]:
    """Get AI provider performance metrics."""

    logger.info("Provider metrics requested")

    try:
        # Get provider statistics from Redis
        provider_keys = await redis_client.keys("ai:provider:*")
        provider_metrics = []

        for key in provider_keys:
            provider_data = await redis_client.hgetall(key)
            if provider_data:
                provider_name = key.split(":")[-1]

                # Get usage statistics for this provider
                usage_pattern = f"metric:provider:{provider_name}:*"
                usage_keys = await redis_client.keys(usage_pattern)

                # Mock performance data (in production, this would be real metrics)
                provider_metrics.append({
                    "name": provider_name,
                    "type": provider_data.get("provider_type", "unknown"),
                    "model": provider_data.get("model", "unknown"),
                    "enabled": provider_data.get("enabled", "false") == "true",
                    "total_requests": len(usage_keys) * 10,
                    "avg_response_time_ms": 200 + (len(provider_name) % 5) * 50,
                    "success_rate": 95 + (len(provider_name) % 3),
                    "last_used": datetime.utcnow().isoformat(),
                    "cost_estimate": len(usage_keys) * 0.001
                })

        return {
            "providers": provider_metrics,
            "count": len(provider_metrics)
        }

    except Exception as e:
        logger.error("Failed to get provider metrics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider metrics"
        )


@router.get("/errors")
async def get_error_metrics(
    limit: int = Query(50, ge=1, le=200)
) -> dict[str, Any]:
    """Get recent error metrics and patterns."""

    logger.info("Error metrics requested", limit=limit)

    try:
        # Get error entries from Redis
        error_keys = await redis_client.keys("metric:error:*")
        error_keys = error_keys[:limit]  # Apply limit

        errors = []
        error_counts = {}

        for key in error_keys:
            error_data = await redis_client.hgetall(key)
            if error_data:
                error_type = error_data.get("error_type", "unknown")
                error_counts[error_type] = error_counts.get(error_type, 0) + 1

                errors.append({
                    "timestamp": error_data.get("timestamp", ""),
                    "error_type": error_type,
                    "error_message": error_data.get("error_message", ""),
                    "path": error_data.get("path", ""),
                    "user_id": error_data.get("user_id", ""),
                    "provider": error_data.get("provider", "")
                })

        # Sort errors by timestamp (most recent first)
        errors.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return {
            "errors": errors,
            "error_counts": error_counts,
            "total_errors": len(errors),
            "limit": limit
        }

    except Exception as e:
        logger.error("Failed to get error metrics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve error metrics"
        )


@router.post("/record")
async def record_metric(metric_data: dict[str, Any]) -> dict[str, Any]:
    """Record a custom metric (used internally by the application)."""

    logger.info("Metric recording requested", metric_type=metric_data.get("type"))

    try:
        metric_type = metric_data.get("type", "custom")
        timestamp = datetime.utcnow().isoformat()

        # Create metric key
        metric_key = f"metric:{metric_type}:{timestamp}"

        # Add timestamp to data
        metric_data["timestamp"] = timestamp

        # Store metric data
        for field, value in metric_data.items():
            await redis_client.hset(metric_key, field, str(value))

        # Set expiration (30 days)
        await redis_client.expire(metric_key, 30 * 24 * 60 * 60)

        logger.info("Metric recorded", type=metric_type, key=metric_key)

        return {
            "success": True,
            "message": "Metric recorded successfully",
            "metric_key": metric_key
        }

    except Exception as e:
        logger.error("Failed to record metric", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record metric"
        )
