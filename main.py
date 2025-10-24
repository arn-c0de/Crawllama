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
from rich.progress import Progress, BarColumn, TextColumn

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

    # Validate proxies if configured
    from utils.proxy_validator import ProxyValidator

    proxy_validator = ProxyValidator.load_from_env()
    if proxy_validator.is_configured():
        console.print("[cyan]Validating proxy configuration...[/cyan]")
        proxy_results = proxy_validator.validate_proxies()

        all_valid = all(proxy_results.values())
        if all_valid:
            console.print("[green]✓ Proxy configuration valid[/green]")
        else:
            console.print("[yellow]⚠ Some proxies failed validation (will proceed without proxy)[/yellow]")
    else:
        console.print("[dim]No proxy configured (direct connection)[/dim]")

    return True


def show_context_status(agent: SearchAgent):
    """
    Display current context usage and available tokens.

    Args:
        agent: SearchAgent instance
    """
    from rich.table import Table
    from rich.panel import Panel

    # Get configuration
    max_tokens = agent.config.get("llm", {}).get("max_tokens", 4096)

    # Calculate token usage
    conversation_tokens = 0
    for entry in agent.conversation_history:
        conversation_tokens += agent.context_manager.estimate_tokens(entry.get("query", ""))
        conversation_tokens += agent.context_manager.estimate_tokens(entry.get("response", ""))

    search_results_tokens = 0
    for result in agent.last_search_results:
        if isinstance(result, dict):
            search_results_tokens += agent.context_manager.estimate_tokens(
                result.get("title", "") + " " + result.get("snippet", "")
            )

    # Total used tokens
    total_used = conversation_tokens + search_results_tokens
    available_tokens = max_tokens - total_used
    usage_percent = (total_used / max_tokens * 100) if max_tokens > 0 else 0

    # Create table
    table = Table(title="Context Usage Tracker", show_header=True, header_style="bold cyan")
    table.add_column("Quelle", style="cyan", width=20)
    table.add_column("Tokens", style="yellow", justify="right", width=12)
    table.add_column("Anteil", style="dim", justify="right", width=12)

    table.add_row(
        "Konversation",
        f"{conversation_tokens:,}",
        f"{(conversation_tokens/max_tokens*100):.1f}%" if max_tokens > 0 else "0%"
    )
    table.add_row(
        "Suchergebnisse",
        f"{search_results_tokens:,}",
        f"{(search_results_tokens/max_tokens*100):.1f}%" if max_tokens > 0 else "0%"
    )
    table.add_row(
        "[bold]Gesamt verwendet[/bold]",
        f"[bold]{total_used:,}[/bold]",
        f"[bold]{usage_percent:.1f}%[/bold]"
    )
    table.add_row(
        "[green]Verfügbar[/green]",
        f"[green]{available_tokens:,}[/green]",
        f"[green]{(available_tokens/max_tokens*100):.1f}%[/green]"
    )
    table.add_row(
        "[dim]Maximum[/dim]",
        f"[dim]{max_tokens:,}[/dim]",
        "[dim]100%[/dim]"
    )

    console.print("\n")
    console.print(table)

    # Visual progress bar
    from rich.progress import BarColumn, Progress, TextColumn

    # Determine color based on usage
    if usage_percent < 50:
        color = "green"
    elif usage_percent < 80:
        color = "yellow"
    else:
        color = "red"

    console.print(f"\n[bold]Context Auslastung:[/bold]")
    console.print(f"[{color}]{'█' * int(usage_percent / 2)}[/{color}]{'░' * int((100 - usage_percent) / 2)} {usage_percent:.1f}%")

    # Session info
    console.print(f"\n[dim]Session Info:[/dim]")
    console.print(f"  • Konversationseinträge: {len(agent.conversation_history)}/{agent.max_history}")
    console.print(f"  • Gespeicherte Suchergebnisse: {len(agent.last_search_results)}")
    if agent.last_search_query:
        console.print(f"  • Letzte Suche: '{agent.last_search_query[:50]}...'")

    console.print()


