"""Global registry for singleton instances.

This module provides a centralized registry for managing global singleton instances
of various system components like performance trackers, alert systems, loaders, etc.
"""
import logging
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("crawllama")


class GlobalRegistry:
    """Singleton registry for all global instances."""
    
    _instances: dict[str, Any] = {}
    _factories: dict[str, Callable[[], Any]] = {}
    _lock = threading.Lock()
    
    @classmethod
    def register_factory(cls, name: str, factory: Callable[[], Any]) -> None:
        """
        Register a factory function for lazy initialization.
        
        Args:
            name: Instance name
            factory: Factory function that creates the instance
        """
        with cls._lock:
            cls._factories[name] = factory
            logger.debug(f"Registered factory: {name}")
    
    @classmethod
    def get(cls, name: str, factory: Callable[[], Any] | None = None) -> Any:
        """
        Get or create instance by name.
        
        Args:
            name: Instance name
            factory: Optional factory function if not pre-registered
        
        Returns:
            Instance
            
        Raises:
            ValueError: If no factory registered and none provided
        """
        with cls._lock:
            # Return cached instance if available
            if name in cls._instances:
                logger.debug(f"Using cached instance: {name}")
                return cls._instances[name]
            
            # Get factory
            factory_func = factory or cls._factories.get(name)
            if factory_func is None:
                raise ValueError(f"No factory registered for '{name}'")
            
            # Create and cache instance
            logger.info(f"Creating instance: {name}")
            instance = factory_func()
            cls._instances[name] = instance
            
            return instance
    
    @classmethod
    def set(cls, name: str, instance: Any) -> None:
        """
        Manually set an instance in the registry.
        
        Args:
            name: Instance name
            instance: Instance to store
        """
        with cls._lock:
            cls._instances[name] = instance
            logger.debug(f"Set instance: {name}")
    
    @classmethod
    def clear(cls, name: str | None = None) -> None:
        """
        Clear instance(s) from registry.
        
        Args:
            name: Specific instance name, or None for all
        """
        with cls._lock:
            if name:
                if name in cls._instances:
                    del cls._instances[name]
                    logger.info(f"Cleared instance: {name}")
            else:
                cls._instances.clear()
                logger.info("Cleared all instances")
    
    @classmethod
    def has(cls, name: str) -> bool:
        """Check if instance exists in registry."""
        return name in cls._instances
    
    @classmethod
    def list_instances(cls) -> list:
        """Get list of all registered instance names."""
        return list(cls._instances.keys())
    
    @classmethod
    def list_factories(cls) -> list:
        """Get list of all registered factory names."""
        return list(cls._factories.keys())


# ========== Pre-registered Factories ==========

def _create_performance_tracker():
    """Factory for PerformanceTracker."""
    from core.health import PerformanceTracker
    return PerformanceTracker()


def _create_alert_system():
    """Factory for AlertSystem."""
    from core.health import AlertSystem
    return AlertSystem()


def _create_system_monitor():
    """Factory for SystemMonitor."""
    from core.health import SystemMonitor
    monitor = SystemMonitor(update_interval=1.0)
    monitor.start()
    return monitor


def _create_unified_loader():
    """Factory for UnifiedLoader."""
    from core.unified_loader import UnifiedLoader
    return UnifiedLoader()


def _create_plugin_manager():
    """Factory for PluginManager."""
    from core.plugin_manager import PluginManager
    return PluginManager()


def _create_safe_fetcher():
    """Factory for SafeFetcher."""
    from utils.safe_fetch import SafeFetcher
    return SafeFetcher()


# Register default factories
GlobalRegistry.register_factory("performance_tracker", _create_performance_tracker)
GlobalRegistry.register_factory("alert_system", _create_alert_system)
GlobalRegistry.register_factory("system_monitor", _create_system_monitor)
GlobalRegistry.register_factory("unified_loader", _create_unified_loader)
GlobalRegistry.register_factory("plugin_manager", _create_plugin_manager)
GlobalRegistry.register_factory("safe_fetcher", _create_safe_fetcher)


# ========== Convenience Functions ==========

def get_performance_tracker():
    """Get or create global PerformanceTracker instance."""
    return GlobalRegistry.get("performance_tracker")


def get_alert_system():
    """Get or create global AlertSystem instance."""
    return GlobalRegistry.get("alert_system")


def get_system_monitor():
    """Get or create global SystemMonitor instance."""
    return GlobalRegistry.get("system_monitor")


def get_unified_loader():
    """Get or create global UnifiedLoader instance."""
    return GlobalRegistry.get("unified_loader")


def get_plugin_manager():
    """Get or create global PluginManager instance."""
    return GlobalRegistry.get("plugin_manager")


def get_safe_fetcher():
    """Get or create global SafeFetcher instance."""
    return GlobalRegistry.get("safe_fetcher")
