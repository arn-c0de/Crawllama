"""Lazy loading system for tools, plugins, and heavy dependencies.

DEPRECATED: This module is deprecated in favor of core.unified_loader.
It is kept for backwards compatibility but will be removed in a future version.
Use core.unified_loader.get_unified_loader() instead.
"""
import logging
import warnings
from collections.abc import Callable
from typing import Any

# Import from new unified system
from core.unified_loader import get_unified_loader

logger = logging.getLogger("crawllama")


# ========== Backwards Compatibility Classes ==========

class LazyLoader:
    """
    Lazy loader for modules and components.
    
    DEPRECATED: Use UnifiedLoader from core.unified_loader instead.
    """

    def __init__(self):
        """Initialize lazy loader with cache."""
        warnings.warn(
            "LazyLoader is deprecated. Use UnifiedLoader from core.unified_loader instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._loader = get_unified_loader()
        logger.info("LazyLoader initialized (deprecated wrapper)")

    def load_module(self, module_path: str, reload: bool = False) -> Any:
        """Lazily load a Python module."""
        return self._loader.load_module(module_path, reload)

    def load_class(self, module_path: str, class_name: str) -> type:
        """Lazily load a class from a module."""
        return self._loader.load_class(module_path, class_name)

    def load_function(self, module_path: str, func_name: str) -> Callable:
        """Lazily load a function from a module."""
        return self._loader.load_function(module_path, func_name)

    def clear_cache(self, module_path: str | None = None):
        """Clear loader cache."""
        if module_path:
            # UnifiedLoader doesn't support per-module clearing
            logger.warning("Per-module cache clearing not supported in UnifiedLoader")
        self._loader.clear_cache("modules")


class ToolLoader:
    """
    Lazy loader specifically for tools.
    
    DEPRECATED: Use UnifiedLoader from core.unified_loader instead.
    """

    def __init__(self):
        """Initialize tool loader."""
        warnings.warn(
            "ToolLoader is deprecated. Use UnifiedLoader from core.unified_loader instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._loader = get_unified_loader()
        logger.info("ToolLoader initialized (deprecated wrapper)")

    def get_tool(self, tool_name: str, **kwargs) -> Any:
        """Get tool by name, loading it lazily if not already loaded."""
        return self._loader.get_tool(tool_name, **kwargs)

    def is_tool_loaded(self, tool_name: str) -> bool:
        """Check if tool is already loaded."""
        return self._loader.is_tool_loaded(tool_name)

    def unload_tool(self, tool_name: str):
        """Unload a tool from cache."""
        self._loader.unload_tool(tool_name)

    def get_loaded_tools(self) -> list:
        """Get list of currently loaded tools."""
        return self._loader.get_loaded_tools()

    def preload_heavy_tools(self):
        """Preload heavy tools during startup."""
        self._loader.preload_heavy_tools()


class PluginLoader:
    """
    Lazy loader for plugins.
    
    DEPRECATED: Use UnifiedLoader from core.unified_loader instead.
    """

    def __init__(self, plugin_dir: str = "plugins"):
        """Initialize plugin loader."""
        warnings.warn(
            "PluginLoader is deprecated. Use UnifiedLoader from core.unified_loader instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._loader = get_unified_loader()
        logger.info(f"PluginLoader initialized (deprecated wrapper): {plugin_dir}")

    def discover_plugins(self) -> list:
        """Discover available plugins in plugin directory."""
        return self._loader.discover_plugins()

    def load_plugin(self, plugin_name: str, reload: bool = False) -> Any:
        """Load a plugin by name."""
        return self._loader.load_plugin(plugin_name, reload)

    def get_plugin(self, plugin_name: str) -> Any:
        """Get plugin, loading if necessary."""
        return self._loader.get_plugin(plugin_name)

    def unload_plugin(self, plugin_name: str):
        """Unload a plugin."""
        self._loader.unload_plugin(plugin_name)

    def reload_plugin(self, plugin_name: str) -> Any:
        """Reload a plugin."""
        return self._loader.reload_plugin(plugin_name)

    def get_loaded_plugins(self) -> list:
        """Get list of loaded plugins."""
        return self._loader.get_loaded_plugins()


class ResourceManager:
    """
    Manage lazy-loaded resources with memory awareness.
    
    DEPRECATED: Use UnifiedLoader.get_resource() instead.
    """

    def __init__(self, max_cached_items: int = 10):
        """Initialize resource manager."""
        warnings.warn(
            "ResourceManager is deprecated. Use UnifiedLoader.get_resource() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self._loader = get_unified_loader()
        self._loader._max_cached_resources = max_cached_items
        logger.info(f"ResourceManager initialized (deprecated wrapper, max_cached={max_cached_items})")

    def get_resource(self, resource_name: str, loader_func: Callable[[], Any]) -> Any:
        """Get resource, loading lazily if needed."""
        return self._loader.get_resource(resource_name, loader_func)

    def clear_cache(self):
        """Clear all cached resources."""
        self._loader.clear_cache("resources")


# ========== Global instances (deprecated) ==========

_tool_loader = None
_plugin_loader = None


def get_tool_loader() -> ToolLoader:
    """
    Get global tool loader instance.
    
    DEPRECATED: Use get_unified_loader() from core.unified_loader instead.
    """
    warnings.warn(
        "get_tool_loader() is deprecated. Use get_unified_loader() from core.unified_loader instead.",
        DeprecationWarning,
        stacklevel=2
    )
    global _tool_loader
    if _tool_loader is None:
        _tool_loader = ToolLoader()
    return _tool_loader


def get_plugin_loader() -> PluginLoader:
    """
    Get global plugin loader instance.
    
    DEPRECATED: Use get_unified_loader() from core.unified_loader instead.
    """
    warnings.warn(
        "get_plugin_loader() is deprecated. Use get_unified_loader() from core.unified_loader instead.",
        DeprecationWarning,
        stacklevel=2
    )
    global _plugin_loader
    if _plugin_loader is None:
        _plugin_loader = PluginLoader()
    return _plugin_loader

