"""Enhanced CLI helper utilities with rich formatting."""
import logging
from typing import Any

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

logger = logging.getLogger("crawllama")
console = Console()


class CLIHelper:
    """Enhanced CLI helper with rich formatting."""

    def __init__(self):
        """Initialize CLI helper."""
        self.console = console

    def print_header(self, title: str, subtitle: str | None = None):
        """
        Print formatted header.

        Args:
            title: Main title
            subtitle: Optional subtitle
        """
        if subtitle:
            text = f"[bold cyan]{title}[/bold cyan]\n[dim]{subtitle}[/dim]"
        else:
            text = f"[bold cyan]{title}[/bold cyan]"

        self.console.print(Panel(text, box=box.DOUBLE))

    def print_section(self, title: str):
        """
        Print section header.

        Args:
            title: Section title
        """
        self.console.print(f"\n[bold yellow]━━━ {title} ━━━[/bold yellow]\n")

    def print_success(self, message: str):
        """Print success message."""
        self.console.print(f"[green]✓[/green] {message}")

    def print_error(self, message: str):
        """Print error message."""
        self.console.print(f"[red]✗[/red] {message}")

    def print_warning(self, message: str):
        """Print warning message."""
        self.console.print(f"[yellow]⚠[/yellow] {message}")

    def print_info(self, message: str):
        """Print info message."""
        self.console.print(f"[blue]ℹ[/blue] {message}")

    def print_table(
        self,
        title: str,
        columns: list[str],
        rows: list[list[str]],
        show_header: bool = True
    ):
        """
        Print formatted table.

        Args:
            title: Table title
            columns: Column headers
            rows: Table rows
            show_header: Show column headers
        """
        table = Table(title=title, box=box.ROUNDED, show_header=show_header)

        for col in columns:
            table.add_column(col, style="cyan")

        for row in rows:
            table.add_row(*row)

        self.console.print(table)

    def print_tree(self, title: str, data: dict[str, Any]):
        """
        Print tree structure.

        Args:
            title: Tree title
            data: Nested dictionary for tree
        """
        tree = Tree(f"[bold]{title}[/bold]")
        self._build_tree(tree, data)
        self.console.print(tree)

    def _build_tree(self, tree: Tree, data: Any, max_depth: int = 3, current_depth: int = 0):
        """
        Recursively build tree structure.

        Args:
            tree: Tree node
            data: Data to add
            max_depth: Maximum nesting depth
            current_depth: Current depth
        """
        if current_depth >= max_depth:
            return

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    branch = tree.add(f"[yellow]{key}[/yellow]")
                    self._build_tree(branch, value, max_depth, current_depth + 1)
                else:
                    tree.add(f"[yellow]{key}[/yellow]: [green]{value}[/green]")

        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    branch = tree.add(f"[cyan]Item {i}[/cyan]")
                    self._build_tree(branch, item, max_depth, current_depth + 1)
                else:
                    tree.add(f"[cyan]•[/cyan] {item}")

    def print_markdown(self, markdown_text: str):
        """
        Print markdown formatted text.

        Args:
            markdown_text: Markdown text
        """
        md = Markdown(markdown_text)
        self.console.print(md)

    def print_stats(self, stats: dict[str, Any]):
        """
        Print statistics in formatted table.

        Args:
            stats: Statistics dictionary
        """
        table = Table(title="Statistics", box=box.SIMPLE)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        for key, value in stats.items():
            table.add_row(str(key), str(value))

        self.console.print(table)

    def progress_spinner(self, description: str = "Processing..."):
        """
        Create progress spinner context.

        Args:
            description: Progress description

        Returns:
            Progress context manager
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True
        )


def print_help_extended():
    """Print extended help information."""
    console = Console()

    console.print("\n[bold cyan]CrawlLama - AI-Powered Web Research Agent[/bold cyan]\n")

    # Basic usage
    console.print("[bold yellow]Basic Usage:[/bold yellow]")
    console.print("  python main.py \"your question\"")
    console.print("  python main.py --interactive\n")

    # Arguments table
    table = Table(title="Command Line Arguments", box=box.ROUNDED)
    table.add_column("Argument", style="cyan")
    table.add_column("Description", style="white")

    args = [
        ("--debug", "Enable debug logging"),
        ("--no-web", "Disable web search (offline mode)"),
        ("--interactive", "Start interactive mode"),
        ("--setup-keys", "Setup API keys securely"),
        ("--multihop", "Use multi-hop reasoning for complex queries"),
        ("--stats", "Show system statistics"),
        ("--plugins", "List available plugins"),
        ("--load-plugin NAME", "Load a specific plugin"),
        ("--api", "Start API server"),
        ("--help-extended", "Show this extended help"),
    ]

    for arg, desc in args:
        table.add_row(arg, desc)

    console.print(table)

    # Examples
    console.print("\n[bold yellow]Examples:[/bold yellow]")
    examples = [
        ("Simple query", 'python main.py "What is Python?"'),
        ("Multi-hop reasoning", 'python main.py --multihop "Compare Python and JavaScript"'),
        ("Offline mode", 'python main.py --no-web "Explain machine learning"'),
        ("Interactive mode", 'python main.py --interactive'),
        ("API server", 'python main.py --api'),
    ]

    for title, cmd in examples:
        console.print(f"  [green]•[/green] {title}:")
        console.print(f"    [dim]{cmd}[/dim]\n")


def print_memory_help():
    """Print memory store help information."""
    console = Console()

    help_md = """
# Persistent Memory Store Commands

The memory store persists OSINT data across sessions (survives `clear` command).

## Memory Commands

