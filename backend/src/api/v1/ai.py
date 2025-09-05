"""AI provider management endpoints."""

from typing import Dict, Any, List, Optional
from datetime import datetime

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from ...database.redis_client import redis_client

router = APIRouter()
logger = structlog.get_logger("ai")


class AIProvider(BaseModel):
    """AI provider configuration model."""
    name: str
    provider_type: str
    api_key_secret: str
    base_url: Optional[str] = None
    model: str
    max_tokens: int = 2048
    temperature: float = 0.7
    enabled: bool = True
    priority: int = 1


class TestRequest(BaseModel):
    """AI provider test request."""
    provider: str
    message: str = "Hello, this is a test message."


@router.get("/providers")
async def list_providers() -> Dict[str, Any]:
    """List all configured AI providers."""
    
    logger.info("AI providers list requested")
    
    try:
        # Get all provider configurations from Redis
        provider_keys = await redis_client.keys("ai:provider:*")
        providers = []
        
        for key in provider_keys:
            provider_data = await redis_client.hgetall(key)
            if provider_data:
                provider_name = key.split(":")[-1]
                providers.append({
                    "name": provider_name,
                    **provider_data
                })
        
        return {
            "providers": providers,
            "count": len(providers)
        }
        
    except Exception as e:
        logger.error("Failed to list AI providers", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve AI providers"
        )


@router.post("/providers")
async def create_provider(provider: AIProvider) -> Dict[str, Any]:
    """Create or update AI provider configuration."""
    
    logger.info("AI provider creation requested", name=provider.name)
    
    try:
        # Store provider configuration in Redis
        provider_key = f"ai:provider:{provider.name}"
        provider_data = {
            "provider_type": provider.provider_type,
            "api_key_secret": provider.api_key_secret,
            "base_url": provider.base_url or "",
            "model": provider.model,
            "max_tokens": str(provider.max_tokens),
            "temperature": str(provider.temperature),
            "enabled": str(provider.enabled),
            "priority": str(provider.priority),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Store all fields as hash
        for field, value in provider_data.items():
            await redis_client.hset(provider_key, field, value)
        
        logger.info("AI provider created", name=provider.name, type=provider.provider_type)
        
        return {
            "success": True,
            "message": f"AI provider '{provider.name}' created successfully",
            "provider": provider_data
        }
        
    except Exception as e:
        logger.error("Failed to create AI provider", error=str(e), name=provider.name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create AI provider"
        )


@router.get("/providers/{provider_name}")
async def get_provider(provider_name: str) -> Dict[str, Any]:
    """Get specific AI provider configuration."""
    
    logger.info("AI provider details requested", name=provider_name)
    
    try:
        provider_key = f"ai:provider:{provider_name}"
        provider_data = await redis_client.hgetall(provider_key)
        
        if not provider_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI provider '{provider_name}' not found"
            )
        
        return {
            "name": provider_name,
            **provider_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get AI provider", error=str(e), name=provider_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve AI provider"
        )


@router.put("/providers/{provider_name}")
async def update_provider(provider_name: str, provider: AIProvider) -> Dict[str, Any]:
    """Update AI provider configuration."""
    
    logger.info("AI provider update requested", name=provider_name)
    
    try:
        provider_key = f"ai:provider:{provider_name}"
        
        # Check if provider exists
        exists = await redis_client.exists(provider_key)
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI provider '{provider_name}' not found"
            )
        
        # Update provider data
        provider_data = {
            "provider_type": provider.provider_type,
            "api_key_secret": provider.api_key_secret,
            "base_url": provider.base_url or "",
            "model": provider.model,
            "max_tokens": str(provider.max_tokens),
            "temperature": str(provider.temperature),
            "enabled": str(provider.enabled),
            "priority": str(provider.priority),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        for field, value in provider_data.items():
            await redis_client.hset(provider_key, field, value)
        
        logger.info("AI provider updated", name=provider_name)
        
        return {
            "success": True,
            "message": f"AI provider '{provider_name}' updated successfully",
            "provider": provider_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update AI provider", error=str(e), name=provider_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update AI provider"
        )


@router.delete("/providers/{provider_name}")
async def delete_provider(provider_name: str) -> Dict[str, Any]:
    """Delete AI provider configuration."""
    
    logger.info("AI provider deletion requested", name=provider_name)
    
    try:
        provider_key = f"ai:provider:{provider_name}"
        deleted = await redis_client.delete(provider_key)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI provider '{provider_name}' not found"
            )
        
        logger.info("AI provider deleted", name=provider_name)
        
        return {
            "success": True,
            "message": f"AI provider '{provider_name}' deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete AI provider", error=str(e), name=provider_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete AI provider"
        )


@router.post("/test")
async def test_provider(test_request: TestRequest) -> Dict[str, Any]:
    """Test AI provider connection and response."""
    
    logger.info("AI provider test requested", provider=test_request.provider)
    
    try:
        # TODO: Implement actual AI provider testing
        # This would use the AI abstraction layer to test the provider
        
        return {
            "success": True,
            "message": f"AI provider '{test_request.provider}' test completed",
            "provider": test_request.provider,
            "test_message": test_request.message,
            "response": "Test response (not implemented)",
            "latency_ms": 250,
            "status": "healthy"
        }
        
    except Exception as e:
        logger.error("AI provider test failed", error=str(e), provider=test_request.provider)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test AI provider '{test_request.provider}'"
        )