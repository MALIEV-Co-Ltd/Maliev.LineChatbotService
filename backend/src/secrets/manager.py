"""Secret Manager integration for secure configuration management."""

import os
import json
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta

import structlog

# Optional Google Cloud dependencies for development
try:
    from google.cloud import secretmanager_v1 as secretmanager
    from google.api_core import exceptions as gcp_exceptions
    HAS_GCP = True
except ImportError:
    try:
        from google.cloud import secretmanager
        from google.api_core import exceptions as gcp_exceptions
        HAS_GCP = True
    except ImportError:
        secretmanager = None
        gcp_exceptions = None
        HAS_GCP = False

from ..config.settings import settings
from ..database.redis_client import redis_client

logger = structlog.get_logger("secrets")


class SecretManager:
    """Manages secrets from Google Secret Manager with Redis caching."""
    
    def __init__(self):
        """Initialize Secret Manager client."""
        self._client: Optional[secretmanager.SecretManagerServiceClient] = None
        self._project_id = settings.google_cloud_project
        self._initialized = False
        self._cache_ttl = 3600  # 1 hour cache TTL
        
    async def initialize(self):
        """Initialize the Secret Manager client."""
        if self._initialized:
            return
        
        try:
            if not self._project_id:
                logger.warning("Google Cloud project not configured, using environment variables only")
                self._initialized = True
                return
            
            # Initialize Google Cloud Secret Manager client
            if settings.google_application_credentials:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.google_application_credentials
            
            self._client = secretmanager.SecretManagerServiceClient()
            
            logger.info("Secret Manager initialized", project_id=self._project_id)
            self._initialized = True
            
        except Exception as e:
            logger.error("Failed to initialize Secret Manager", error=str(e))
            # Continue without Secret Manager for development
            self._initialized = True
    
    async def get_secret(self, secret_name: str, use_cache: bool = True) -> Optional[str]:
        """Get secret value with caching."""
        
        if not self._initialized:
            await self.initialize()
        
        # Check cache first
        if use_cache:
            cached_value = await self._get_cached_secret(secret_name)
            if cached_value is not None:
                return cached_value
        
        # Get secret from source
        secret_value = await self._get_secret_from_source(secret_name)
        
        # Cache the secret if obtained
        if secret_value and use_cache:
            await self._cache_secret(secret_name, secret_value)
        
        return secret_value
    
    async def _get_secret_from_source(self, secret_name: str) -> Optional[str]:
        """Get secret from appropriate source (GCP Secret Manager or environment)."""
        
        # Handle environment variable references
        if secret_name.startswith("env:"):
            env_var = secret_name[4:]  # Remove "env:" prefix
            value = os.getenv(env_var)
            if value:
                logger.debug("Retrieved secret from environment", secret_name=secret_name)
                return value
            else:
                logger.warning("Environment variable not found", env_var=env_var)
                return None
        
        # Handle direct values (for development)
        if not secret_name.startswith("projects/"):
            # Assume it's a direct value if not a GCP resource name
            return secret_name
        
        # Get from Google Secret Manager
        if not self._client or not self._project_id:
            logger.warning("Secret Manager not available", secret_name=secret_name)
            return None
        
        try:
            # Construct the resource name
            if not secret_name.startswith("projects/"):
                name = f"projects/{self._project_id}/secrets/{secret_name}/versions/latest"
            else:
                name = secret_name
            
            response = self._client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            
            logger.debug("Retrieved secret from GCP Secret Manager", secret_name=secret_name)
            return secret_value
            
        except gcp_exceptions.NotFound:
            logger.warning("Secret not found in Secret Manager", secret_name=secret_name)
            return None
        except gcp_exceptions.PermissionDenied:
            logger.error("Permission denied accessing secret", secret_name=secret_name)
            return None
        except Exception as e:
            logger.error("Failed to retrieve secret", secret_name=secret_name, error=str(e))
            return None
    
    async def _get_cached_secret(self, secret_name: str) -> Optional[str]:
        """Get secret from Redis cache."""
        try:
            cache_key = f"secret:{secret_name}"
            cached_data = await redis_client.hgetall(cache_key)
            
            if not cached_data:
                return None
            
            # Check expiration
            expires_at = datetime.fromisoformat(cached_data.get("expires_at", ""))
            if datetime.utcnow() > expires_at:
                # Expired, remove from cache
                await redis_client.delete(cache_key)
                return None
            
            logger.debug("Retrieved secret from cache", secret_name=secret_name)
            return cached_data.get("value")
            
        except Exception as e:
            logger.warning("Failed to retrieve secret from cache", secret_name=secret_name, error=str(e))
            return None
    
    async def _cache_secret(self, secret_name: str, secret_value: str):
        """Cache secret in Redis with expiration."""
        try:
            cache_key = f"secret:{secret_name}"
            expires_at = datetime.utcnow() + timedelta(seconds=self._cache_ttl)
            
            await redis_client.hset(cache_key, "value", secret_value)
            await redis_client.hset(cache_key, "expires_at", expires_at.isoformat())
            await redis_client.hset(cache_key, "cached_at", datetime.utcnow().isoformat())
            
            # Set Redis expiration
            await redis_client.expire(cache_key, self._cache_ttl)
            
            logger.debug("Cached secret", secret_name=secret_name, expires_at=expires_at.isoformat())
            
        except Exception as e:
            logger.warning("Failed to cache secret", secret_name=secret_name, error=str(e))
    
    async def invalidate_cache(self, secret_name: Optional[str] = None):
        """Invalidate secret cache."""
        try:
            if secret_name:
                # Invalidate specific secret
                cache_key = f"secret:{secret_name}"
                await redis_client.delete(cache_key)
                logger.info("Invalidated secret cache", secret_name=secret_name)
            else:
                # Invalidate all secrets
                secret_keys = await redis_client.keys("secret:*")
                if secret_keys:
                    await redis_client.delete(*secret_keys)
                logger.info("Invalidated all secret caches", count=len(secret_keys))
                
        except Exception as e:
            logger.error("Failed to invalidate secret cache", error=str(e))
    
    async def get_configuration(self, config_section: str = "app") -> Dict[str, Any]:
        """Get complete configuration section with secret resolution."""
        
        try:
            # Get configuration from Redis
            config_pattern = f"config:{config_section}:*"
            config_keys = await redis_client.keys(config_pattern)
            
            configuration = {}
            
            for key in config_keys:
                config_value = await redis_client.get(key)
                config_name = key.split(":")[-1]
                
                # Check if value is a secret reference
                if config_value and (config_value.startswith("env:") or 
                                   config_value.startswith("projects/") or
                                   config_value.startswith("secret:")):
                    
                    # Resolve secret
                    secret_value = await self.get_secret(config_value)
                    configuration[config_name] = secret_value
                else:
                    configuration[config_name] = config_value
            
            return configuration
            
        except Exception as e:
            logger.error("Failed to get configuration", section=config_section, error=str(e))
            return {}
    
    async def update_configuration(self, config_section: str, config_key: str, config_value: str):
        """Update configuration in Redis."""
        
        try:
            redis_key = f"config:{config_section}:{config_key}"
            await redis_client.set(redis_key, config_value)
            
            logger.info("Configuration updated", section=config_section, key=config_key)
            
            # If this is a secret reference, invalidate related cache
            if config_value.startswith(("env:", "projects/", "secret:")):
                await self.invalidate_cache(config_value)
            
        except Exception as e:
            logger.error("Failed to update configuration", 
                        section=config_section, key=config_key, error=str(e))
            raise
    
    async def create_secret(self, secret_id: str, secret_value: str, labels: Optional[Dict[str, str]] = None) -> bool:
        """Create a new secret in Google Secret Manager."""
        
        if not self._client or not self._project_id:
            logger.error("Secret Manager not available for secret creation")
            return False
        
        try:
            parent = f"projects/{self._project_id}"
            
            # Create the secret
            secret = {
                "replication": {"automatic": {}},
                "labels": labels or {}
            }
            
            response = self._client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": secret
                }
            )
            
            # Add the secret version
            version_response = self._client.add_secret_version(
                request={
                    "parent": response.name,
                    "payload": {"data": secret_value.encode("UTF-8")}
                }
            )
            
            logger.info("Secret created", secret_id=secret_id, version=version_response.name)
            return True
            
        except Exception as e:
            logger.error("Failed to create secret", secret_id=secret_id, error=str(e))
            return False
    
    async def list_secrets(self) -> Dict[str, Any]:
        """List all secrets in the project."""
        
        if not self._client or not self._project_id:
            return {"secrets": [], "count": 0}
        
        try:
            parent = f"projects/{self._project_id}"
            secrets = []
            
            for secret in self._client.list_secrets(request={"parent": parent}):
                secrets.append({
                    "name": secret.name.split("/")[-1],
                    "create_time": secret.create_time.isoformat() if secret.create_time else None,
                    "labels": dict(secret.labels) if secret.labels else {}
                })
            
            return {
                "secrets": secrets,
                "count": len(secrets)
            }
            
        except Exception as e:
            logger.error("Failed to list secrets", error=str(e))
            return {"secrets": [], "count": 0, "error": str(e)}


# Global secret manager instance
secret_manager = SecretManager()