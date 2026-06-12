"""Example plugin demonstrating plugin system capabilities."""
import logging
from collections.abc import Callable
from typing import Any

from core.plugin_manager import Plugin, PluginMetadata

logger = logging.getLogger("crawllama")


class ExamplePlugin(Plugin):
    """Example plugin showing basic plugin structure."""

    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            name="ExamplePlugin",
            version="1.0.0",
            description="Example plugin demonstrating plugin capabilities",
            author="CrawlLama Team",
            dependencies=[]
        )

    def initialize(self, config: dict[str, Any]):
        """
        Initialize plugin.

        Args:
            config: Plugin configuration
        """
        logger.info("ExamplePlugin initialized")
        self.config = config

    def shutdown(self):
        """Cleanup on shutdown."""
        logger.info("ExamplePlugin shutdown")

    def get_tools(self) -> list[Callable]:
        """
        Get tools provided by this plugin.

        Returns:
            List of tool functions
        """
        return [self.example_tool]

    def get_commands(self) -> dict[str, Callable]:
        """
        Get CLI commands.

        Returns:
            Dictionary of commands
        """
        return {
            "example": self.example_command
        }

    @staticmethod
    def example_tool(query: str) -> str:
        """
        Example tool function.

        Args:
            query: Input query

        Returns:
            Tool result
        """
        return f"ExamplePlugin processed: {query}"

    @staticmethod
    def example_command():
        """Example CLI command."""
        print("Example plugin command executed!")
        return "Command completed"


# Initialize plugin when module is loaded
def init_plugin():
    """Called when plugin is loaded."""
    logger.info("ExamplePlugin module loaded")


def cleanup_plugin():
    """Called when plugin is unloaded."""
    logger.info("ExamplePlugin module unloaded")
