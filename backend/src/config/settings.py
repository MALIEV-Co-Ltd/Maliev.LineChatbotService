"""Application configuration and settings using Pydantic Settings."""


from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application Settings
    app_name: str = "Maliev LINE Chatbot Service"
    version: str = "1.0.0"
    environment: str = Field(default="development", description="Environment: development, staging, production")
    debug: bool = Field(default=True, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Server Settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    reload: bool = Field(default=True, description="Auto-reload on changes")

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    redis_max_connections: int = Field(default=20, description="Redis connection pool size")
    redis_retry_on_timeout: bool = Field(default=True, description="Retry Redis operations on timeout")

    # Google Cloud Settings
    google_cloud_project: str | None = Field(default=None, description="GCP project ID")
    google_application_credentials: str | None = Field(
        default=None, description="Path to GCP service account JSON"
    )

    # API Keys (for development - production uses Secret Manager)
    line_channel_access_token: str | None = Field(default=None, description="LINE channel access token")
    line_channel_secret: str | None = Field(default=None, description="LINE channel secret")
    gemini_api_key: str | None = Field(default=None, description="Gemini API key")
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")

    # Security Settings
    jwt_secret_key: str = Field(default="dev-secret-key-change-in-production", description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_access_token_expire_minutes: int = Field(default=1440, description="JWT token expiration (minutes)")

    # Admin UI Settings
    admin_username: str = Field(default="admin", description="Default admin username")
    admin_password: str = Field(default="admin123", description="Default admin password")

    # Application URLs
    webhook_url: str | None = Field(default=None, description="LINE webhook URL")
    admin_ui_url: str = Field(default="http://localhost:3000", description="Admin UI URL")

    # CORS Settings
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins"
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow CORS credentials")
    cors_allow_methods: list[str] = Field(default=["*"], description="Allowed CORS methods")
    cors_allow_headers: list[str] = Field(default=["*"], description="Allowed CORS headers")

    # Feature Flags
    enable_caching: bool = Field(default=True, description="Enable LLM caching")
    enable_analytics: bool = Field(default=True, description="Enable analytics")
    enable_customer_management: bool = Field(default=True, description="Enable customer management")
    enable_instruction_system: bool = Field(default=True, description="Enable dynamic instructions")

    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")
    rate_limit_burst: int = Field(default=10, description="Rate limit burst")

    # Cache Settings
    cache_ttl_seconds: int = Field(default=604800, description="Default cache TTL (7 days)")
    cache_max_entries: int = Field(default=10000, description="Maximum cache entries")
    semantic_similarity_threshold: float = Field(
        default=0.85, description="Semantic similarity threshold"
    )

    # Customer Management
    customer_data_retention_days: int = Field(default=2555, description="Customer data retention (7 years)")
    auto_extract_customer_info: bool = Field(default=True, description="Auto-extract customer info")

    # AI Provider Settings
    primary_ai_provider: str = Field(default="gemini", description="Primary AI provider")
    enable_fallback_providers: bool = Field(default=True, description="Enable fallback providers")
    max_tokens_default: int = Field(default=2048, description="Default max tokens")
    temperature_default: float = Field(default=0.7, description="Default temperature")
    max_instruction_tokens: int = Field(default=2000, description="Max tokens for instructions")

    # Monitoring and Health Checks
    health_check_interval: int = Field(default=30, description="Health check interval (seconds)")
    metrics_enabled: bool = Field(default=True, description="Enable metrics collection")
    structured_logging: bool = Field(default=True, description="Enable structured logging")

    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        """Validate environment setting."""
        allowed = ["development", "staging", "production"]
        if v.lower() not in allowed:
            raise ValueError(f"Environment must be one of: {allowed}")
        return v.lower()

    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        """Validate log level setting."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of: {allowed}")
        return v.upper()

    @validator("semantic_similarity_threshold")
    def validate_similarity_threshold(cls, v: float) -> float:
        """Validate semantic similarity threshold."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Semantic similarity threshold must be between 0.0 and 1.0")
        return v

    @validator("temperature_default")
    def validate_temperature(cls, v: float) -> float:
        """Validate default temperature setting."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    def get_redis_config(self) -> dict:
        """Get Redis configuration dictionary."""
        return {
            "url": self.redis_url,
            "max_connections": self.redis_max_connections,
            "retry_on_timeout": self.redis_retry_on_timeout,
            "decode_responses": True,
            "encoding": "utf-8",
        }

    def get_cors_config(self) -> dict:
        """Get CORS configuration dictionary."""
        return {
            "allow_origins": self.cors_origins,
            "allow_credentials": self.cors_allow_credentials,
            "allow_methods": self.cors_allow_methods,
            "allow_headers": self.cors_allow_headers,
        }


# Global settings instance
settings = Settings()