def show_settings(config: dict):
    """
    Display current settings in a formatted way.

    Args:
        config: Configuration dictionary
    """
    from rich.table import Table

    table = Table(title="CrawlLama Einstellungen", show_header=True, header_style="bold cyan")
    table.add_column("Kategorie", style="cyan")
    table.add_column("Einstellung", style="yellow")
    table.add_column("Wert", style="green")

    # LLM Settings
    llm_config = config.get("llm", {})
    table.add_row("LLM", "Model", llm_config.get("model", "N/A"))
    table.add_row("", "Temperature", str(llm_config.get("temperature", "N/A")))
    table.add_row("", "Max Tokens", str(llm_config.get("max_tokens", "N/A")))
    table.add_row("", "Stream", str(llm_config.get("stream", "N/A")))

    # Search Settings
    search_config = config.get("search", {})
    table.add_row("Search", "Provider", search_config.get("provider", "N/A"))
    table.add_row("", "Max Results", str(search_config.get("max_results", "N/A")))
    table.add_row("", "Region", search_config.get("region", "N/A"))

    # RAG Settings
    rag_config = config.get("rag", {})
    table.add_row("RAG", "Enabled", str(rag_config.get("enabled", "N/A")))
    table.add_row("", "Embedding Model", rag_config.get("embedding_model", "N/A"))
    table.add_row("", "Top K", str(rag_config.get("top_k", "N/A")))

    # Cache Settings
    cache_config = config.get("cache", {})
    table.add_row("Cache", "Enabled", str(cache_config.get("enabled", "N/A")))
    table.add_row("", "TTL Hours", str(cache_config.get("ttl_hours", "N/A")))

    # OSINT Settings
    osint_config = config.get("osint", {})
    table.add_row("OSINT", "Max Results", str(osint_config.get("max_results", "N/A")))
    table.add_row("", "Email Search Limit", str(osint_config.get("email_search_limit", "N/A")))
    table.add_row("", "Phone Search Limit", str(osint_config.get("phone_search_limit", "N/A")))
    table.add_row("", "General OSINT Limit", str(osint_config.get("general_osint_limit", "N/A")))

    console.print("\n")
    console.print(table)
    console.print("\n")


