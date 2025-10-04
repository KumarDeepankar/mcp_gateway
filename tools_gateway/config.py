#!/usr/bin/env python3
"""
Configuration management for Tools Gateway
Provides dynamic configuration for connection health checks and allowed origins
"""
import pickle
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ConnectionHealthConfig(BaseModel):
    """Configuration for connection health checks"""
    enabled: bool = Field(default=True, description="Enable connection health monitoring")
    check_interval_seconds: int = Field(default=60, description="Interval between health checks in seconds")
    stale_timeout_seconds: int = Field(default=300, description="Consider connection stale after this many seconds")
    max_retry_attempts: int = Field(default=3, description="Maximum retry attempts for failed connections")
    retry_delay_seconds: int = Field(default=5, description="Delay between retry attempts")


class OriginConfig(BaseModel):
    """Configuration for allowed origins"""
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "0.0.0.0"],
        description="List of allowed origins/hostnames"
    )
    allow_ngrok: bool = Field(default=True, description="Allow ngrok domains")
    allow_https: bool = Field(default=True, description="Allow all HTTPS origins")


class GatewayConfig(BaseModel):
    """Main gateway configuration"""
    connection_health: ConnectionHealthConfig = Field(default_factory=ConnectionHealthConfig)
    origin: OriginConfig = Field(default_factory=OriginConfig)
    updated_at: datetime = Field(default_factory=datetime.now)


class ConfigManager:
    """Manages gateway configuration with persistence using pickle storage and in-memory caching"""

    def __init__(self, config_file: str = "gateway_config.pkl"):
        self.config_file = Path(config_file)
        self.config: GatewayConfig = GatewayConfig()

        # In-memory cache for fast origin validation
        self._origin_cache: set = set()
        self._config_hash: Optional[str] = None

        self._load_config()
        self._refresh_cache()

    def _load_config(self):
        """Load configuration from pickle file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'rb') as f:
                    data = pickle.load(f)
                    self.config = GatewayConfig(**data)
                    logger.info(f"Loaded configuration from {self.config_file}")
            else:
                logger.info("No config file found, using defaults")
                self._save_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}, using defaults")
            self.config = GatewayConfig()

    def _refresh_cache(self):
        """Refresh in-memory cache for origin validation"""
        self._origin_cache = set(self.config.origin.allowed_origins)
        # Create hash for cache invalidation detection
        import hashlib
        config_str = str(sorted(self.config.origin.allowed_origins))
        self._config_hash = hashlib.md5(config_str.encode()).hexdigest()
        logger.debug(f"Origin cache refreshed with {len(self._origin_cache)} origins")

    def _save_config(self):
        """Save configuration to pickle file with backup"""
        try:
            # Create backup of existing file
            if self.config_file.exists():
                backup_path = self.config_file.with_suffix('.pkl.backup')
                with open(self.config_file, 'rb') as src:
                    with open(backup_path, 'wb') as dst:
                        dst.write(src.read())

            # Write new data
            with open(self.config_file, 'wb') as f:
                pickle.dump(self.config.model_dump(), f)
            logger.info(f"Saved configuration to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def get_connection_health_config(self) -> ConnectionHealthConfig:
        """Get connection health configuration"""
        return self.config.connection_health

    def update_connection_health_config(self, **kwargs) -> ConnectionHealthConfig:
        """Update connection health configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config.connection_health, key):
                setattr(self.config.connection_health, key, value)
        self.config.updated_at = datetime.now()
        self._save_config()
        logger.info(f"Updated connection health config: {kwargs}")
        return self.config.connection_health

    def get_origin_config(self) -> OriginConfig:
        """Get origin configuration"""
        return self.config.origin

    def add_allowed_origin(self, origin: str) -> bool:
        """Add an allowed origin"""
        if origin not in self.config.origin.allowed_origins:
            self.config.origin.allowed_origins.append(origin)
            self.config.updated_at = datetime.now()
            self._save_config()
            self._refresh_cache()  # Refresh cache after modification
            logger.info(f"Added allowed origin: {origin}")
            return True
        return False

    def remove_allowed_origin(self, origin: str) -> bool:
        """Remove an allowed origin"""
        if origin in self.config.origin.allowed_origins:
            self.config.origin.allowed_origins.remove(origin)
            self.config.updated_at = datetime.now()
            self._save_config()
            self._refresh_cache()  # Refresh cache after modification
            logger.info(f"Removed allowed origin: {origin}")
            return True
        return False

    def update_origin_config(self, **kwargs) -> OriginConfig:
        """Update origin configuration"""
        for key, value in kwargs.items():
            if hasattr(self.config.origin, key):
                setattr(self.config.origin, key, value)
        self.config.updated_at = datetime.now()
        self._save_config()
        self._refresh_cache()  # Refresh cache after modification
        logger.info(f"Updated origin config: {kwargs}")
        return self.config.origin

    def get_all_config(self) -> Dict[str, Any]:
        """Get all configuration as dictionary"""
        return self.config.model_dump()

    def is_origin_allowed(self, hostname: str) -> bool:
        """
        Fast in-memory check if hostname is in allowed origins.
        Uses cached set for O(1) lookup instead of reading pickle file.
        """
        return hostname in self._origin_cache

    def get_origin_validation_config(self) -> tuple[set, bool, bool]:
        """
        Get cached origin validation configuration for fast access.
        Returns: (allowed_origins_set, allow_ngrok, allow_https)
        """
        return (
            self._origin_cache,
            self.config.origin.allow_ngrok,
            self.config.origin.allow_https
        )


# Singleton instance
config_manager = ConfigManager()
