"""Plugin management system for extensible functionality."""
import hashlib
import hmac
import json
import logging
import types
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.unified_loader import get_unified_loader
from utils.singleton import lazy_singleton

logger = logging.getLogger("crawllama")


@dataclass
class PluginMetadata:
    """Plugin metadata."""
    name: str
    version: str
    description: str
    author: str
    dependencies: list[str]
    enabled: bool = True


class Plugin:
    """Base plugin class."""

    def __init__(self):
        """Initialize plugin."""
        self.name = self.__class__.__name__
        self.enabled = True

    def get_metadata(self) -> PluginMetadata:
        """
        Get plugin metadata.

        Returns:
            PluginMetadata instance
        """
        return PluginMetadata(
            name=self.name,
            version="1.0.0",
            description="",
            author="",
            dependencies=[]
        )

    def initialize(self, config: dict[str, Any]):
        """
        Initialize plugin with configuration.

        Args:
            config: Plugin configuration
        """
        pass

    def shutdown(self):
        """Cleanup on plugin shutdown."""
        pass

    def get_tools(self) -> list[Callable]:
        """
        Get tools provided by this plugin.

        Returns:
            List of tool functions
        """
        return []

    def get_commands(self) -> dict[str, Callable]:
        """
        Get CLI commands provided by this plugin.

        Returns:
            Dictionary of command_name -> function
        """
        return {}


