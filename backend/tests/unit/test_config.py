"""Unit tests for configuration and settings."""

import pytest
import os
from unittest.mock import patch
from src.config.settings import Settings


@pytest.mark.unit
class TestSettingsUnit:
    """Unit tests for settings configuration."""
    
    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        
        assert settings.app_name == "Maliev LINE Chatbot Service"
        assert settings.version == "1.0.0"
        assert settings.environment == "development"
        assert settings.debug is True
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.log_level == "INFO"
    
    def test_redis_default_config(self):
        """Test Redis default configuration."""
        settings = Settings()
        
        assert settings.redis_url == "redis://localhost:6379/0"
        assert settings.redis_max_connections == 20
        assert settings.redis_retry_on_timeout is True
    
    def test_ai_provider_defaults(self):
        """Test AI provider default settings."""
        settings = Settings()
        
        assert settings.primary_ai_provider == "gemini"
        assert settings.enable_fallback_providers is True
        assert settings.max_tokens_default == 2048
        assert settings.temperature_default == 0.7
    
    def test_cache_settings(self):
        """Test cache configuration."""
        settings = Settings()
        
        assert settings.enable_caching is True
        assert settings.cache_ttl_seconds == 604800  # 7 days
        assert settings.cache_max_entries == 10000
        assert settings.semantic_similarity_threshold == 0.85
    
    def test_security_settings(self):
        """Test security configuration."""
        settings = Settings()
        
        assert settings.jwt_secret_key == "dev-secret-key-change-in-production"
        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_access_token_expire_minutes == 1440  # 24 hours
    
    def test_cors_settings(self):
        """Test CORS configuration."""
        settings = Settings()
        
        assert "http://localhost:3000" in settings.cors_origins
        assert "http://127.0.0.1:3000" in settings.cors_origins
        assert settings.cors_allow_credentials is True
        assert settings.cors_allow_methods == ["*"]
        assert settings.cors_allow_headers == ["*"]
    
    @patch.dict(os.environ, {
        'ENVIRONMENT': 'production',
        'DEBUG': 'false',
        'REDIS_URL': 'redis://prod-redis:6379/0',
        'GEMINI_API_KEY': 'prod-gemini-key',
        'PRIMARY_AI_PROVIDER': 'openai'
    })
    def test_environment_variable_override(self):
        """Test settings override from environment variables."""
        settings = Settings()
        
        assert settings.environment == "production"
        assert settings.debug is False
        assert settings.redis_url == "redis://prod-redis:6379/0"
        assert settings.gemini_api_key == "prod-gemini-key"
        assert settings.primary_ai_provider == "openai"
    
    def test_customer_management_settings(self):
        """Test customer management configuration."""
        settings = Settings()
        
        assert settings.enable_customer_management is True
        assert settings.auto_extract_customer_info is True
        assert settings.customer_data_retention_days == 2555  # ~7 years
    
    def test_monitoring_settings(self):
        """Test monitoring and analytics configuration."""
        settings = Settings()
        
        assert settings.enable_analytics is True
        assert settings.metrics_enabled is True
        assert settings.structured_logging is True
        assert settings.health_check_interval == 30