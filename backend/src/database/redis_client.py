"""Redis client configuration and connection management."""

import asyncio
import logging
from typing import Any, Dict, Optional, Union

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from ..config.settings import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client wrapper with connection management."""

    def __init__(self) -> None:
        """Initialize Redis client."""
        self._client: Optional[Redis] = None
        self._connection_pool: Optional[redis.ConnectionPool] = None
        self._connected = False

    async def connect(self) -> None:
        """Establish Redis connection."""
        if self._connected and self._client:
            return

        try:
            # Create connection pool
            self._connection_pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                max_connections=settings.redis_max_connections,
                retry_on_timeout=settings.redis_retry_on_timeout,
                decode_responses=True,
                encoding='utf-8'
            )

            # Create Redis client
            self._client = redis.Redis(connection_pool=self._connection_pool)

            # Test connection
            await self._client.ping()
            self._connected = True
            
            logger.info("Redis connection established successfully")

        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self._connected = False
            raise

        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

        if self._connection_pool:
            await self._connection_pool.aclose()
            self._connection_pool = None

        self._connected = False
        logger.info("Redis connection closed")

    async def health_check(self) -> bool:
        """Check Redis connection health."""
        try:
            if not self._client:
                return False
            
            await self._client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

    @property
    def client(self) -> Redis:
        """Get Redis client instance."""
        if not self._connected or not self._client:
            raise ConnectionError("Redis client is not connected")
        return self._client

    @property
    def is_connected(self) -> bool:
        """Check if Redis client is connected."""
        return self._connected

    # Core Redis operations with error handling

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        try:
            return await self.client.get(key)
        except RedisError as e:
            logger.error(f"Redis GET error for key '{key}': {e}")
            raise

    async def set(
        self, 
        key: str, 
        value: Union[str, bytes, int, float], 
        ex: Optional[int] = None,
        px: Optional[int] = None,
        nx: bool = False,
        xx: bool = False
    ) -> bool:
        """Set key-value pair with optional expiration."""
        try:
            return await self.client.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
        except RedisError as e:
            logger.error(f"Redis SET error for key '{key}': {e}")
            raise

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        try:
            return await self.client.delete(*keys)
        except RedisError as e:
            logger.error(f"Redis DELETE error for keys {keys}: {e}")
            raise

    async def exists(self, *keys: str) -> int:
        """Check if keys exist."""
        try:
            return await self.client.exists(*keys)
        except RedisError as e:
            logger.error(f"Redis EXISTS error for keys {keys}: {e}")
            raise

    async def expire(self, key: str, time: int) -> bool:
        """Set key expiration time."""
        try:
            return await self.client.expire(key, time)
        except RedisError as e:
            logger.error(f"Redis EXPIRE error for key '{key}': {e}")
            raise

    async def ttl(self, key: str) -> int:
        """Get key time to live."""
        try:
            return await self.client.ttl(key)
        except RedisError as e:
            logger.error(f"Redis TTL error for key '{key}': {e}")
            raise

    # Hash operations

    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field value."""
        try:
            return await self.client.hget(name, key)
        except RedisError as e:
            logger.error(f"Redis HGET error for hash '{name}' key '{key}': {e}")
            raise

    async def hset(self, name: str, key: str, value: Union[str, bytes, int, float]) -> int:
        """Set hash field value."""
        try:
            return await self.client.hset(name, key, value)
        except RedisError as e:
            logger.error(f"Redis HSET error for hash '{name}' key '{key}': {e}")
            raise

    async def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields and values."""
        try:
            return await self.client.hgetall(name)
        except RedisError as e:
            logger.error(f"Redis HGETALL error for hash '{name}': {e}")
            raise

    async def hdel(self, name: str, *keys: str) -> int:
        """Delete hash fields."""
        try:
            return await self.client.hdel(name, *keys)
        except RedisError as e:
            logger.error(f"Redis HDEL error for hash '{name}' keys {keys}: {e}")
            raise

    async def hincrby(self, name: str, key: str, amount: int = 1) -> int:
        """Increment hash field by amount."""
        try:
            return await self.client.hincrby(name, key, amount)
        except RedisError as e:
            logger.error(f"Redis HINCRBY error for hash '{name}' key '{key}': {e}")
            raise

    # Set operations

    async def sadd(self, name: str, *values: Union[str, bytes, int, float]) -> int:
        """Add members to set."""
        try:
            return await self.client.sadd(name, *values)
        except RedisError as e:
            logger.error(f"Redis SADD error for set '{name}': {e}")
            raise

    async def srem(self, name: str, *values: Union[str, bytes, int, float]) -> int:
        """Remove members from set."""
        try:
            return await self.client.srem(name, *values)
        except RedisError as e:
            logger.error(f"Redis SREM error for set '{name}': {e}")
            raise

    async def smembers(self, name: str) -> set:
        """Get all set members."""
        try:
            return await self.client.smembers(name)
        except RedisError as e:
            logger.error(f"Redis SMEMBERS error for set '{name}': {e}")
            raise

    async def sismember(self, name: str, value: Union[str, bytes, int, float]) -> bool:
        """Check if value is set member."""
        try:
            return await self.client.sismember(name, value)
        except RedisError as e:
            logger.error(f"Redis SISMEMBER error for set '{name}': {e}")
            raise

    # Pub/Sub operations

    async def publish(self, channel: str, message: str) -> int:
        """Publish message to channel."""
        try:
            return await self.client.publish(channel, message)
        except RedisError as e:
            logger.error(f"Redis PUBLISH error for channel '{channel}': {e}")
            raise

    def pubsub(self):
        """Get pub/sub instance."""
        return self.client.pubsub()

    # Utility operations

    async def keys(self, pattern: str = "*") -> list:
        """Get keys matching pattern."""
        try:
            return await self.client.keys(pattern)
        except RedisError as e:
            logger.error(f"Redis KEYS error for pattern '{pattern}': {e}")
            raise

    async def scan(self, cursor: int = 0, match: Optional[str] = None, count: Optional[int] = None):
        """Scan keys with cursor."""
        try:
            return await self.client.scan(cursor, match, count)
        except RedisError as e:
            logger.error(f"Redis SCAN error: {e}")
            raise

    async def flushdb(self) -> bool:
        """Flush current database."""
        try:
            return await self.client.flushdb()
        except RedisError as e:
            logger.error(f"Redis FLUSHDB error: {e}")
            raise

    async def dbsize(self) -> int:
        """Get database size."""
        try:
            return await self.client.dbsize()
        except RedisError as e:
            logger.error(f"Redis DBSIZE error: {e}")
            raise

    async def info(self, section: Optional[str] = None) -> Dict[str, Any]:
        """Get Redis server info."""
        try:
            return await self.client.info(section)
        except RedisError as e:
            logger.error(f"Redis INFO error: {e}")
            raise

    # List operations

    async def lrange(self, key: str, start: int, end: int) -> list:
        """Get range of list elements."""
        try:
            return await self.client.lrange(key, start, end)
        except RedisError as e:
            logger.error(f"Redis LRANGE error for key '{key}': {e}")
            raise

    async def rpush(self, key: str, *values: Union[str, bytes, int, float]) -> int:
        """Push elements to end of list."""
        try:
            return await self.client.rpush(key, *values)
        except RedisError as e:
            logger.error(f"Redis RPUSH error for key '{key}': {e}")
            raise

    async def lpush(self, key: str, *values: Union[str, bytes, int, float]) -> int:
        """Push elements to start of list."""
        try:
            return await self.client.lpush(key, *values)
        except RedisError as e:
            logger.error(f"Redis LPUSH error for key '{key}': {e}")
            raise

    async def ltrim(self, key: str, start: int, end: int) -> bool:
        """Trim list to specified range."""
        try:
            return await self.client.ltrim(key, start, end)
        except RedisError as e:
            logger.error(f"Redis LTRIM error for key '{key}': {e}")
            raise

    async def llen(self, key: str) -> int:
        """Get length of list."""
        try:
            return await self.client.llen(key)
        except RedisError as e:
            logger.error(f"Redis LLEN error for key '{key}': {e}")
            raise


# Global Redis client instance
redis_client = RedisClient()