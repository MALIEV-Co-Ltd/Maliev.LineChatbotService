"""Unit tests for Redis client using fake Redis."""

import pytest
from src.database.redis_client import RedisClient


@pytest.mark.unit
class TestRedisClientUnit:
    """Unit tests for Redis client - isolated and fast."""
    
    @pytest.fixture
    async def redis_client(self, fake_redis):
        """Redis client with fake Redis."""
        client = RedisClient()
        client._client = fake_redis
        client._connected = True
        return client
    
    @pytest.mark.asyncio
    async def test_basic_get_set(self, redis_client):
        """Test basic get/set operations."""
        # Test set
        result = await redis_client.set("test_key", "test_value")
        assert result is True
        
        # Test get
        result = await redis_client.get("test_key")
        assert result == "test_value"
        
        # Test get non-existent key
        result = await redis_client.get("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_hash_operations(self, redis_client):
        """Test hash field operations."""
        # Test hset
        result = await redis_client.hset("test_hash", "field1", "value1")
        assert result >= 0  # Returns number of fields added
        
        # Test hget
        result = await redis_client.hget("test_hash", "field1")
        assert result == "value1"
        
        # Test hgetall
        await redis_client.hset("test_hash", "field2", "value2")
        result = await redis_client.hgetall("test_hash")
        assert result == {"field1": "value1", "field2": "value2"}
        
        # Test hincrby
        await redis_client.hset("test_hash", "counter", "5")
        result = await redis_client.hincrby("test_hash", "counter", 3)
        assert result == 8
    
    @pytest.mark.asyncio
    async def test_list_operations(self, redis_client):
        """Test list operations."""
        # Test rpush
        result = await redis_client.rpush("test_list", "item1", "item2", "item3")
        assert result == 3
        
        # Test lrange
        result = await redis_client.lrange("test_list", 0, -1)
        assert result == ["item1", "item2", "item3"]
        
        # Test lpush
        result = await redis_client.lpush("test_list", "item0")
        assert result == 4
        
        # Test llen
        result = await redis_client.llen("test_list")
        assert result == 4
        
        # Test ltrim
        await redis_client.ltrim("test_list", 0, 2)
        result = await redis_client.llen("test_list")
        assert result == 3
    
    @pytest.mark.asyncio
    async def test_expiration(self, redis_client):
        """Test key expiration."""
        # Set with expiration
        await redis_client.set("expire_key", "value", ex=1)
        
        # Check exists
        result = await redis_client.exists("expire_key")
        assert result == 1
        
        # Check TTL
        ttl = await redis_client.ttl("expire_key")
        assert ttl > 0
    
    @pytest.mark.asyncio
    async def test_delete_operations(self, redis_client):
        """Test delete operations."""
        # Set up test data
        await redis_client.set("key1", "value1")
        await redis_client.set("key2", "value2")
        await redis_client.hset("hash1", "field1", "value1")
        
        # Test single delete
        result = await redis_client.delete("key1")
        assert result == 1
        
        # Verify deletion
        result = await redis_client.get("key1")
        assert result is None
        
        # Test multiple delete
        result = await redis_client.delete("key2", "hash1", "nonexistent")
        assert result == 2  # Only key2 and hash1 existed