"""Component tests for Redis integration using real Redis container."""

import pytest
from src.database.redis_client import RedisClient


@pytest.mark.component
@pytest.mark.slow
class TestRedisIntegration:
    """Component tests with real Redis - tests full integration."""
    
    @pytest.fixture
    async def redis_client_real(self, real_redis):
        """Redis client connected to real Redis container."""
        client = RedisClient()
        client.client = real_redis
        client._connected = True
        return client
    
    @pytest.mark.asyncio
    async def test_connection_and_basic_operations(self, redis_client_real):
        """Test actual Redis connection and operations."""
        # Test connection
        result = await redis_client_real.ping()
        assert result is True
        
        # Test basic operations
        await redis_client_real.set("integration_test", "success")
        result = await redis_client_real.get("integration_test")
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_complex_data_structures(self, redis_client_real):
        """Test complex Redis data structures."""
        # Hash operations
        hash_data = {
            "user_id": "user123",
            "name": "John Doe", 
            "email": "john@example.com",
            "created_at": "2024-01-01T00:00:00Z"
        }
        
        for field, value in hash_data.items():
            await redis_client_real.hset("user:123", field, value)
        
        stored_data = await redis_client_real.hgetall("user:123")
        assert stored_data == hash_data
        
        # List operations
        conversation_history = [
            "Hello, how can I help you?",
            "I need help with 3D printing",
            "Sure! What specific aspect?",
            "Material recommendations"
        ]
        
        for message in conversation_history:
            await redis_client_real.rpush("conversation:123", message)
        
        stored_history = await redis_client_real.lrange("conversation:123", 0, -1)
        assert stored_history == conversation_history
    
    @pytest.mark.asyncio
    async def test_conversation_storage_workflow(self, redis_client_real):
        """Test realistic conversation storage workflow."""
        user_id = "user_789"
        conversation_key = f"conversation:{user_id}"
        
        # Store conversation messages
        messages = [
            '{"role": "user", "content": "Hello"}',
            '{"role": "assistant", "content": "Hi! How can I help?"}',
            '{"role": "user", "content": "Tell me about 3D printing"}',
            '{"role": "assistant", "content": "3D printing is an additive manufacturing process..."}'
        ]
        
        for message in messages:
            await redis_client_real.rpush(conversation_key, message)
        
        # Limit conversation history (keep last 10)
        await redis_client_real.ltrim(conversation_key, -10, -1)
        
        # Verify storage
        stored_messages = await redis_client_real.lrange(conversation_key, 0, -1)
        assert len(stored_messages) == len(messages)
        assert stored_messages == messages
        
        # Update user statistics
        stats_key = f"user_stats:{user_id}"
        await redis_client_real.hincrby(stats_key, "message_count", len(messages))
        await redis_client_real.hincrby(stats_key, "conversation_count", 1)
        
        stats = await redis_client_real.hgetall(stats_key)
        assert int(stats["message_count"]) == len(messages)
        assert int(stats["conversation_count"]) == 1
    
    @pytest.mark.asyncio
    async def test_cache_workflow(self, redis_client_real):
        """Test LLM response caching workflow."""
        # Simulate caching AI responses
        query_hash = "hash_of_user_query_123"
        cache_key = f"llm_cache:exact:{query_hash}"
        
        response_data = {
            "response": "This is a cached AI response about 3D printing materials.",
            "provider": "gemini",
            "model": "gemini-2.0-flash-exp",
            "timestamp": "2024-01-01T12:00:00Z",
            "tokens_used": 150,
            "cost": 0.002
        }
        
        # Store cache entry with TTL (7 days)
        import json
        await redis_client_real.set(
            cache_key, 
            json.dumps(response_data),
            ex=7 * 24 * 60 * 60  # 7 days
        )
        
        # Retrieve and verify
        cached_response = await redis_client_real.get(cache_key)
        assert cached_response is not None
        
        parsed_response = json.loads(cached_response)
        assert parsed_response == response_data
        
        # Test cache hit statistics
        stats_key = "cache:stats"
        await redis_client_real.hincrby(stats_key, "hits", 1)
        await redis_client_real.hincrby(stats_key, "total_requests", 1)
        
        stats = await redis_client_real.hgetall(stats_key)
        assert int(stats["hits"]) == 1
        assert int(stats["total_requests"]) == 1
    
    @pytest.mark.asyncio
    async def test_customer_profile_storage(self, redis_client_real):
        """Test customer profile management workflow."""
        customer_id = "customer_456"
        profile_key = f"customer:{customer_id}"
        
        # Store customer profile
        profile_data = {
            "user_id": customer_id,
            "name": "Jane Smith",
            "email": "jane.smith@example.com", 
            "phone": "+1234567890",
            "company": "Smith Manufacturing",
            "industry": "Automotive",
            "preferences": '{"material": "PLA", "color": "black"}',
            "first_contact": "2024-01-01T10:00:00Z",
            "last_interaction": "2024-01-15T14:30:00Z",
            "total_orders": "5",
            "total_spent": "2500.00",
            "vip_status": "true"
        }
        
        for field, value in profile_data.items():
            await redis_client_real.hset(profile_key, field, value)
        
        # Verify storage
        stored_profile = await redis_client_real.hgetall(profile_key)
        assert stored_profile == profile_data
        
        # Update interaction timestamp
        import time
        current_timestamp = str(int(time.time()))
        await redis_client_real.hset(profile_key, "last_interaction", current_timestamp)
        
        updated_timestamp = await redis_client_real.hget(profile_key, "last_interaction")
        assert updated_timestamp == current_timestamp
    
    @pytest.mark.asyncio
    async def test_error_resilience(self, redis_client_real):
        """Test Redis client error handling and resilience."""
        # Test with very large data
        large_data = "x" * 10000  # 10KB string
        await redis_client_real.set("large_key", large_data)
        result = await redis_client_real.get("large_key")
        assert result == large_data
        
        # Test with special characters
        special_data = "Hello 世界! 🤖 Special chars: @#$%^&*()"
        await redis_client_real.set("special_key", special_data)
        result = await redis_client_real.get("special_key")
        assert result == special_data
        
        # Test concurrent operations
        import asyncio
        
        async def concurrent_set(key_suffix, value):
            await redis_client_real.set(f"concurrent_{key_suffix}", value)
            return await redis_client_real.get(f"concurrent_{key_suffix}")
        
        tasks = [concurrent_set(i, f"value_{i}") for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        for i, result in enumerate(results):
            assert result == f"value_{i}"