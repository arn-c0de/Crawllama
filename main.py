"""CrawlLama - Local AI Search and Answer Agent

A fully local AI system that intelligently answers user queries by combining:
- Ollama (local LLM) for text understanding
- Autonomous web research with structured tool calls
- RAG (Retrieval-Augmented Generation) for context-based answers
"""
import argparse
import json
import sys
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.agent import SearchAgent
from utils.logger import setup_logger

console = Console()


def load_config(config_path: str = "config.json") -> dict:
    """Load configuration from JSON file."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(f"[red]Error: Config file not found: {config_path}[/red]")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Invalid JSON in config file: {e}[/red]")
        sys.exit(1)


def startup_check(config: dict) -> bool:
    """
    Perform startup health checks.

    Args:
        config: Configuration dictionary

    Returns:
        True if all checks pass
    """
    console.print("[cyan]Performing startup checks...[/cyan]")

    # Check Ollama connection
    from core.llm_client import OllamaClient

    llm_config = config.get("llm", {})
    client = OllamaClient(
        base_url=llm_config.get("base_url"),
        model=llm_config.get("model")
    )

    if not client._ensure_connection():
        console.print("[red]✗ Ollama is not running or not accessible[/red]")
        console.print("[yellow]Please start Ollama: ollama serve[/yellow]")
        return False

    console.print("[green]✓ Ollama connection successful[/green]")

    # Check directories
    for directory in ["data/cache", "data/embeddings", "logs"]:
        Path(directory).mkdir(parents=True, exist_ok=True)

    console.print("[green]✓ Directories initialized[/green]")
    return True


def interactive_mode(agent: SearchAgent):
    """
    Run agent in interactive mode.

    Args:
        agent: Initialized SearchAgent instance
    """
    console.print(Panel.fit(
        "[bold cyan]CrawlLama - Lokaler Such- und Antwort-Agent[/bold cyan]\n"
        "Stelle Fragen und erhalte intelligente Antworten.\n"
        "Befehle: [yellow]exit, quit, clear, stats[/yellow]",
        border_style="cyan"
    ))

    while True:
        try:
            # Get user input
            query = Prompt.ask("\n[bold cyan]❯[/bold cyan]")

            if not query.strip():
                continue

            # Handle commands
            if query.lower() in ["exit", "quit"]:
                console.print("[yellow]Auf Wiedersehen![/yellow]")
                break

            elif query.lower() == "clear":
                console.clear()
                continue

            elif query.lower() == "stats":
                stats = agent.get_stats()
                console.print("\n[bold]Agent Statistiken:[/bold]")
                console.print(json.dumps(stats, indent=2))
                continue

            # Process query
            console.print("\n[dim]Verarbeite Anfrage...[/dim]\n")
            response = agent.query(query)

            # Display response
            console.print(Markdown(response))

        except KeyboardInterrupt:
            console.print("\n[yellow]Unterbrochen. Verwende 'exit' zum Beenden.[/yellow]")
            continue
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def direct_query_mode(agent: SearchAgent, query: str):
    """
    Process single query and exit.

    Args:
        agent: Initialized SearchAgent instance
        query: Query string
    """
    try:
        console.print(f"[cyan]Frage:[/cyan] {query}\n")
        response = agent.query(query)
        console.print(Markdown(response))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="CrawlLama - Lokaler Such- und Antwort-Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  %(prog)s                                    # Interaktiver Modus
  %(prog)s "Was ist Python?"                  # Direkte Frage
  %(prog)s --no-web "Erkläre Photosynthese"   # Offline-Modus
  %(prog)s --model qwen2.5:3b "Frage"         # Anderes Modell
        """
    )

    parser.add_argument(
        "query",
        nargs="*",
        help="Direkte Frage (optional, startet interaktiven Modus wenn leer)"
    )

    parser.add_argument(
        "--config",
        default="config.json",
        help="Pfad zur Konfigurationsdatei (Standard: config.json)"
    )

    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Offline-Modus (keine Web-Suche)"
    )

    parser.add_argument(
        "--model",
        help="Ollama-Modell überschreiben (z.B. qwen2.5:3b, llama3:7b)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Debug-Modus aktivieren"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Agent-Statistiken anzeigen und beenden"
    )

    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Cache leeren und beenden"
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Load configuration
    config = load_config(args.config)

    # Override model if specified
    if args.model:
        config["llm"]["model"] = args.model

    # Setup logging
    log_config = config.get("logging", {})
    setup_logger(
        name="crawllama",
        log_file=log_config.get("file", "logs/app.log"),
        level="DEBUG" if args.debug else log_config.get("level", "INFO")
    )

    # Handle cache clearing
    if args.clear_cache:
        from core.cache import CacheManager
        cache = CacheManager()
        count = cache.clear()
        console.print(f"[green]Cache cleared: {count} files deleted[/green]")
        return

    # Startup checks
    if not startup_check(config):
        sys.exit(1)

    # Initialize agent
    try:
        agent = SearchAgent(
            config=config,
            enable_web=not args.no_web,
            debug=args.debug
        )
    except Exception as e:
        console.print(f"[red]Failed to initialize agent: {e}[/red]")
        sys.exit(1)

    # Handle stats display
    if args.stats:
        stats = agent.get_stats()
        console.print("\n[bold]Agent Statistiken:[/bold]")
        console.print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    # Run in appropriate mode
    if args.query:
        # Direct query mode
        query = " ".join(args.query)
        direct_query_mode(agent, query)
    else:
        # Interactive mode
        interactive_mode(agent)


if __name__ == "__main__":
    main()