def edit_settings(config: dict) -> dict:
    """
    Interactive settings editor.

    Args:
        config: Current configuration dictionary

    Returns:
        Updated configuration dictionary
    """
    console.print("\n[bold cyan]Settings Editor[/bold cyan]")
    console.print("[dim]Wähle die Kategorie aus, die du ändern möchtest[/dim]\n")

    # Category selection
    category_choice = Prompt.ask(
        "[cyan]Welche Kategorie möchtest du ändern?[/cyan]",
        choices=["llm", "search", "rag", "cache", "osint", "all"],
        default="all"
    )

    categories = [category_choice] if category_choice != "all" else ["llm", "search", "rag", "cache", "osint"]

    for category in categories:
        if category == "llm":
            console.print("\n[bold cyan]═══ LLM Einstellungen ═══[/bold cyan]")

            # LLM Model
            current_model = config.get("llm", {}).get("model", "qwen2.5:3b")
            new_model = Prompt.ask(
                f"[cyan]LLM Model[/cyan]",
                default=current_model
            )
            if new_model and new_model != current_model:
                config["llm"]["model"] = new_model
                console.print(f"[green]✓ Model geändert: {new_model}[/green]")

            # Temperature
            current_temp = config.get("llm", {}).get("temperature", 0.7)
            new_temp = Prompt.ask(
                f"[cyan]Temperature (0.0-1.0)[/cyan]",
                default=str(current_temp)
            )
            try:
                temp_value = float(new_temp)
                if 0.0 <= temp_value <= 1.0 and temp_value != current_temp:
                    config["llm"]["temperature"] = temp_value
                    console.print(f"[green]✓ Temperature geändert: {temp_value}[/green]")
            except ValueError:
                console.print("[yellow]Ungültiger Wert, überspringe...[/yellow]")

        elif category == "search":
            console.print("\n[bold cyan]═══ Search Einstellungen ═══[/bold cyan]")

            # Max Results
            current_max = config.get("search", {}).get("max_results", 10)
            new_max = Prompt.ask(
                f"[cyan]Max Search Results[/cyan]",
                default=str(current_max)
            )
            try:
                max_value = int(new_max)
                if max_value != current_max:
                    config["search"]["max_results"] = max_value
                    console.print(f"[green]✓ Max Results geändert: {max_value}[/green]")
            except ValueError:
                console.print("[yellow]Ungültiger Wert, überspringe...[/yellow]")

            # Region
            current_region = config.get("search", {}).get("region", "de-de")
            new_region = Prompt.ask(
                f"[cyan]Search Region (de-de, us-en, wt-wt)[/cyan]",
                default=current_region
            )
            if new_region and new_region != current_region:
                config["search"]["region"] = new_region
                console.print(f"[green]✓ Region geändert: {new_region}[/green]")

        elif category == "rag":
            console.print("\n[bold cyan]═══ RAG Einstellungen ═══[/bold cyan]")

            # RAG Enabled
            current_rag = config.get("rag", {}).get("enabled", True)
            rag_choice = Prompt.ask(
                f"[cyan]RAG aktivieren? (y/n)[/cyan]",
                default="y" if current_rag else "n",
                choices=["y", "n"]
            )
            new_rag = rag_choice.lower() == "y"
            if new_rag != current_rag:
                config["rag"]["enabled"] = new_rag
                console.print(f"[green]✓ RAG {'aktiviert' if new_rag else 'deaktiviert'}[/green]")

        elif category == "cache":
            console.print("\n[bold cyan]═══ Cache Einstellungen ═══[/bold cyan]")

            # Cache Enabled
            current_cache = config.get("cache", {}).get("enabled", True)
            cache_choice = Prompt.ask(
                f"[cyan]Cache aktivieren? (y/n)[/cyan]",
                default="y" if current_cache else "n",
                choices=["y", "n"]
            )
            new_cache = cache_choice.lower() == "y"
            if new_cache != current_cache:
                config["cache"]["enabled"] = new_cache
                console.print(f"[green]✓ Cache {'aktiviert' if new_cache else 'deaktiviert'}[/green]")

        elif category == "osint":
            console.print("\n[bold cyan]═══ OSINT Einstellungen ═══[/bold cyan]")

            # Ensure osint config exists
            if "osint" not in config:
                config["osint"] = {
                    "max_results": 20,
                    "email_search_limit": 50,
                    "phone_search_limit": 50,
                    "general_osint_limit": 100
                }

            # Max Results
            current_osint_max = config.get("osint", {}).get("max_results", 20)
            new_osint_max = Prompt.ask(
                f"[cyan]OSINT Max Results (1-50)[/cyan]",
                default=str(current_osint_max)
            )
            try:
                osint_max_value = int(new_osint_max)
                if 1 <= osint_max_value <= 50 and osint_max_value != current_osint_max:
                    config["osint"]["max_results"] = osint_max_value
                    console.print(f"[green]✓ OSINT Max Results geändert: {osint_max_value}[/green]")
            except ValueError:
                console.print("[yellow]Ungültiger Wert, überspringe...[/yellow]")

            # Email Search Limit
            current_email_limit = config.get("osint", {}).get("email_search_limit", 50)
            new_email_limit = Prompt.ask(
                f"[cyan]Email Search Limit pro Stunde[/cyan]",
                default=str(current_email_limit)
            )
            try:
                email_limit_value = int(new_email_limit)
                if email_limit_value != current_email_limit:
                    config["osint"]["email_search_limit"] = email_limit_value
                    console.print(f"[green]✓ Email Search Limit geändert: {email_limit_value}[/green]")
            except ValueError:
                console.print("[yellow]Ungültiger Wert, überspringe...[/yellow]")

            # Phone Search Limit
            current_phone_limit = config.get("osint", {}).get("phone_search_limit", 50)
            new_phone_limit = Prompt.ask(
                f"[cyan]Phone Search Limit pro Stunde[/cyan]",
                default=str(current_phone_limit)
            )
            try:
                phone_limit_value = int(new_phone_limit)
                if phone_limit_value != current_phone_limit:
                    config["osint"]["phone_search_limit"] = phone_limit_value
                    console.print(f"[green]✓ Phone Search Limit geändert: {phone_limit_value}[/green]")
            except ValueError:
                console.print("[yellow]Ungültiger Wert, überspringe...[/yellow]")

            # General OSINT Limit
            current_general_limit = config.get("osint", {}).get("general_osint_limit", 100)
            new_general_limit = Prompt.ask(
                f"[cyan]General OSINT Limit pro Stunde[/cyan]",
                default=str(current_general_limit)
            )
            try:
                general_limit_value = int(new_general_limit)
                if general_limit_value != current_general_limit:
                    config["osint"]["general_osint_limit"] = general_limit_value
                    console.print(f"[green]✓ General OSINT Limit geändert: {general_limit_value}[/green]")
            except ValueError:
                console.print("[yellow]Ungültiger Wert, überspringe...[/yellow]")

    return config