class PluginManager:
    """Manage plugins for extensibility."""

    def __init__(self, plugin_dir: str = "plugins", config_path: str = "config.json"):
        """
        Initialize plugin manager.

        Args:
            plugin_dir: Directory containing plugins
            config_path: Path to configuration file
        """
        self.plugin_dir = Path(plugin_dir)
        self.config_path = config_path

        self._plugins: dict[str, Plugin] = {}
        self._plugin_modules: dict[str, types.ModuleType] = {}
        self._unified_loader = get_unified_loader()

        # Load configuration
        self.config = self._load_config()

        # Ensure plugin directory exists
        self.plugin_dir.mkdir(exist_ok=True)

        logger.info(f"Plugin manager initialized: {plugin_dir}")

    def _load_config(self) -> dict[str, Any]:
        """Load plugin configuration."""
        try:
            with open(self.config_path) as f:
                config = json.load(f)
                return config.get("plugins", {})
        except Exception as e:
            logger.warning(f"Failed to load plugin config: {e}")
            return {}

    def discover_plugins(self) -> list[str]:
        """
        Discover available plugins.

        Returns:
            List of plugin names
        """
        return self._unified_loader.discover_plugins()

    def load_plugin(self, plugin_name: str, auto_initialize: bool = True) -> Plugin | None:
        """
        Load a plugin.

        Args:
            plugin_name: Plugin name
            auto_initialize: Automatically initialize plugin

        Returns:
            Plugin instance or None
        """
        if plugin_name in self._plugins:
            logger.warning(f"Plugin '{plugin_name}' already loaded")
            return self._plugins[plugin_name]

        # Enforce explicit allowlist from config
        plugin_config = self.config.get(plugin_name)
        if not plugin_config or not plugin_config.get("enabled", False):
            logger.warning(f"Plugin '{plugin_name}' is not enabled in config")
            return None

        # Enforce hash verification
        expected_hash = plugin_config.get("sha256")
        if not expected_hash:
            logger.error(f"Plugin '{plugin_name}' missing sha256 in config - refusing to load")
            return None

        # Hash and execute the very same bytes: importing by module name could
        # run a different (or cached, pre-reload) file than the one verified.
        source = self._read_verified_plugin(plugin_name, expected_hash)
        if source is None:
            logger.error(f"Plugin '{plugin_name}' failed sha256 verification - refusing to load")
            return None

        try:
            plugin_module = self._exec_plugin_source(plugin_name, source)

            # Find Plugin class in module
            plugin_class = self._unified_loader.find_plugin_class(plugin_module, Plugin)

            if not plugin_class:
                logger.error(f"No Plugin class found in '{plugin_name}'")
                return None

            # Instantiate plugin
            plugin_instance = plugin_class()

            # Initialize if requested
            if auto_initialize:
                plugin_instance.initialize(plugin_config)

            # Store plugin (only once it initialized successfully)
            self._plugins[plugin_name] = plugin_instance
            self._plugin_modules[plugin_name] = plugin_module

            logger.info(f"Loaded plugin: {plugin_name}")
            return plugin_instance

        except Exception as e:
            logger.error(f"Failed to load plugin '{plugin_name}': {e}")
            return None

    def unload_plugin(self, plugin_name: str):
        """
        Unload a plugin.

        Args:
            plugin_name: Plugin name
        """
        if plugin_name not in self._plugins:
            logger.warning(f"Plugin '{plugin_name}' not loaded")
            return

        try:
            plugin = self._plugins[plugin_name]
            plugin.shutdown()

            del self._plugins[plugin_name]
            module = self._plugin_modules.pop(plugin_name, None)
            if module is not None and hasattr(module, "cleanup_plugin"):
                module.cleanup_plugin()

            logger.info(f"Unloaded plugin: {plugin_name}")

        except Exception as e:
            logger.error(f"Failed to unload plugin '{plugin_name}': {e}")

    def reload_plugin(self, plugin_name: str) -> Plugin | None:
        """
        Reload a plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            Reloaded plugin instance
        """
        self.unload_plugin(plugin_name)
        return self.load_plugin(plugin_name)

    def get_plugin(self, plugin_name: str) -> Plugin | None:
        """
        Get loaded plugin.

        Args:
            plugin_name: Plugin name

        Returns:
            Plugin instance or None
        """
        return self._plugins.get(plugin_name)

    def get_loaded_plugins(self) -> list[str]:
        """Get list of loaded plugin names."""
        return list(self._plugins.keys())

    def get_all_tools(self) -> list[Callable]:
        """
        Get all tools from loaded plugins.

        Returns:
            List of tool functions
        """
        tools = []
        for plugin in self._plugins.values():
            if plugin.enabled:
                tools.extend(plugin.get_tools())
        return tools

    def get_all_commands(self) -> dict[str, Callable]:
        """
        Get all CLI commands from loaded plugins.

        Returns:
            Dictionary of command_name -> function
        """
        commands = {}
        for plugin in self._plugins.values():
            if plugin.enabled:
                plugin_commands = plugin.get_commands()
                commands.update(plugin_commands)
        return commands

    def enable_plugin(self, plugin_name: str):
        """
        Enable a plugin.

        Args:
            plugin_name: Plugin name
        """
        if plugin_name in self._plugins:
            self._plugins[plugin_name].enabled = True
            logger.info(f"Enabled plugin: {plugin_name}")

    def disable_plugin(self, plugin_name: str):
        """
        Disable a plugin.

        Args:
            plugin_name: Plugin name
        """
        if plugin_name in self._plugins:
            self._plugins[plugin_name].enabled = False
            logger.info(f"Disabled plugin: {plugin_name}")

    def get_plugin_info(self, plugin_name: str) -> dict[str, Any] | None:
        """
        Get plugin information.

        Args:
            plugin_name: Plugin name

        Returns:
            Plugin info dictionary
        """
        plugin = self._plugins.get(plugin_name)
        if not plugin:
            return None

        metadata = plugin.get_metadata()

        return {
            "name": metadata.name,
            "version": metadata.version,
            "description": metadata.description,
            "author": metadata.author,
            "dependencies": metadata.dependencies,
            "enabled": plugin.enabled,
            "tools_count": len(plugin.get_tools()),
            "commands_count": len(plugin.get_commands())
        }

    def get_all_plugin_info(self) -> dict[str, dict[str, Any]]:
        """Get information for all loaded plugins."""
        return {
            name: self.get_plugin_info(name)
            for name in self._plugins.keys()
        }

    def load_all_enabled_plugins(self):
        """Load all plugins that are enabled in config."""
        for plugin_name, plugin_config in self.config.items():
            if plugin_config.get("enabled", False):
                self.load_plugin(plugin_name)

        logger.info(f"Loaded {len(self._plugins)} plugins")

    def _read_verified_plugin(self, plugin_name: str, expected_hash: str) -> bytes | None:
        """Return the plugin file's bytes if its sha256 matches, else None.

        Only plain identifiers are accepted, so a dotted or path-like name can
        never point the check (or the import) at another file.
        """
        if not plugin_name.isidentifier():
            logger.error(f"Invalid plugin name: {plugin_name!r}")
            return None

        plugin_path = self.plugin_dir / f"{plugin_name}.py"
        if not plugin_path.is_file():
            logger.error(f"Plugin file not found: {plugin_path}")
            return None

        try:
            source = plugin_path.read_bytes()
        except OSError as e:
            logger.error(f"Failed to read plugin '{plugin_name}': {e}")
            return None

        actual = hashlib.sha256(source).hexdigest()
        if not hmac.compare_digest(actual.lower(), expected_hash.lower()):
            return None
        return source

    def _exec_plugin_source(self, plugin_name: str, source: bytes) -> types.ModuleType:
        """Execute verified plugin source as a fresh module (never a cached one)."""
        plugin_path = self.plugin_dir / f"{plugin_name}.py"
        module = types.ModuleType(f"crawllama_plugins.{plugin_name}")
        module.__file__ = str(plugin_path)
        exec(compile(source, str(plugin_path), "exec"), module.__dict__)  # nosec B102 - sha256-verified plugin
        if hasattr(module, "init_plugin"):
            module.init_plugin()
        return module


@lazy_singleton
def get_plugin_manager() -> PluginManager:
    """Get global plugin manager instance."""
    return PluginManager()
