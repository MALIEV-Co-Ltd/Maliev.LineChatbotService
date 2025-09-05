"""Dynamic configuration system with Redis and Secret Manager integration."""

import json
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

import structlog

from ..database.redis_client import redis_client
from ..secrets.manager import secret_manager

logger = structlog.get_logger("config.dynamic")


class DynamicConfiguration:
    """Dynamic configuration management with Redis storage and Secret Manager integration."""
    
    def __init__(self):
        """Initialize dynamic configuration manager."""
        self._initialized = False
        self._config_cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes
    
    async def initialize(self):
        """Initialize the configuration system."""
        if self._initialized:
            return
        
        try:
            await secret_manager.initialize()
            
            logger.info("Dynamic configuration system initialized")
            self._initialized = True
            
        except Exception as e:
            logger.error("Failed to initialize dynamic configuration", error=str(e))
            raise
    
    async def get(self, key: str, section: str = "app", default: Any = None) -> Any:
        """Get configuration value with secret resolution."""
        
        if not self._initialized:
            await self.initialize()
        
        try:
            # Build Redis key
            redis_key = f"config:{section}:{key}"
            
            # Get from Redis
            value = await redis_client.get(redis_key)
            
            if value is None:
                return default
            
            # Try to parse as JSON (for complex types)
            try:
                parsed_value = json.loads(value)
                value = parsed_value
            except (json.JSONDecodeError, TypeError):
                # Keep as string
                pass
            
            # Resolve secret if it's a secret reference
            if isinstance(value, str) and self._is_secret_reference(value):
                secret_value = await secret_manager.get_secret(value)
                return secret_value if secret_value is not None else default
            
            return value
            
        except Exception as e:
            logger.error("Failed to get configuration", key=key, section=section, error=str(e))
            return default
    
    async def set(self, key: str, value: Any, section: str = "app", notify: bool = True) -> bool:
        """Set configuration value."""
        
        if not self._initialized:
            await self.initialize()
        
        try:
            # Build Redis key
            redis_key = f"config:{section}:{key}"
            
            # Serialize value if needed
            if isinstance(value, (dict, list, tuple)):
                serialized_value = json.dumps(value)
            else:
                serialized_value = str(value)
            
            # Store in Redis
            await redis_client.set(redis_key, serialized_value)
            
            # Add metadata
            metadata_key = f"config_meta:{section}:{key}"
            metadata = {
                "updated_at": datetime.utcnow().isoformat(),
                "type": type(value).__name__,
                "size": len(serialized_value)
            }
            
            for field, meta_value in metadata.items():
                await redis_client.hset(metadata_key, field, str(meta_value))
            
            logger.info("Configuration set", key=key, section=section, type=type(value).__name__)
            
            # Notify other components if needed
            if notify:
                await self._notify_config_change(section, key, value)
            
            return True
            
        except Exception as e:
            logger.error("Failed to set configuration", key=key, section=section, error=str(e))
            return False
    
    async def get_section(self, section: str) -> Dict[str, Any]:
        """Get all configuration values in a section."""
        
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get all keys in section
            pattern = f"config:{section}:*"
            config_keys = await redis_client.keys(pattern)
            
            configuration = {}
            
            for redis_key in config_keys:
                # Extract config key name
                config_key = redis_key.split(":")[-1]
                
                # Get value
                value = await self.get(config_key, section)
                configuration[config_key] = value
            
            return configuration
            
        except Exception as e:
            logger.error("Failed to get configuration section", section=section, error=str(e))
            return {}
    
    async def delete(self, key: str, section: str = "app") -> bool:
        """Delete configuration value."""
        
        try:
            redis_key = f"config:{section}:{key}"
            metadata_key = f"config_meta:{section}:{key}"
            
            # Delete config and metadata
            deleted_count = await redis_client.delete(redis_key, metadata_key)
            
            logger.info("Configuration deleted", key=key, section=section)
            
            # Notify about deletion
            await self._notify_config_change(section, key, None, deleted=True)
            
            return deleted_count > 0
            
        except Exception as e:
            logger.error("Failed to delete configuration", key=key, section=section, error=str(e))
            return False
    
    async def list_sections(self) -> List[str]:
        """List all configuration sections."""
        
        try:
            # Get all config keys
            all_keys = await redis_client.keys("config:*")
            
            # Extract unique sections
            sections = set()
            for key in all_keys:
                parts = key.split(":")
                if len(parts) >= 2:
                    sections.add(parts[1])
            
            return sorted(list(sections))
            
        except Exception as e:
            logger.error("Failed to list configuration sections", error=str(e))
            return []
    
    async def export_section(self, section: str) -> Dict[str, Any]:
        """Export configuration section with metadata."""
        
        try:
            config_data = await self.get_section(section)
            
            # Get metadata for each key
            metadata = {}
            for key in config_data.keys():
                meta_key = f"config_meta:{section}:{key}"
                key_metadata = await redis_client.hgetall(meta_key)
                if key_metadata:
                    metadata[key] = key_metadata
            
            return {
                "section": section,
                "configuration": config_data,
                "metadata": metadata,
                "exported_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to export configuration section", section=section, error=str(e))
            return {}
    
    async def import_section(self, section: str, config_data: Dict[str, Any], overwrite: bool = False) -> bool:
        """Import configuration section."""
        
        try:
            imported_count = 0
            
            for key, value in config_data.items():
                # Check if key exists
                if not overwrite:
                    existing = await self.get(key, section)
                    if existing is not None:
                        logger.info("Skipping existing configuration", key=key, section=section)
                        continue
                
                # Set configuration
                success = await self.set(key, value, section, notify=False)
                if success:
                    imported_count += 1
            
            logger.info("Configuration section imported", 
                       section=section, 
                       imported_count=imported_count,
                       total_count=len(config_data))
            
            return imported_count > 0
            
        except Exception as e:
            logger.error("Failed to import configuration section", section=section, error=str(e))
            return False
    
    async def reload_secrets(self, section: Optional[str] = None):
        """Reload secrets for configuration values."""
        
        try:
            if section:
                sections = [section]
            else:
                sections = await self.list_sections()
            
            reloaded_count = 0
            
            for sec in sections:
                config_keys = await redis_client.keys(f"config:{sec}:*")
                
                for redis_key in config_keys:
                    value = await redis_client.get(redis_key)
                    
                    # Check if it's a secret reference
                    if value and self._is_secret_reference(value):
                        # Invalidate secret cache to force refresh
                        await secret_manager.invalidate_cache(value)
                        reloaded_count += 1
            
            logger.info("Configuration secrets reloaded", 
                       sections=sections, 
                       reloaded_count=reloaded_count)
            
        except Exception as e:
            logger.error("Failed to reload configuration secrets", error=str(e))
    
    def _is_secret_reference(self, value: str) -> bool:
        """Check if a value is a secret reference."""
        return (value.startswith("env:") or 
                value.startswith("projects/") or 
                value.startswith("secret:"))
    
    async def _notify_config_change(self, section: str, key: str, value: Any, deleted: bool = False):
        """Notify other components about configuration changes."""
        
        try:
            # Publish to Redis pub/sub for real-time updates
            channel = f"config_change:{section}"
            
            notification = {
                "section": section,
                "key": key,
                "value": value,
                "deleted": deleted,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await redis_client.publish(channel, json.dumps(notification))
            
            logger.debug("Configuration change notification sent", 
                        section=section, key=key, deleted=deleted)
            
        except Exception as e:
            logger.warning("Failed to send configuration change notification", error=str(e))
    
    async def subscribe_to_changes(self, section: str, callback):
        """Subscribe to configuration changes for a section."""
        
        try:
            pubsub = redis_client.pubsub()
            channel = f"config_change:{section}"
            
            await pubsub.subscribe(channel)
            
            logger.info("Subscribed to configuration changes", section=section)
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        notification = json.loads(message["data"])
                        await callback(notification)
                    except Exception as e:
                        logger.warning("Failed to process config change notification", error=str(e))
            
        except Exception as e:
            logger.error("Failed to subscribe to configuration changes", section=section, error=str(e))


# Global dynamic configuration instance
dynamic_config = DynamicConfiguration()