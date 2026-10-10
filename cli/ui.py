"""Shared Rich console instance for the CLI.

Kept in its own module so both ``main`` and the extracted CLI helpers can
import the same console without creating an import cycle between them.
"""
from rich.console import Console

console = Console()