### Remember (Store Data)
```bash
remember email:test@example.com           # Remember an email
remember phone:+491234567890              # Remember a phone
remember ip:192.168.1.1                   # Remember an IP
remember username:johndoe                 # Remember a username
remember domain:example.com               # Remember a domain
remember note:"Important finding about X" # Add a note
```

### Recall (View Data)
```bash
recall                    # Show all stored data summary
recall emails            # Show all emails
recall phones            # Show all phones
recall ips               # Show all IPs
recall usernames         # Show all usernames
recall domains           # Show all domains
recall notes             # Show all notes
recall search:keyword    # Search across all categories
```

### Forget (Delete Data)
```bash
forget email:test@example.com    # Remove specific email
forget phone:+491234567890       # Remove specific phone
forget ip:192.168.1.1           # Remove specific IP
forget username:johndoe          # Remove specific username
forget category:emails           # Clear all emails
forget category:phones           # Clear all phones
forget all                       # Clear entire memory (WARNING!)
```

### Export/Import
```bash
export memory:backup.json        # Export memory to file
import memory:backup.json        # Import memory from file
import memory:backup.json merge  # Merge with existing data
```

## Natural Language Integration

You can also ask the agent to remember things naturally:
```
"Remember all emails from source [1]"
"Save the phone numbers from the last search"
"Show me all saved IPs"
"Forget the email test@example.com"
```

The agent will automatically extract and store relevant data from OSINT results.
    """

    console.print(Markdown(help_md))


def print_examples():
    """Print usage examples."""
    console = Console()

    examples_md = """
# CrawlLama Usage Examples

## Basic Queries
```bash
python main.py "What is machine learning?"
python main.py "Latest news about AI"
```

## Multi-Hop Reasoning
For complex queries requiring multiple steps:
```bash
python main.py --multihop "Compare Python and JavaScript for web development"
python main.py --multihop "What are the pros and cons of electric vehicles?"
```

## Reading Web Pages
```bash
python main.py "What is on https://example.com"
```

## Interactive Mode
```bash
python main.py --interactive
# Then type your questions interactively
```

## OSINT Intelligence
```bash
# Single target queries
python main.py "email:test@example.com"
python main.py "phone:+491234567890"
python main.py "ip:8.8.8.8"
python main.py "username:johndoe"

# Batch processing (multiple targets)
python main.py "email:test@example.com user@domain.com admin@site.com"
python main.py "phone:+491234567890 +441234567890 +331234567890"

# Remember findings for later
python main.py "email:test@example.com"
# Then: remember email:test@example.com
# Or: "Merke dir diese Email"
```

## API Server
```bash
# Start API server
python main.py --api

# Query via API (in another terminal)
curl -X POST http://localhost:8000/query \\
  -H "Content-Type: application/json" \\
  -d '{"query": "What is Python?", "use_multihop": false}'
```

## Plugin Management
```bash
# List plugins
python main.py --plugins

# Load plugin
python main.py --load-plugin example_plugin
```

## System Statistics
```bash
python main.py --stats
```
    """

    console.print(Markdown(examples_md))


def visualize_reasoning_path(reasoning_path: list[str]):
    """
    Visualize multi-hop reasoning path.

    Args:
        reasoning_path: List of reasoning steps
    """
    console = Console()

    tree = Tree("[bold cyan]Reasoning Path[/bold cyan]")

    for i, step in enumerate(reasoning_path, 1):
        tree.add(f"[yellow]Step {i}:[/yellow] {step}")

    console.print(tree)


def visualize_search_results(results: list[dict[str, Any]]):
    """
    Visualize search results.

    Args:
        results: List of search result dictionaries
    """
    console = Console()

    table = Table(title="Search Results", box=box.ROUNDED)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Source", style="yellow")
    table.add_column("Relevance", style="green", width=10)
    table.add_column("Preview", style="white")

    for i, result in enumerate(results[:10], 1):
        source = result.get("metadata", {}).get("source", "Unknown")
        relevance = f"{result.get('relevance', 0):.2%}"
        preview = result.get("text", "")[:80] + "..."

        table.add_row(str(i), source, relevance, preview)

    console.print(table)


def show_system_info(stats: dict[str, Any]):
    """
    Show system information in formatted panels.

    Args:
        stats: System statistics
    """
    console = Console()

    # Agent stats
    agent_stats = stats.get("agent_stats", {})
    if agent_stats:
        agent_table = Table(box=box.SIMPLE, show_header=False)
        agent_table.add_column("Metric", style="cyan")
        agent_table.add_column("Value", style="green")

        for key, value in agent_stats.items():
            agent_table.add_row(str(key), str(value))

        console.print(Panel(agent_table, title="Agent Statistics", border_style="blue"))

    # Resource stats
    resource_stats = stats.get("resource_stats", {})
    if resource_stats:
        memory = resource_stats.get("memory", {})
        if memory:
            mem_table = Table(box=box.SIMPLE, show_header=False)
            mem_table.add_column("Metric", style="cyan")
            mem_table.add_column("Value", style="green")

            mem_table.add_row("Current Memory", f"{memory.get('current_rss_mb', 0):.1f} MB")
            mem_table.add_row("Peak Memory", f"{memory.get('peak_rss_mb', 0):.1f} MB")
            mem_table.add_row("Usage", f"{memory.get('current_percent', 0):.1f}%")

            console.print(Panel(mem_table, title="Memory Usage", border_style="yellow"))


# Global CLI helper instance
_cli_helper = None


def get_cli_helper() -> CLIHelper:
    """Get global CLI helper instance."""
    global _cli_helper
    if _cli_helper is None:
        _cli_helper = CLIHelper()
    return _cli_helper
