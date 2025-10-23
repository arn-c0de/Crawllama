"""Lazy loading system for tools, plugins, and heavy dependencies."""
import logging
import importlib
import sys
from typing import Dict, Any, Optional, Callable, Type
from pathlib import Path
import threading

logger = logging.getLogger("crawllama")


class LazyLoader:
    """Lazy loader for modules and components."""

    def __init__(self):
        """Initialize lazy loader with cache."""
        self._cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        logger.info("Lazy loader initialized")

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
            if module_path in self._cache and not reload:
                logger.debug(f"Using cached module: {module_path}")
                return self._cache[module_path]

            try:
                logger.info(f"Loading module: {module_path}")
                module = importlib.import_module(module_path)

                if reload and module_path in sys.modules:
                    module = importlib.reload(module)

                self._cache[module_path] = module
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

    def clear_cache(self, module_path: Optional[str] = None):
        """
        Clear loader cache.

        Args:
            module_path: Specific module to clear, or None for all
        """
        with self._lock:
            if module_path:
                self._cache.pop(module_path, None)
                logger.info(f"Cleared cache for: {module_path}")
            else:
                self._cache.clear()
                logger.info("Cleared all lazy loader cache")


class ToolLoader:
    """Lazy loader specifically for tools."""

    def __init__(self):
        """Initialize tool loader."""
        self._tools: Dict[str, Any] = {}
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
        self._lazy_loader = LazyLoader()
        logger.info(f"Tool loader initialized with {len(self._tool_configs)} tools")

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
        if tool_name in self._tools:
            logger.debug(f"Using cached tool: {tool_name}")
            return self._tools[tool_name]

        # Load tool
        if tool_name not in self._tool_configs:
            raise ValueError(f"Unknown tool: {tool_name}")

        config = self._tool_configs[tool_name]
        logger.info(f"Lazy loading tool: {tool_name}")

        try:
            if "class" in config:
                # Load class and instantiate
                tool_class = self._lazy_loader.load_class(
                    config["module"],
                    config["class"]
                )
                tool_instance = tool_class(**kwargs)
                self._tools[tool_name] = tool_instance
                return tool_instance

            elif "func" in config:
                # Load function
                tool_func = self._lazy_loader.load_function(
                    config["module"],
                    config["func"]
                )
                self._tools[tool_name] = tool_func
                return tool_func

        except Exception as e:
            logger.error(f"Failed to load tool '{tool_name}': {e}")
            raise

    def is_tool_loaded(self, tool_name: str) -> bool:
        """
        Check if tool is already loaded.

        Args:
            tool_name: Tool name

        Returns:
            True if loaded
        """
        return tool_name in self._tools

    def unload_tool(self, tool_name: str):
        """
        Unload a tool from cache.

        Args:
            tool_name: Tool name
        """
        if tool_name in self._tools:
            del self._tools[tool_name]
            logger.info(f"Unloaded tool: {tool_name}")

    def get_loaded_tools(self) -> list:
        """Get list of currently loaded tools."""
        return list(self._tools.keys())

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


class PluginLoader:
    """Lazy loader for plugins."""

    def __init__(self, plugin_dir: str = "plugins"):
        """
        Initialize plugin loader.

        Args:
            plugin_dir: Directory containing plugins
        """
        self.plugin_dir = Path(plugin_dir)
        self._plugins: Dict[str, Any] = {}
        self._lazy_loader = LazyLoader()

        logger.info(f"Plugin loader initialized: {plugin_dir}")

    def discover_plugins(self) -> list:
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
        if plugin_name in self._plugins and not reload:
            return self._plugins[plugin_name]

        try:
            module_path = f"{self.plugin_dir.name}.{plugin_name}"
            plugin = self._lazy_loader.load_module(module_path, reload=reload)

            self._plugins[plugin_name] = plugin
            logger.info(f"Loaded plugin: {plugin_name}")

            # Call plugin initialization if available
            if hasattr(plugin, "init_plugin"):
                plugin.init_plugin()

            return plugin

        except Exception as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}")
            raise

    def get_plugin(self, plugin_name: str) -> Any:
        """
        Get plugin, loading if necessary.

        Args:
            plugin_name: Plugin name

        Returns:
            Plugin module
        """
        return self.load_plugin(plugin_name)

    def unload_plugin(self, plugin_name: str):
        """
        Unload a plugin.

        Args:
            plugin_name: Plugin name
        """
        if plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]

            # Call cleanup if available
            if hasattr(plugin, "cleanup_plugin"):
                plugin.cleanup_plugin()

            del self._plugins[plugin_name]
            logger.info(f"Unloaded plugin: {plugin_name}")

    def reload_plugin(self, plugin_name: str) -> Any:
        """
        Reload a plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            Reloaded plugin
        """
        self.unload_plugin(plugin_name)
        return self.load_plugin(plugin_name, reload=True)

    def get_loaded_plugins(self) -> list:
        """Get list of loaded plugins."""
        return list(self._plugins.keys())


class ResourceManager:
    """Manage lazy-loaded resources with memory awareness."""

    def __init__(self, max_cached_items: int = 10):
        """
        Initialize resource manager.

        Args:
            max_cached_items: Maximum items to keep in cache
        """
        self.max_cached_items = max_cached_items
        self._resources: Dict[str, Any] = {}
        self._access_order: list = []
        self._lock = threading.Lock()

        logger.info(f"Resource manager initialized (max_cached={max_cached_items})")

    def get_resource(
        self,
        resource_name: str,
        loader_func: Callable[[], Any]
    ) -> Any:
        """
        Get resource, loading lazily if needed.

        Args:
            resource_name: Resource identifier
            loader_func: Function to load resource if not cached

        Returns:
            Resource
        """
        with self._lock:
            # Check cache
            if resource_name in self._resources:
                # Move to end (most recently used)
                self._access_order.remove(resource_name)
                self._access_order.append(resource_name)
                return self._resources[resource_name]

            # Load resource
            logger.info(f"Loading resource: {resource_name}")
            resource = loader_func()

            # Add to cache
            self._resources[resource_name] = resource
            self._access_order.append(resource_name)

            # Evict oldest if cache is full
            if len(self._resources) > self.max_cached_items:
                oldest = self._access_order.pop(0)
                del self._resources[oldest]
                logger.info(f"Evicted resource from cache: {oldest}")

            return resource

    def clear_cache(self):
        """Clear all cached resources."""
        with self._lock:
            self._resources.clear()
            self._access_order.clear()
            logger.info("Cleared resource cache")


# Global instances
_tool_loader = None
_plugin_loader = None


def get_tool_loader() -> ToolLoader:
    """Get global tool loader instance."""
    global _tool_loader
    if _tool_loader is None:
        _tool_loader = ToolLoader()
    return _tool_loader


def get_plugin_loader() -> PluginLoader:
    """Get global plugin loader instance."""
    global _plugin_loader
    if _plugin_loader is None:
        _plugin_loader = PluginLoader()
    return _plugin_loader
