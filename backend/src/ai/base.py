"""Base AI provider interface and common functionality."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime

import structlog

logger = structlog.get_logger("ai.base")


@dataclass
class AIMessage:
    """Represents a message in the conversation."""
    role: str  # system, user, assistant
    content: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class AIResponse:
    """Response from AI provider."""
    content: str
    provider: str
    model: str
    usage: Dict[str, int]  # tokens, etc.
    metadata: Dict[str, Any]
    finish_reason: Optional[str] = None
    response_time_ms: Optional[float] = None


@dataclass
class AIConfiguration:
    """AI provider configuration."""
    name: str
    provider_type: str
    api_key: str
    base_url: Optional[str] = None
    model: str = ""
    max_tokens: int = 65536
    temperature: float = 0.7
    enabled: bool = True
    priority: int = 1
    timeout_seconds: int = 30
    retry_attempts: int = 3
    additional_params: Dict[str, Any] = None


class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, config: AIConfiguration):
        """Initialize AI provider with configuration."""
        self.config = config
        self.logger = structlog.get_logger(f"ai.{config.provider_type}")
        
    @property
    def name(self) -> str:
        """Get provider name."""
        return self.config.name
    
    @property
    def provider_type(self) -> str:
        """Get provider type."""
        return self.config.provider_type
    
    @property
    def model(self) -> str:
        """Get model name."""
        return self.config.model
    
    @property
    def is_enabled(self) -> bool:
        """Check if provider is enabled."""
        return self.config.enabled
    
    @property
    def priority(self) -> int:
        """Get provider priority."""
        return self.config.priority
    
    @abstractmethod
    async def generate_response(
        self,
        messages: List[AIMessage],
        **kwargs
    ) -> AIResponse:
        """Generate response from AI provider."""
        pass
    
    @abstractmethod
    async def generate_stream_response(
        self,
        messages: List[AIMessage],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response from AI provider."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is healthy and responsive."""
        pass
    
    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for given text."""
        pass
    
    def validate_config(self) -> bool:
        """Validate provider configuration."""
        if not self.config.api_key:
            self.logger.error("Missing API key", provider=self.name)
            return False
        
        if not self.config.model:
            self.logger.error("Missing model configuration", provider=self.name)
            return False
        
        if self.config.temperature < 0 or self.config.temperature > 2:
            self.logger.error("Invalid temperature value", temperature=self.config.temperature)
            return False
        
        if self.config.max_tokens <= 0:
            self.logger.error("Invalid max_tokens value", max_tokens=self.config.max_tokens)
            return False
        
        return True
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test connection to AI provider."""
        try:
            start_time = datetime.utcnow()
            
            # Test with simple message
            test_messages = [
                AIMessage(role="user", content="Hello, this is a test message.")
            ]
            
            response = await self.generate_response(test_messages)
            
            end_time = datetime.utcnow()
            response_time = (end_time - start_time).total_seconds() * 1000
            
            return {
                "success": True,
                "provider": self.name,
                "model": self.model,
                "response_time_ms": response_time,
                "response_content": response.content[:100] + "..." if len(response.content) > 100 else response.content,
                "usage": response.usage,
                "timestamp": end_time.isoformat()
            }
            
        except Exception as e:
            self.logger.error("Connection test failed", provider=self.name, error=str(e))
            return {
                "success": False,
                "provider": self.name,
                "model": self.model,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def prepare_messages(self, messages: List[AIMessage]) -> List[Dict[str, Any]]:
        """Prepare messages for API call (can be overridden by providers)."""
        return [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in messages
        ]
    
    def create_response(
        self,
        content: str,
        usage: Dict[str, int],
        finish_reason: Optional[str] = None,
        response_time_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AIResponse:
        """Create standardized AI response."""
        return AIResponse(
            content=content,
            provider=self.name,
            model=self.model,
            usage=usage,
            metadata=metadata or {},
            finish_reason=finish_reason,
            response_time_ms=response_time_ms
        )


class AIProviderError(Exception):
    """Base exception for AI provider errors."""
    
    def __init__(self, message: str, provider: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.provider = provider
        self.error_code = error_code


class AIProviderTimeoutError(AIProviderError):
    """Exception for AI provider timeouts."""
    pass


class AIProviderQuotaError(AIProviderError):
    """Exception for AI provider quota/rate limit errors."""
    pass


class AIProviderAuthError(AIProviderError):
    """Exception for AI provider authentication errors."""
    pass