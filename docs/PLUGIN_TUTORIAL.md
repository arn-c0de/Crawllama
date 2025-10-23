# Plugin Development Tutorial

## Einführung

CrawlLama verfügt über ein flexibles Plugin-System, das es ermöglicht, die Funktionalität durch benutzerdefinierte Plugins zu erweitern.

## Plugin-Architektur

### Plugin-Struktur

```
plugins/
├── __init__.py
├── example_plugin.py
├── github_plugin.py
└── custom_plugin.py
```

### Basis-Plugin-Klasse

Alle Plugins erben von der `Plugin`-Basisklasse:

```python
from core.plugin_manager import Plugin, PluginMetadata

class MyPlugin(Plugin):
    def get_metadata(self) -> PluginMetadata:
        """Plugin-Metadaten."""
        pass

    def initialize(self, config: Dict[str, Any]):
        """Initialisierung mit Config."""
        pass

    def shutdown(self):
        """Aufräumen bei Shutdown."""
        pass

    def get_tools(self) -> List[Callable]:
        """Tools für den Agent."""
        pass

    def get_commands(self) -> Dict[str, Callable]:
        """CLI-Commands."""
        pass
```

## Einfaches Plugin erstellen

### Schritt 1: Plugin-Datei erstellen

```python
# plugins/hello_plugin.py

import logging
from typing import Dict, Any, List, Callable
from core.plugin_manager import Plugin, PluginMetadata

logger = logging.getLogger("crawllama")


class HelloPlugin(Plugin):
    """Simple hello world plugin."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="HelloPlugin",
            version="1.0.0",
            description="Simple greeting plugin",
            author="Your Name",
            dependencies=[]
        )

    def initialize(self, config: Dict[str, Any]):
        logger.info("HelloPlugin initialized")
        self.greeting = config.get("greeting", "Hello")

    def shutdown(self):
        logger.info("HelloPlugin shutdown")

    def get_tools(self) -> List[Callable]:
        return [self.greet_tool]

    def get_commands(self) -> Dict[str, Callable]:
        return {
            "greet": self.greet_command
        }

    def greet_tool(self, name: str) -> str:
        """Greeting tool for agent."""
        return f"{self.greeting}, {name}!"

    def greet_command(self):
        """CLI greeting command."""
        print(f"{self.greeting} from HelloPlugin!")
```

### Schritt 2: Plugin laden

```python
# In main.py oder interaktiv
from core.plugin_manager import get_plugin_manager

plugin_manager = get_plugin_manager()

# Plugin laden
plugin = plugin_manager.load_plugin("hello_plugin")

# Tool nutzen
result = plugin.greet_tool("World")
print(result)  # "Hello, World!"

# Command ausführen
plugin.greet_command()  # "Hello from HelloPlugin!"
```

### Schritt 3: Konfigurieren

```json
// config.json
{
  "plugins": {
    "hello_plugin": {
      "enabled": true,
      "greeting": "Hi"
    }
  }
}
```

## Fortgeschrittenes Plugin: GitHub Integration

### Plugin mit API-Zugriff

```python
# plugins/github_plugin.py

import requests
import logging
from typing import Dict, Any, List, Callable
from core.plugin_manager import Plugin, PluginMetadata

logger = logging.getLogger("crawllama")


class GitHubPlugin(Plugin):
    """GitHub integration plugin."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="GitHubPlugin",
            version="1.0.0",
            description="GitHub API integration",
            author="CrawlLama Team",
            dependencies=["requests"]
        )

    def initialize(self, config: Dict[str, Any]):
        self.api_key = config.get("github_api_key")
        self.base_url = "https://api.github.com"

        if not self.api_key:
            logger.warning("GitHub API key not configured")

        logger.info("GitHubPlugin initialized")

    def shutdown(self):
        logger.info("GitHubPlugin shutdown")

    def get_tools(self) -> List[Callable]:
        return [
            self.get_repo_info,
            self.search_repositories,
            self.get_user_info
        ]

    def get_commands(self) -> Dict[str, Callable]:
        return {
            "gh-repo": self.repo_command,
            "gh-search": self.search_command
        }

    def get_repo_info(self, repo_name: str) -> str:
        """
        Get repository information.

        Args:
            repo_name: Repository name (owner/repo)

        Returns:
            Repository info as string
        """
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"token {self.api_key}"

            url = f"{self.base_url}/repos/{repo_name}"
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()

                info = f"""
Repository: {data['full_name']}
Description: {data['description']}
Stars: {data['stargazers_count']}
Forks: {data['forks_count']}
Language: {data['language']}
Updated: {data['updated_at']}
URL: {data['html_url']}
                """

                return info.strip()
            else:
                return f"Error: {response.status_code}"

        except Exception as e:
            logger.error(f"GitHub API error: {e}")
            return f"Error fetching repo info: {str(e)}"

    def search_repositories(self, query: str, max_results: int = 5) -> str:
        """
        Search GitHub repositories.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            Search results as string
        """
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"token {self.api_key}"

            url = f"{self.base_url}/search/repositories"
            params = {
                "q": query,
                "per_page": max_results,
                "sort": "stars"
            }

            response = requests.get(url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                items = data['items']

                results = []
                for repo in items:
                    results.append(
                        f"{repo['full_name']} (⭐ {repo['stargazers_count']}): "
                        f"{repo['description']}"
                    )

                return "\n".join(results)
            else:
                return f"Error: {response.status_code}"

        except Exception as e:
            logger.error(f"GitHub search error: {e}")
            return f"Error searching repositories: {str(e)}"

    def get_user_info(self, username: str) -> str:
        """Get GitHub user information."""
        try:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"token {self.api_key}"

            url = f"{self.base_url}/users/{username}"
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()

                info = f"""
User: {data['login']}
Name: {data.get('name', 'N/A')}
Bio: {data.get('bio', 'N/A')}
Public Repos: {data['public_repos']}
Followers: {data['followers']}
Following: {data['following']}
Profile: {data['html_url']}
                """

                return info.strip()
            else:
                return f"Error: {response.status_code}"

        except Exception as e:
            logger.error(f"GitHub user info error: {e}")
            return f"Error fetching user info: {str(e)}"

    def repo_command(self, repo_name: str):
        """CLI command to get repo info."""
        print(self.get_repo_info(repo_name))

    def search_command(self, query: str):
        """CLI command to search repos."""
        print(self.search_repositories(query))
```

