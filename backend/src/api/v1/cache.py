"""Cache management endpoints."""

from typing import Dict, Any, List, Optional
from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from ...database.redis_client import redis_client

router = APIRouter()
logger = structlog.get_logger("cache")


class CacheStats(BaseModel):
    """Cache statistics model."""
    total_entries: int
    exact_matches: int
    semantic_matches: int
    pattern_matches: int
    total_size_mb: float
    hit_rate: float
    miss_rate: float


class CacheEntry(BaseModel):
    """Cache entry model."""
    key: str
    value: str
    cache_type: str  # exact, semantic, pattern
    ttl: int
    created_at: str
    last_accessed: str
    access_count: int


@router.get("/stats")
async def get_cache_stats() -> CacheStats:
    """Get comprehensive cache statistics."""
    
    logger.info("Cache statistics requested")
    
    try:
        # Get all cache-related keys
        cache_keys = await redis_client.keys("cache:*")
        hit_keys = await redis_client.keys("cache_hit:*")
        miss_keys = await redis_client.keys("cache_miss:*")
        
        # Count different cache types
        exact_matches = len(await redis_client.keys("cache:exact:*"))
        semantic_matches = len(await redis_client.keys("cache:semantic:*"))
        pattern_matches = len(await redis_client.keys("cache:pattern:*"))
        
        # Calculate hit rate
        total_hits = len(hit_keys)
        total_misses = len(miss_keys)
        total_requests = total_hits + total_misses
        
        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
        miss_rate = (total_misses / total_requests * 100) if total_requests > 0 else 0
        
        # Estimate cache size (simplified)
        total_size_mb = len(cache_keys) * 0.001  # Rough estimate
        
        stats = CacheStats(
            total_entries=len(cache_keys),
            exact_matches=exact_matches,
            semantic_matches=semantic_matches,
            pattern_matches=pattern_matches,
            total_size_mb=total_size_mb,
            hit_rate=round(hit_rate, 2),
            miss_rate=round(miss_rate, 2)
        )
        
        logger.info("Cache statistics retrieved", total_entries=stats.total_entries, hit_rate=stats.hit_rate)
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get cache statistics", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache statistics"
        )


@router.get("/entries")
async def list_cache_entries(
    cache_type: Optional[str] = Query(None, regex="^(exact|semantic|pattern)$"),
    limit: int = Query(50, ge=1, le=200)
) -> Dict[str, Any]:
    """List cache entries with optional type filtering."""
    
    logger.info("Cache entries list requested", cache_type=cache_type, limit=limit)
    
    try:
        # Build search pattern
        if cache_type:
            pattern = f"cache:{cache_type}:*"
        else:
            pattern = "cache:*"
        
        # Get cache keys
        cache_keys = await redis_client.keys(pattern)
        cache_keys = cache_keys[:limit]  # Apply limit
        
        entries = []
        for key in cache_keys:
            try:
                # Get cache entry data
                cache_data = await redis_client.hgetall(key)
                if cache_data:
                    # Get TTL
                    ttl = await redis_client.ttl(key)
                    
                    # Extract cache type from key
                    key_parts = key.split(":")
                    entry_cache_type = key_parts[1] if len(key_parts) > 1 else "unknown"
                    
                    entry = CacheEntry(
                        key=key,
                        value=cache_data.get("response", "")[:200] + "..." if len(cache_data.get("response", "")) > 200 else cache_data.get("response", ""),
                        cache_type=entry_cache_type,
                        ttl=ttl,
                        created_at=cache_data.get("created_at", ""),
                        last_accessed=cache_data.get("last_accessed", ""),
                        access_count=int(cache_data.get("access_count", 0))
                    )
                    entries.append(entry.dict())
            except Exception as entry_error:
                logger.warning("Failed to process cache entry", key=key, error=str(entry_error))
                continue
        
        return {
            "entries": entries,
            "count": len(entries),
            "cache_type": cache_type,
            "limit": limit
        }
        
    except Exception as e:
        logger.error("Failed to list cache entries", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache entries"
        )


