"""Global test configuration and fixtures."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from typing import AsyncGenerator, Generator
import fakeredis.aioredis as fakeredis
from testcontainers.redis import RedisContainer
import redis.asyncio as redis

from src.config.settings import Settings


# Test settings override
@pytest.fixture
def test_settings():
    """Override settings for testing."""
    return Settings(
        environment="test",
        debug=True,
        redis_url="redis://localhost:6379/15",  # Test database
        log_level="DEBUG",
        # Disable external services for testing
        google_cloud_project=None,
        line_channel_access_token="test-token",
        line_channel_secret="test-secret",
        gemini_api_key="test-gemini-key",
    )


# Unit test fixtures (fast, isolated)
@pytest.fixture
async def fake_redis() -> AsyncGenerator[fakeredis.FakeRedis, None]:
    """Fake Redis for unit tests - fast and isolated."""
    fake_client = fakeredis.FakeRedis(decode_responses=True)
    yield fake_client
    await fake_client.flushall()
    await fake_client.aclose()


@pytest.fixture
def mock_redis() -> MagicMock:
    """Mocked Redis for pure unit tests."""
    mock = AsyncMock()
    # Setup common mock behaviors
    mock.get.return_value = None
    mock.set.return_value = True
    mock.exists.return_value = False
    return mock


# Component test fixtures (real Redis via containers)
@pytest.fixture(scope="session")
def redis_container() -> Generator[RedisContainer, None, None]:
    """Real Redis container for component tests."""
    with RedisContainer("redis:7-alpine") as container:
        yield container


@pytest.fixture
async def real_redis(redis_container) -> AsyncGenerator[redis.Redis, None]:
    """Real Redis connection for component tests."""
    client = redis.from_url(redis_container.get_connection_url())
    await client.flushall()  # Clean slate
    yield client
    await client.flushall()  # Cleanup
    await client.aclose()


# Smoke test fixtures (external services)
@pytest.fixture
async def smoke_redis() -> AsyncGenerator[redis.Redis, None]:
    """Redis for smoke tests - assumes real Redis running locally."""
    try:
        client = redis.from_url("redis://localhost:6379/15")
        await client.ping()  # Test connection
        await client.flushdb()  # Clean test database
        yield client
        await client.flushdb()  # Cleanup
        await client.aclose()
    except Exception as e:
        pytest.skip(f"Redis not available for smoke tests: {e}")


# Mock fixtures for external services
@pytest.fixture
def mock_line_client():
    """Mock LINE client for testing."""
    mock = AsyncMock()
    mock.send_reply_message.return_value = True
    mock.send_push_message.return_value = True
    mock.get_profile.return_value = {
        "displayName": "Test User",
        "userId": "test-user-id",
        "pictureUrl": "https://example.com/picture.jpg"
    }
    return mock


@pytest.fixture
def mock_ai_provider():
    """Mock AI provider for testing."""
    mock = AsyncMock()
    mock.generate_response.return_value = "Test AI response"
    mock.is_available.return_value = True
    mock.get_usage_stats.return_value = {
        "requests": 0,
        "tokens": 0,
        "cost": 0.0
    }
    return mock


# Event loop configuration for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# Test markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.component = pytest.mark.component  
pytest.mark.smoke = pytest.mark.smoke
pytest.mark.slow = pytest.mark.slow
pytest.mark.integration = pytest.mark.integration