### Konfiguration

```json
{
  "plugins": {
    "github_plugin": {
      "enabled": true,
      "github_api_key": "your_github_token"
    }
  }
}
```

## Plugin Management

### Plugins auflisten

```bash
# Via CLI
python main.py --plugins

# Via API
curl http://localhost:8000/plugins
```

### Plugin laden

```bash
# Via CLI
python main.py --load-plugin github_plugin

# Via API
curl -X POST http://localhost:8000/plugins/github_plugin/load
```

### Plugin entladen

```python
plugin_manager = get_plugin_manager()
plugin_manager.unload_plugin("github_plugin")
```

## Best Practices

### 1. Fehlerbehandlung

```python
def get_tools(self) -> List[Callable]:
    """Always wrap tools in try/except."""
    return [self.safe_tool]

def safe_tool(self, input: str) -> str:
    try:
        # Tool logic
        result = self._process(input)
        return result
    except Exception as e:
        logger.error(f"Tool error: {e}")
        return f"Error: {str(e)}"
```

### 2. Konfiguration validieren

```python
def initialize(self, config: Dict[str, Any]):
    # Required settings
    required = ["api_key", "api_url"]

    for key in required:
        if key not in config:
            raise ValueError(f"Missing required config: {key}")

    self.api_key = config["api_key"]
    self.api_url = config["api_url"]
```

### 3. Ressourcen aufräumen

```python
def shutdown(self):
    """Always cleanup resources."""
    if hasattr(self, 'connection'):
        self.connection.close()

    if hasattr(self, 'temp_files'):
        for file in self.temp_files:
            os.remove(file)
```

### 4. Logging nutzen

```python
import logging

logger = logging.getLogger("crawllama")

def my_function(self):
    logger.debug("Debug info")
    logger.info("Info message")
    logger.warning("Warning")
    logger.error("Error occurred")
```

## Testing

### Plugin-Tests

```python
# tests/test_my_plugin.py

import pytest
from plugins.my_plugin import MyPlugin

def test_plugin_initialization():
    """Test plugin initialization."""
    config = {"setting": "value"}
    plugin = MyPlugin()
    plugin.initialize(config)

    assert plugin.enabled is True

def test_plugin_tool():
    """Test plugin tool."""
    plugin = MyPlugin()
    plugin.initialize({})

    result = plugin.my_tool("input")
    assert result is not None
```

## Deployment

### Plugin verteilen

1. **Als Python Package:**
```bash
# pyproject.toml
[project]
name = "crawllama-my-plugin"
version = "1.0.0"

[project.entry-points."crawllama.plugins"]
my_plugin = "my_plugin:MyPlugin"
```

2. **Als einzelne Datei:**
```bash
# Kopieren in plugins/ Verzeichnis
cp my_plugin.py /path/to/crawllama/plugins/
```

3. **Via Git:**
```bash
git clone https://github.com/user/my-plugin plugins/my_plugin
```

## Weitere Ressourcen

- [Plugin API Reference](API_DOCS.md)
- [Example Plugins](../plugins/)
- [Contributing Guide](CONTRIBUTING.md)