@router.delete("/entries/{cache_key:path}")
async def delete_cache_entry(cache_key: str) -> Dict[str, Any]:
    """Delete specific cache entry."""
    
    logger.info("Cache entry deletion requested", key=cache_key)
    
    try:
        deleted = await redis_client.delete(cache_key)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cache entry '{cache_key}' not found"
            )
        
        logger.info("Cache entry deleted", key=cache_key)
        
        return {
            "success": True,
            "message": f"Cache entry '{cache_key}' deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete cache entry", error=str(e), key=cache_key)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete cache entry"
        )


@router.delete("/clear")
async def clear_cache(cache_type: Optional[str] = Query(None, regex="^(exact|semantic|pattern|all)$")) -> Dict[str, Any]:
    """Clear cache entries by type or all."""
    
    logger.info("Cache clear requested", cache_type=cache_type or "all")
    
    try:
        if cache_type and cache_type != "all":
            # Clear specific cache type
            pattern = f"cache:{cache_type}:*"
            keys = await redis_client.keys(pattern)
        else:
            # Clear all cache entries
            keys = await redis_client.keys("cache:*")
        
        cleared_count = 0
        if keys:
            cleared_count = await redis_client.delete(*keys)
        
        logger.info("Cache cleared", cache_type=cache_type or "all", cleared_count=cleared_count)
        
        return {
            "success": True,
            "message": f"Cleared {cleared_count} cache entries",
            "cache_type": cache_type or "all",
            "cleared_count": cleared_count
        }
        
    except Exception as e:
        logger.error("Failed to clear cache", error=str(e), cache_type=cache_type)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )


@router.get("/search")
async def search_cache(
    query: str = Query(..., min_length=1),
    cache_type: Optional[str] = Query(None, regex="^(exact|semantic|pattern)$"),
    limit: int = Query(20, ge=1, le=100)
) -> Dict[str, Any]:
    """Search cache entries by query."""
    
    logger.info("Cache search requested", query=query, cache_type=cache_type)
    
    try:
        # Build search pattern
        if cache_type:
            pattern = f"cache:{cache_type}:*"
        else:
            pattern = "cache:*"
        
        # Get cache keys
        all_keys = await redis_client.keys(pattern)
        matching_entries = []
        
        for key in all_keys:
            if len(matching_entries) >= limit:
                break
                
            try:
                # Get cache entry data
                cache_data = await redis_client.hgetall(key)
                if cache_data:
                    # Search in key, request, and response
                    search_text = f"{key} {cache_data.get('request', '')} {cache_data.get('response', '')}".lower()
                    
                    if query.lower() in search_text:
                        # Get TTL
                        ttl = await redis_client.ttl(key)
                        
                        # Extract cache type from key
                        key_parts = key.split(":")
                        entry_cache_type = key_parts[1] if len(key_parts) > 1 else "unknown"
                        
                        matching_entries.append({
                            "key": key,
                            "cache_type": entry_cache_type,
                            "request": cache_data.get("request", "")[:100] + "..." if len(cache_data.get("request", "")) > 100 else cache_data.get("request", ""),
                            "response": cache_data.get("response", "")[:100] + "..." if len(cache_data.get("response", "")) > 100 else cache_data.get("response", ""),
                            "ttl": ttl,
                            "created_at": cache_data.get("created_at", ""),
                            "access_count": int(cache_data.get("access_count", 0))
                        })
            except Exception as entry_error:
                logger.warning("Failed to search cache entry", key=key, error=str(entry_error))
                continue
        
        return {
            "query": query,
            "cache_type": cache_type,
            "results": matching_entries,
            "count": len(matching_entries),
            "limit": limit
        }
        
    except Exception as e:
        logger.error("Failed to search cache", error=str(e), query=query)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search cache"
        )