def save_config(config: dict, config_path: str = "config.json"):
    """
    Save configuration to JSON file.

    Args:
        config: Configuration dictionary
        config_path: Path to config file
    """
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        console.print(f"[green]✓ Konfiguration gespeichert: {config_path}[/green]")
        return True
    except Exception as e:
        console.print(f"[red]✗ Fehler beim Speichern: {e}[/red]")
        return False


def interactive_mode(agent: SearchAgent):
    """
    Run agent in interactive mode.

    Args:
        agent: Initialized SearchAgent instance
    """
    # Check OSINT terms acceptance on startup
    from core.osint import OSINTCompliance
    compliance = OSINTCompliance(config=agent.config)

    if not compliance.check_terms_accepted("default"):
        console.print("\n[bold yellow]═══ OSINT Features verfügbar ═══[/bold yellow]")
        console.print("[dim]CrawlLama v1.2 enthält OSINT-Features für Email/Phone Intelligence.[/dim]")
        console.print("[dim]Operatoren: email:, phone:, site:, inurl:, etc.[/dim]\n")

        console.print(compliance.display_terms())

        accept_choice = Prompt.ask(
            "\n[cyan]Möchten Sie die OSINT Terms of Use akzeptieren?[/cyan]",
            choices=["accept", "decline"],
            default="accept"
        )

        if accept_choice.lower() == "accept":
            compliance.accept_terms("default")
            console.print("[green]✓ OSINT Terms akzeptiert. Sie können jetzt OSINT-Features nutzen![/green]")
            console.print("[dim]Beispiele: email:test@example.com, phone:\"+49 151 12345678\", site:github.com[/dim]\n")
        else:
            console.print("[yellow]⚠ OSINT Features werden nicht aktiviert.[/yellow]")
            console.print("[dim]Sie können normale Suche weiterhin nutzen.[/dim]\n")

    console.print(Panel.fit(
        "[bold cyan]CrawlLama - Lokaler Such- und Antwort-Agent[/bold cyan]\n"
        "Stelle Fragen und erhalte intelligente Antworten.\n\n"
        "Befehle:\n"
        "  [yellow]clear[/yellow]       - Session zurücksetzen (Historie + Cache)\n"
        "  [yellow]clear-cache[/yellow] - Nur Cache löschen\n"
        "  [yellow]save[/yellow]        - Session manuell speichern\n"
        "  [yellow]load[/yellow]        - Session neu laden\n"
        "  [yellow]stats[/yellow]       - Statistiken anzeigen\n"
        "  [yellow]status[/yellow]      - Context-Verbrauch anzeigen\n"
        "  [yellow]settings[/yellow]    - Einstellungen anzeigen/ändern\n"
        "  [yellow]restart[/yellow]     - Agent neu starten (Config neu laden)\n"
        "  [yellow]exit, quit[/yellow]  - Beenden\n\n"
        "Spezial-Syntax:\n"
        "  [yellow]< frage[/yellow]     - Nur Kontext nutzen (keine Web-Suche)\n"
        "  [dim]Beispiel: \"< wer ist er denn?\" nutzt nur Gesprächshistorie[/dim]\n\n"
        "[dim]Session wird automatisch gespeichert und beim Start geladen.[/dim]",
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
                # Clear session data
                stats = agent.clear_session()
                console.clear()
                console.print(f"[green]✓ Session zurückgesetzt:[/green]")
                console.print(f"  • {stats['conversation_entries']} Konversationseinträge gelöscht")
                console.print(f"  • {stats['search_results']} Suchergebnisse gelöscht")
                console.print(f"  • {stats['cache_files']} Cache-Dateien gelöscht")
                continue

            elif query.lower() == "stats":
                stats = agent.get_stats()
                console.print("\n[bold]Agent Statistiken:[/bold]")
                console.print(json.dumps(stats, indent=2))
                continue

            elif query.lower() == "status":
                # Show context usage
                show_context_status(agent)
                continue

            elif query.lower() == "clear-cache":
                from core.cache import CacheManager
                cache = CacheManager()
                count = cache.clear()
                console.print(f"[green]Cache gelöscht: {count} Dateien entfernt[/green]")
                continue

            elif query.lower() == "save":
                # Manually save session
                success = agent.save_session()
                if success:
                    console.print(f"[green]✓ Session gespeichert:[/green]")
                    console.print(f"  • {len(agent.conversation_history)} Konversationseinträge")
                    console.print(f"  • {len(agent.last_search_results)} Suchergebnisse")
                    console.print(f"  • Datei: data/session.json")
                else:
                    console.print(f"[red]✗ Fehler beim Speichern der Session[/red]")
                continue

            elif query.lower() == "load":
                # Reload session
                success = agent.load_session()
                if success:
                    console.print(f"[green]✓ Session geladen:[/green]")
                    console.print(f"  • {len(agent.conversation_history)} Konversationseinträge")
                    console.print(f"  • {len(agent.last_search_results)} Suchergebnisse")
                else:
                    console.print(f"[yellow]⚠ Keine gespeicherte Session gefunden[/yellow]")
                continue

            elif query.lower() == "settings":
                # Settings menu
                show_settings(agent.config)

                edit_choice = Prompt.ask(
                    "\n[cyan]Möchtest du die Einstellungen ändern?[/cyan]",
                    choices=["y", "n"],
                    default="n"
                )

                if edit_choice.lower() == "y":
                    agent.config = edit_settings(agent.config)

                    save_choice = Prompt.ask(
                        "\n[cyan]Einstellungen speichern?[/cyan]",
                        choices=["y", "n"],
                        default="y"
                    )

                    if save_choice.lower() == "y":
                        save_config(agent.config)

                        restart_choice = Prompt.ask(
                            "\n[cyan]Agent neu starten um Änderungen zu übernehmen?[/cyan]",
                            choices=["y", "n"],
                            default="y"
                        )

                        if restart_choice.lower() == "y":
                            console.print("[yellow]Agent wird neu gestartet...[/yellow]")
                            return "RESTART"  # Signal to restart agent
                        else:
                            console.print("[yellow]⚠ Einige Änderungen werden erst nach einem Neustart wirksam.[/yellow]")

                continue

            elif query.lower() == "restart":
                # Restart agent
                console.print("[yellow]Agent wird neu gestartet...[/yellow]")

                # Ask if session should be saved
                save_choice = Prompt.ask(
                    "[cyan]Session vor Neustart speichern?[/cyan]",
                    choices=["y", "n"],
                    default="y"
                )

                if save_choice.lower() == "y":
                    agent.save_session()
                    console.print("[green]✓ Session gespeichert[/green]")

                return "RESTART"  # Signal to restart agent

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

    parser.add_argument(
        "--setup-keys",
        action="store_true",
        help="Interaktives Setup für API-Keys"
    )

    args = parser.parse_args()

    # Handle API key setup
    if args.setup_keys:
        from utils.secure_config import SecureConfig
        config_manager = SecureConfig()
        config_manager.setup_interactive()
        return

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

    # Auto-clear cache on startup
    console.print("[cyan]Clearing cache on startup...[/cyan]")
    from core.cache import CacheManager
    cache = CacheManager(
        cache_dir=config.get("cache", {}).get("cache_dir", "data/cache"),
        ttl_hours=config.get("cache", {}).get("ttl_hours", 24)
    )
    cleared_count = cache.clear()
    console.print(f"[green]✓ Cache cleared: {cleared_count} files deleted[/green]")

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
        # Interactive mode with restart support
        while True:
            result = interactive_mode(agent)

            if result == "RESTART":
                # Reload configuration
                console.print("[cyan]Lade Konfiguration neu...[/cyan]")
                config = load_config(args.config)

                # Override model if specified
                if args.model:
                    config["llm"]["model"] = args.model

                # Reinitialize agent
                try:
                    console.print("[cyan]Initialisiere Agent neu...[/cyan]")
                    agent = SearchAgent(
                        config=config,
                        enable_web=not args.no_web,
                        debug=args.debug
                    )
                    console.print("[green]✓ Agent erfolgreich neu gestartet![/green]\n")
                except Exception as e:
                    console.print(f"[red]Fehler beim Neustart: {e}[/red]")
                    console.print("[yellow]Fahre mit altem Agent fort...[/yellow]\n")
            else:
                # Normal exit
                break


if __name__ == "__main__":
    main()
