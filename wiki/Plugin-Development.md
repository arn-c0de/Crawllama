# Plugin Development

CrawlLama features a flexible plugin system that allows extending functionality through custom plugins. All plugins are hash-verified and allowlisted for security.

## Plugin Architecture

All plugins inherit from the `Plugin` base class and should be placed in the `plugins/` directory.

### Base Plugin Structure

```python
from core.plugin_manager import Plugin, PluginMetadata

class MyPlugin(Plugin):
    def get_metadata(self) -> PluginMetadata:
        """Returns plugin metadata including name, version, and author."""
        pass

    def initialize(self, config: Dict[str, Any]):
        """Initialize the plugin with configuration parameters."""
        pass

    def shutdown(self):
        """Cleanup logic executed when the plugin is unloaded."""
        pass

    def get_tools(self) -> List[Callable]:
        """Returns a list of tools to be registered with the agent."""
        pass

    def get_commands(self) -> Dict[str, Callable]:
        """Returns custom CLI commands."""
        pass
```

## Creating a Simple Plugin

### 1. Create the Plugin File

Example: `plugins/hello_plugin.py`

```python
import logging
from typing import Dict, Any, List, Callable
from core.plugin_manager import Plugin, PluginMetadata

logger = logging.getLogger("crawllama")

class HelloPlugin(Plugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="HelloPlugin",
            version="1.0.0",
            description="Simple greeting plugin",
            author="Developer",
            dependencies=[]
        )

    def initialize(self, config: Dict[str, Any]):
        self.greeting = config.get("greeting", "Hello")
        logger.info("HelloPlugin initialized")

    def get_tools(self) -> List[Callable]:
        return [self.greet_tool]

    def greet_tool(self, name: str) -> str:
        """Greeting tool for the agent."""
        return f"{self.greeting}, {name}!"
```

### 2. Register the Plugin

Compute the SHA256 hash of your plugin file:

```bash
sha256sum plugins/hello_plugin.py
```

Add the plugin to your `config.json`:

```json
{
    "plugins": {
        "hello_plugin": {
            "enabled": true,
            "sha256": "your_generated_hash_here",
            "greeting": "Welcome"
        }
    }
}
```

## Security Requirements

To protect the local environment, CrawlLama enforces the following:
1. **Allowlisting:** Plugins must be explicitly defined in `config.json`.
2. **Hash Verification:** The `sha256` in the config must match the file on disk.
3. **Explicit Loading:** Plugins can be loaded or unloaded dynamically via CLI or API.

## Best Practices

- **Error Handling:** Wrap tool logic in try-except blocks to prevent agent crashes.
- **Logging:** Use the standard `crawllama` logger for consistent output.
- **Resource Management:** Implement the `shutdown` method to close database connections or file handles.
- **Lazy Loading:** Ensure heavy dependencies are only imported when the plugin is initialized.

---
[Back to Home](Home.md)
