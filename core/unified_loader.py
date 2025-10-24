"""Unified lazy loading system for tools, plugins, and modules.

This module consolidates LazyLoader, ToolLoader, PluginLoader, and ResourceManager
into a single, coherent loading system.
"""
import logging
import importlib
import sys
import inspect
from typing import Dict, Any, Optional, Callable, Type, List
from pathlib import Path
import threading

logger = logging.getLogger("crawllama")


class UnifiedLoader:
    """Unified loader for modules, tools, plugins, and resources."""

    def __init__(self, plugin_dir: str = "plugins"):
        """
        Initialize unified loader.

        Args:
            plugin_dir: Directory containing plugins
        """
        self.plugin_dir = Path(plugin_dir)
        
        # Separate caches for different resource types
        self._module_cache: Dict[str, Any] = {}
        self._tool_cache: Dict[str, Any] = {}
        self._plugin_cache: Dict[str, Any] = {}
        self._resource_cache: Dict[str, Any] = {}
        
        # Resource management
        self._resource_access_order: List[str] = []
        self._max_cached_resources: int = 10
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Tool configurations
        self._tool_configs: Dict[str, Dict[str, Any]] = {
            "web_search": {
                "module": "tools.web_search",
                "func": "web_search",
                "heavy": False
            },
            "wiki_lookup": {
                "module": "tools.wiki_lookup",
                "func": "wiki_lookup",
                "heavy": False
            },
            "rag": {
                "module": "tools.rag",
                "class": "RAGManager",
                "heavy": True  # Heavy due to ChromaDB
            },
            "read_page": {
                "module": "tools.page_reader",
                "func": "read_page",
                "heavy": False
            }
        }
        
        logger.info(f"Unified loader initialized (plugin_dir={plugin_dir})")

    # ========== Module Loading ==========
    
    def load_module(self, module_path: str, reload: bool = False) -> Any:
        """
        Lazily load a Python module.

        Args:
            module_path: Module path (e.g., "tools.web_search")
            reload: Force reload even if cached

        Returns:
            Loaded module
        """
        with self._lock:
            if module_path in self._module_cache and not reload:
                logger.debug(f"Using cached module: {module_path}")
                return self._module_cache[module_path]

            try:
                logger.info(f"Loading module: {module_path}")
                module = importlib.import_module(module_path)

                if reload and module_path in sys.modules:
                    module = importlib.reload(module)

                self._module_cache[module_path] = module
                return module

            except Exception as e:
                logger.error(f"Failed to load module '{module_path}': {e}")
                raise

    def load_class(self, module_path: str, class_name: str) -> Type:
        """
        Lazily load a class from a module.

        Args:
            module_path: Module path
            class_name: Class name to load

        Returns:
            Class type
        """
        module = self.load_module(module_path)
        return getattr(module, class_name)

    def load_function(self, module_path: str, func_name: str) -> Callable:
        """
        Lazily load a function from a module.

        Args:
            module_path: Module path
            func_name: Function name

        Returns:
            Function callable
        """
        module = self.load_module(module_path)
        return getattr(module, func_name)

    # ========== Tool Loading ==========
    
    def get_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Get tool by name, loading it lazily if not already loaded.

        Args:
            tool_name: Name of the tool
            **kwargs: Arguments for tool initialization

        Returns:
            Tool instance or function
        """
        # Return cached tool if available
        if tool_name in self._tool_cache:
            logger.debug(f"Using cached tool: {tool_name}")
            return self._tool_cache[tool_name]

        # Load tool
        if tool_name not in self._tool_configs:
            raise ValueError(f"Unknown tool: {tool_name}")

        config = self._tool_configs[tool_name]
        logger.info(f"Lazy loading tool: {tool_name}")

        try:
            if "class" in config:
                # Load class and instantiate
                tool_class = self.load_class(config["module"], config["class"])
                tool_instance = tool_class(**kwargs)
                self._tool_cache[tool_name] = tool_instance
                return tool_instance

            elif "func" in config:
                # Load function
                tool_func = self.load_function(config["module"], config["func"])
                self._tool_cache[tool_name] = tool_func
                return tool_func

        except Exception as e:
            logger.error(f"Failed to load tool '{tool_name}': {e}")
            raise

    def is_tool_loaded(self, tool_name: str) -> bool:
        """Check if tool is already loaded."""
        return tool_name in self._tool_cache

    def unload_tool(self, tool_name: str):
        """Unload a tool from cache."""
        if tool_name in self._tool_cache:
            del self._tool_cache[tool_name]
            logger.info(f"Unloaded tool: {tool_name}")

    def get_loaded_tools(self) -> List[str]:
        """Get list of currently loaded tools."""
        return list(self._tool_cache.keys())

    def preload_heavy_tools(self):
        """Preload heavy tools during startup."""
        heavy_tools = [
            name for name, config in self._tool_configs.items()
            if config.get("heavy", False)
        ]

        logger.info(f"Preloading {len(heavy_tools)} heavy tools")

        for tool_name in heavy_tools:
            try:
                self.get_tool(tool_name)
            except Exception as e:
                logger.warning(f"Failed to preload '{tool_name}': {e}")

    # ========== Plugin Loading ==========
    
    def discover_plugins(self) -> List[str]:
        """
        Discover available plugins in plugin directory.

        Returns:
            List of plugin names
        """
        if not self.plugin_dir.exists():
            logger.warning(f"Plugin directory does not exist: {self.plugin_dir}")
            return []

        plugins = []

        for path in self.plugin_dir.glob("*.py"):
            if path.stem != "__init__":
                plugins.append(path.stem)

        logger.info(f"Discovered {len(plugins)} plugins: {plugins}")
        return plugins

    def load_plugin(self, plugin_name: str, reload: bool = False) -> Any:
        """
        Load a plugin by name.

        Args:
            plugin_name: Plugin name (filename without .py)
            reload: Force reload

        Returns:
            Plugin module
        """
        if plugin_name in self._plugin_cache and not reload:
            return self._plugin_cache[plugin_name]

        try:
            module_path = f"{self.plugin_dir.name}.{plugin_name}"
            plugin = self.load_module(module_path, reload=reload)

            self._plugin_cache[plugin_name] = plugin
            logger.info(f"Loaded plugin: {plugin_name}")

            # Call plugin initialization if available
            if hasattr(plugin, "init_plugin"):
                plugin.init_plugin()

            return plugin

        except Exception as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}")
            raise

    def get_plugin(self, plugin_name: str) -> Any:
        """Get plugin, loading if necessary."""
        return self.load_plugin(plugin_name)

    def unload_plugin(self, plugin_name: str):
        """Unload a plugin."""
        if plugin_name in self._plugin_cache:
            plugin = self._plugin_cache[plugin_name]

            # Call cleanup if available
            if hasattr(plugin, "cleanup_plugin"):
                plugin.cleanup_plugin()

            del self._plugin_cache[plugin_name]
            logger.info(f"Unloaded plugin: {plugin_name}")

    def reload_plugin(self, plugin_name: str) -> Any:
        """Reload a plugin."""
        self.unload_plugin(plugin_name)
        return self.load_plugin(plugin_name, reload=True)

    def get_loaded_plugins(self) -> List[str]:
        """Get list of loaded plugins."""
        return list(self._plugin_cache.keys())

    def find_plugin_class(self, plugin_module: Any, base_class: Type) -> Optional[Type]:
        """
        Find a class in plugin module that inherits from base_class.

        Args:
            plugin_module: Plugin module
            base_class: Base class to search for

        Returns:
            Plugin class or None
        """
        for name, obj in inspect.getmembers(plugin_module):
            if (inspect.isclass(obj) and
                issubclass(obj, base_class) and
                obj is not base_class):
                return obj
        return None

    # ========== Resource Management ==========
    
    def get_resource(
        self,
        resource_name: str,
        loader_func: Callable[[], Any]
    ) -> Any:
        """
        Get resource, loading lazily if needed with LRU eviction.

        Args:
            resource_name: Resource identifier
            loader_func: Function to load resource if not cached

        Returns:
            Resource
        """
        with self._lock:
            # Check cache
            if resource_name in self._resource_cache:
                # Move to end (most recently used)
                self._resource_access_order.remove(resource_name)
                self._resource_access_order.append(resource_name)
                return self._resource_cache[resource_name]

            # Load resource
            logger.info(f"Loading resource: {resource_name}")
            resource = loader_func()

            # Add to cache
            self._resource_cache[resource_name] = resource
            self._resource_access_order.append(resource_name)

            # Evict oldest if cache is full
            if len(self._resource_cache) > self._max_cached_resources:
                oldest = self._resource_access_order.pop(0)
                del self._resource_cache[oldest]
                logger.info(f"Evicted resource from cache: {oldest}")

            return resource

    # ========== Cache Management ==========
    
    def clear_cache(self, cache_type: Optional[str] = None):
        """
        Clear loader cache.

        Args:
            cache_type: Cache type to clear ('modules', 'tools', 'plugins', 
                       'resources', or None for all)
        """
        with self._lock:
            if cache_type == "modules" or cache_type is None:
                self._module_cache.clear()
                logger.info("Cleared module cache")
            
            if cache_type == "tools" or cache_type is None:
                self._tool_cache.clear()
                logger.info("Cleared tool cache")
            
            if cache_type == "plugins" or cache_type is None:
                self._plugin_cache.clear()
                logger.info("Cleared plugin cache")
            
            if cache_type == "resources" or cache_type is None:
                self._resource_cache.clear()
                self._resource_access_order.clear()
                logger.info("Cleared resource cache")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "modules": len(self._module_cache),
            "tools": len(self._tool_cache),
            "plugins": len(self._plugin_cache),
            "resources": len(self._resource_cache)
        }


# ========== Global Instance ==========

_unified_loader = None
_loader_lock = threading.Lock()


def get_unified_loader() -> UnifiedLoader:
    """Get or create global unified loader instance."""
    global _unified_loader
    if _unified_loader is None:
        with _loader_lock:
            if _unified_loader is None:
                _unified_loader = UnifiedLoader()
    return _unified_loader


# ========== Backwards Compatibility Wrappers ==========

def get_tool_loader() -> UnifiedLoader:
    """
    Get tool loader (backwards compatibility).
    
    DEPRECATED: Use get_unified_loader() instead.
    """
    import warnings
    warnings.warn(
        "get_tool_loader() is deprecated, use get_unified_loader() instead",
        DeprecationWarning,
        stacklevel=2
    )
    return get_unified_loader()


def get_plugin_loader() -> UnifiedLoader:
    """
    Get plugin loader (backwards compatibility).
    
    DEPRECATED: Use get_unified_loader() instead.
    """
    import warnings
    warnings.warn(
        "get_plugin_loader() is deprecated, use get_unified_loader() instead",
        DeprecationWarning,
        stacklevel=2
    )
    return get_unified_loader()
