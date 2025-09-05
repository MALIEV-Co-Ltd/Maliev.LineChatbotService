"""AI provider manager for handling multiple providers and routing."""

import asyncio
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime

import structlog

from .base import AIProvider, AIMessage, AIResponse, AIConfiguration, AIProviderError
from ..database.redis_client import redis_client
from ..config.settings import settings

logger = structlog.get_logger("ai.manager")


class AIProviderManager:
    """Manages multiple AI providers with routing, fallback, and load balancing."""
    
    def __init__(self):
        """Initialize AI provider manager."""
        self.providers: Dict[str, AIProvider] = {}
        self.primary_provider: Optional[str] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize the AI provider manager."""
        if self._initialized:
            return
        
        logger.info("Initializing AI provider manager")
        
        try:
            # Load providers from Redis configuration
            await self._load_providers_from_redis()
            
            # Set primary provider
            self.primary_provider = settings.primary_ai_provider
            
            # Validate at least one provider is available
            enabled_providers = [p for p in self.providers.values() if p.is_enabled]
            if not enabled_providers:
                logger.warning("No enabled AI providers found")
            else:
                logger.info("AI provider manager initialized", 
                          total_providers=len(self.providers),
                          enabled_providers=len(enabled_providers),
                          primary_provider=self.primary_provider)
            
            self._initialized = True
            
        except Exception as e:
            logger.error("Failed to initialize AI provider manager", error=str(e))
            raise
    
    async def _load_providers_from_redis(self):
        """Load provider configurations from Redis."""
        try:
            provider_keys = await redis_client.keys("ai:provider:*")
            
            for key in provider_keys:
                provider_data = await redis_client.hgetall(key)
                if provider_data:
                    provider_name = key.split(":")[-1]
                    
                    # Create configuration
                    config = AIConfiguration(
                        name=provider_name,
                        provider_type=provider_data.get("provider_type", ""),
                        api_key=await self._get_api_key(provider_data.get("api_key_secret", "")),
                        base_url=provider_data.get("base_url") or None,
                        model=provider_data.get("model", ""),
                        max_tokens=int(provider_data.get("max_tokens", 2048)),
                        temperature=float(provider_data.get("temperature", 0.7)),
                        enabled=provider_data.get("enabled", "false").lower() == "true",
                        priority=int(provider_data.get("priority", 1))
                    )
                    
                    # Create provider instance
                    provider = await self._create_provider(config)
                    if provider and provider.validate_config():
                        self.providers[provider_name] = provider
                        logger.info("Loaded AI provider", name=provider_name, type=config.provider_type)
                    else:
                        logger.warning("Failed to load AI provider", name=provider_name)
                        
        except Exception as e:
            logger.error("Failed to load providers from Redis", error=str(e))
            raise
    
    async def _get_api_key(self, secret_name: str) -> str:
        """Get API key from environment or Secret Manager."""
        # TODO: Implement Secret Manager integration
        # For now, return from environment variables
        
        if secret_name.startswith("env:"):
            # Environment variable
            import os
            env_var = secret_name[4:]  # Remove "env:" prefix
            return os.getenv(env_var, "")
        
        # Direct value (for development)
        return secret_name
    
    async def _create_provider(self, config: AIConfiguration) -> Optional[AIProvider]:
        """Create provider instance based on configuration."""
        try:
            if config.provider_type == "gemini":
                from .providers.gemini import GeminiProvider
                return GeminiProvider(config)
            elif config.provider_type == "openai":
                from .providers.openai import OpenAIProvider
                return OpenAIProvider(config)
            elif config.provider_type == "deepseek":
                from .providers.deepseek import DeepSeekProvider
                return DeepSeekProvider(config)
            else:
                logger.error("Unknown provider type", provider_type=config.provider_type)
                return None
                
        except ImportError as e:
            logger.error("Failed to import provider", provider_type=config.provider_type, error=str(e))
            return None
        except Exception as e:
            logger.error("Failed to create provider", provider_type=config.provider_type, error=str(e))
            return None
    
    def get_provider(self, provider_name: Optional[str] = None) -> Optional[AIProvider]:
        """Get specific provider or primary provider."""
        if provider_name:
            return self.providers.get(provider_name)
        
        # Return primary provider
        if self.primary_provider and self.primary_provider in self.providers:
            provider = self.providers[self.primary_provider]
            if provider.is_enabled:
                return provider
        
        # Fallback to first enabled provider
        for provider in sorted(self.providers.values(), key=lambda p: p.priority, reverse=True):
            if provider.is_enabled:
                return provider
        
        return None
    
    def get_enabled_providers(self) -> List[AIProvider]:
        """Get all enabled providers sorted by priority."""
        enabled = [p for p in self.providers.values() if p.is_enabled]
        return sorted(enabled, key=lambda p: p.priority, reverse=True)
    
    async def generate_response(
        self,
        messages: List[AIMessage],
        provider_name: Optional[str] = None,
        use_fallback: bool = True,
        **kwargs
    ) -> AIResponse:
        """Generate response using specified provider with optional fallback."""
        
        if not self._initialized:
            await self.initialize()
        
        # Determine providers to try
        if provider_name:
            providers_to_try = [self.get_provider(provider_name)]
        else:
            providers_to_try = [self.get_provider()]  # Primary provider
            
            if use_fallback and settings.enable_fallback_providers:
                # Add other enabled providers as fallback
                fallback_providers = [p for p in self.get_enabled_providers() 
                                    if p.name != (providers_to_try[0].name if providers_to_try[0] else "")]
                providers_to_try.extend(fallback_providers)
        
        # Filter None providers
        providers_to_try = [p for p in providers_to_try if p is not None]
        
        if not providers_to_try:
            raise AIProviderError("No available AI providers", "manager")
        
        last_error = None
        
        for provider in providers_to_try:
            try:
                logger.info("Attempting AI request", provider=provider.name, model=provider.model)
                
                start_time = datetime.utcnow()
                response = await provider.generate_response(messages, **kwargs)
                end_time = datetime.utcnow()
                
                # Add response time to metadata
                response.response_time_ms = (end_time - start_time).total_seconds() * 1000
                
                logger.info("AI request successful", 
                          provider=provider.name, 
                          response_time_ms=response.response_time_ms,
                          tokens_used=response.usage.get("total_tokens", 0))
                
                # Record success metric
                await self._record_metric("success", provider.name, response.response_time_ms)
                
                return response
                
            except Exception as e:
                last_error = e
                logger.warning("AI provider failed", provider=provider.name, error=str(e))
                
                # Record failure metric
                await self._record_metric("error", provider.name, 0, str(e))
                
                if not use_fallback:
                    break
        
        # All providers failed
        error_msg = f"All AI providers failed. Last error: {str(last_error)}"
        logger.error(error_msg)
        raise AIProviderError(error_msg, "manager")
    
    async def generate_stream_response(
        self,
        messages: List[AIMessage],
        provider_name: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response using specified provider."""
        
        if not self._initialized:
            await self.initialize()
        
        provider = self.get_provider(provider_name)
        if not provider:
            raise AIProviderError("No available AI provider for streaming", "manager")
        
        try:
            logger.info("Starting streaming AI request", provider=provider.name)
            
            async for chunk in provider.generate_stream_response(messages, **kwargs):
                yield chunk
                
        except Exception as e:
            logger.error("Streaming AI request failed", provider=provider.name, error=str(e))
            await self._record_metric("stream_error", provider.name, 0, str(e))
            raise
    
    async def health_check_all(self) -> Dict[str, Any]:
        """Check health of all providers."""
        if not self._initialized:
            await self.initialize()
        
        results = {}
        
        for name, provider in self.providers.items():
            try:
                healthy = await provider.health_check()
                results[name] = {
                    "healthy": healthy,
                    "enabled": provider.is_enabled,
                    "provider_type": provider.provider_type,
                    "model": provider.model,
                    "priority": provider.priority
                }
            except Exception as e:
                results[name] = {
                    "healthy": False,
                    "enabled": provider.is_enabled,
                    "error": str(e)
                }
        
        return results
    
    async def reload_providers(self):
        """Reload providers from Redis configuration."""
        logger.info("Reloading AI providers")
        
        try:
            # Clear existing providers
            self.providers.clear()
            
            # Reload from Redis
            await self._load_providers_from_redis()
            
            logger.info("AI providers reloaded", count=len(self.providers))
            
        except Exception as e:
            logger.error("Failed to reload AI providers", error=str(e))
            raise
    
    async def _record_metric(self, metric_type: str, provider: str, response_time: float, error: str = ""):
        """Record metric for monitoring."""
        try:
            timestamp = datetime.utcnow().isoformat()
            metric_key = f"metric:ai:{metric_type}:{timestamp}"
            
            metric_data = {
                "provider": provider,
                "response_time_ms": str(response_time),
                "timestamp": timestamp,
                "error": error
            }
            
            for field, value in metric_data.items():
                await redis_client.hset(metric_key, field, value)
            
            # Set expiration (7 days)
            await redis_client.expire(metric_key, 7 * 24 * 60 * 60)
            
        except Exception as e:
            logger.warning("Failed to record AI metric", error=str(e))


# Global AI provider manager instance
ai_manager = AIProviderManager()