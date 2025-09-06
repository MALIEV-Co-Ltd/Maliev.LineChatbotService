"""Test configuration and settings."""

import pytest
from src.config.settings import Settings


class TestSettings:
    """Test settings configuration."""
    
    def test_default_settings(self):
        """Test default settings are loaded correctly."""
        settings = Settings()
        
        assert settings.app_name == "Maliev LINE Chatbot Service"
        assert settings.version == "1.0.0"
        assert settings.environment == "development"
        assert settings.debug is True
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        
    def test_redis_settings(self):
        """Test Redis configuration."""
        settings = Settings()
        
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.redis_max_connections == 20
        assert settings.redis_retry_on_timeout is True
        
    def test_cors_settings(self):
        """Test CORS configuration."""
        settings = Settings()
        
        assert "http://localhost:3000" in settings.cors_origins
        assert "http://127.0.0.1:3000" in settings.cors_origins
        assert settings.cors_allow_credentials is True