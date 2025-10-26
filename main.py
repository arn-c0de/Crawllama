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
import re
from typing import Union, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


class CrawllamaException(Exception):
    """Custom exception for Crawllama application errors."""
    
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code
        self.message = message


class InputValidator:
    """Input validation helper for settings."""
    
    @staticmethod
    def validate_float(value: str, min_val: float = None, max_val: float = None) -> Optional[float]:
        """Validate and convert string to float within bounds."""
        try:
            float_val = float(value)
            if min_val is not None and float_val < min_val:
                return None
            if max_val is not None and float_val > max_val:
                return None
            return float_val
        except ValueError:
            return None
            
    @staticmethod
    def validate_int(value: str, min_val: int = None, max_val: int = None) -> Optional[int]:
        """Validate and convert string to int within bounds."""
        try:
            int_val = int(value)
            if min_val is not None and int_val < min_val:
                return None
            if max_val is not None and int_val > max_val:
                return None
            return int_val
        except ValueError:
            return None
            
    @staticmethod
    def validate_url(value: str) -> bool:
        """Validate URL format."""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return bool(url_pattern.match(value))
        
    @staticmethod
    def validate_model_name(value: str) -> bool:
        """Validate LLM model name format."""
        if not value or len(value) < 2:
            return False
        # Allow alphanumeric, dots, colons, hyphens, underscores
        pattern = re.compile(r'^[a-zA-Z0-9._:-]+$')
        return bool(pattern.match(value))

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
        raise CrawllamaException(f"Config file not found: {config_path}", 1)
    except json.JSONDecodeError as e:
        raise CrawllamaException(f"Invalid JSON in config file: {e}", 1)


def startup_check(config: dict) -> dict:
    """
    Perform startup health checks.

    Args:
        config: Configuration dictionary

    Returns:
        Dict with component status and error messages
    """
    console.print("[cyan]Performing startup checks...[/cyan]")
    results = {}

    # Check Ollama connection
    from core.llm_client import OllamaClient
    llm_config = config.get("llm", {})
    client = OllamaClient(
        base_url=llm_config.get("base_url"),
        model=llm_config.get("model"),
        timeout=llm_config.get("timeout", 120)
    )
    if not client._ensure_connection():
        msg = "Ollama is not running or not accessible. Please start Ollama: ollama serve"
        console.print(f"[red]✗ {msg}[/red]")
        results["ollama"] = {"status": False, "error_msg": msg}
    else:
        console.print("[green]✓ Ollama connection successful[/green]")
        results["ollama"] = {"status": True, "error_msg": ""}

    # Check directories (from config)
    paths_config = config.get("paths", {})
    directories = [
        paths_config.get("cache_dir", "data/cache"),
        paths_config.get("embeddings_dir", "data/embeddings"),
        paths_config.get("logs_dir", "logs")
    ]
    dir_errors = []
    for directory in directories:
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            dir_errors.append(f"{directory}: {e}")

    if dir_errors:
        console.print(f"[red]✗ Directory initialization failed: {dir_errors}[/red]")
        results["directories"] = {"status": False, "error_msg": "; ".join(dir_errors)}
    else:
        console.print("[green]✓ Directories initialized[/green]")
        results["directories"] = {"status": True, "error_msg": ""}

    # Validate proxies if configured
    from utils.proxy_validator import ProxyValidator
    proxy_validator = ProxyValidator.load_from_env()
    if proxy_validator.is_configured():
        console.print("[cyan]Validating proxy configuration...[/cyan]")
        proxy_results = proxy_validator.validate_proxies()
        all_valid = all(proxy_results.values())
        if all_valid:
            console.print("[green]✓ Proxy configuration valid[/green]")
            results["proxy"] = {"status": True, "error_msg": ""}
        else:
            msg = "Some proxies failed validation (will proceed without proxy)"
            console.print(f"[yellow]⚠ {msg}[/yellow]")
            results["proxy"] = {"status": False, "error_msg": msg}
    else:
        console.print("[dim]No proxy configured (direct connection)[/dim]")
        results["proxy"] = {"status": True, "error_msg": ""}

    return results


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
    table.add_row("", "Safesearch", str(osint_config.get("safesearch", "N/A")))

    # Memory Store Settings
    memory_config = config.get("memory", {})
    table.add_row("Memory", "Enabled", str(memory_config.get("enabled", "N/A")))
    table.add_row("", "Auto Clear on Clear", str(memory_config.get("auto_clear_on_clear", "N/A")))
    table.add_row("", "Max Entries", str(memory_config.get("max_entries", "N/A")))
    table.add_row("", "Max File Size (MB)", str(memory_config.get("max_file_size_mb", "N/A")))
    table.add_row("", "File Path", str(memory_config.get("file_path", "N/A")))

    # Hallucination Detection Settings
    hallu_config = config.get("hallucination_detection", {})
    table.add_row("Hallucination", "Enabled", str(hallu_config.get("enabled", "N/A")))
    table.add_row("", "Detection Level", str(hallu_config.get("detection_level", "N/A")))
    table.add_row("", "Warning Mode", str(hallu_config.get("warning_mode", "N/A")))
    table.add_row("", "Threshold", str(hallu_config.get("hallucination_threshold", "N/A")))
    table.add_row("", "Context Alignment", str(hallu_config.get("context_alignment_threshold", "N/A")))
    table.add_row("", "Fact Checking", str(hallu_config.get("fact_checking_enabled", "N/A")))
    table.add_row("", "Max Processing Time", str(hallu_config.get("max_processing_time", "N/A")))

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
        choices=["llm", "search", "rag", "cache", "osint", "memory", "hallucination", "all"],
        default="all"
    )

    categories = [category_choice] if category_choice != "all" else ["llm", "search", "rag", "cache", "osint", "memory", "hallucination"]

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
                if InputValidator.validate_model_name(new_model):
                    config["llm"]["model"] = new_model
                    console.print(f"[green]✓ Model geändert: {new_model}[/green]")
                else:
                    console.print("[red]❌ Ungültiger Model-Name! Erlaubt: Buchstaben, Zahlen, '.', ':', '-', '_'[/red]")

            # Temperature
            current_temp = config.get("llm", {}).get("temperature", 0.7)
            new_temp = Prompt.ask(
                f"[cyan]Temperature (0.0-1.0)[/cyan]",
                default=str(current_temp)
            )
            
            temp_value = InputValidator.validate_float(new_temp, 0.0, 1.0)
            if temp_value is not None and temp_value != current_temp:
                config["llm"]["temperature"] = temp_value
                console.print(f"[green]✓ Temperature geändert: {temp_value}[/green]")
            elif temp_value is None:
                console.print("[red]❌ Ungültiger Wert! Temperature muss zwischen 0.0 und 1.0 liegen.[/red]")

            # Max Tokens (Context Size)
            current_tokens = config.get("llm", {}).get("max_tokens", 10000)
            new_tokens = Prompt.ask(
                f"[cyan]Max Tokens / Context Size (1000-32000)[/cyan]",
                default=str(current_tokens)
            )
            
            tokens_value = InputValidator.validate_int(new_tokens, 1000, 32000)
            if tokens_value is not None and tokens_value != current_tokens:
                config["llm"]["max_tokens"] = tokens_value
                console.print(f"[green]✓ Max Tokens geändert: {tokens_value}[/green]")
                console.print("[dim]Empfohlung: RTX 3080+ → 10k-16k, RTX 3060/70 → 6k-8k, CPU → 2k-4k[/dim]")
            elif tokens_value is None:
                console.print("[red]❌ Ungültiger Wert! Max Tokens muss zwischen 1000 und 32000 liegen.[/red]")

        elif category == "search":
            console.print("\n[bold cyan]═══ Search Einstellungen ═══[/bold cyan]")

            # Max Results
            current_max = config.get("search", {}).get("max_results", 10)
            new_max = Prompt.ask(
                f"[cyan]Max Search Results (1-100)[/cyan]",
                default=str(current_max)
            )
            
            max_value = InputValidator.validate_int(new_max, 1, 100)
            if max_value is not None and max_value != current_max:
                config["search"]["max_results"] = max_value
                console.print(f"[green]✓ Max Results geändert: {max_value}[/green]")
            elif max_value is None:
                console.print("[red]❌ Ungültiger Wert! Max Results muss zwischen 1 und 100 liegen.[/red]")

            # Region
            current_region = config.get("search", {}).get("region", "de-de")
            new_region = Prompt.ask(
                f"[cyan]Search Region[/cyan]",
                choices=["de-de", "us-en", "wt-wt", "gb-en", "fr-fr"],
                default=current_region
            )
            if new_region and new_region != current_region:
                config["search"]["region"] = new_region
                console.print(f"[green]✓ Region geändert: {new_region}[/green]")

        elif category == "rag":
            console.print("\n[bold cyan]═══ RAG Einstellungen ═══[/bold cyan]")

            # Ensure rag config exists
            if "rag" not in config:
                config["rag"] = {
                    "enabled": True,
                    "embedding_model": "nomic-embed-text",
                    "top_k": 5
                }

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

            # Embedding Model
            current_model = config.get("rag", {}).get("embedding_model", "nomic-embed-text")
            new_model = Prompt.ask(
                f"[cyan]Embedding Model[/cyan]",
                default=current_model
            )
            if new_model != current_model:
                config["rag"]["embedding_model"] = new_model
                console.print(f"[green]✓ Embedding Model geändert: {new_model}[/green]")

            # Top K
            current_topk = config.get("rag", {}).get("top_k", 5)
            new_topk = Prompt.ask(
                f"[cyan]Top K (Anzahl der RAG-Dokumente, 1-20)[/cyan]",
                default=str(current_topk)
            )
            
            topk_value = InputValidator.validate_int(new_topk, 1, 20)
            if topk_value is not None and topk_value != current_topk:
                config["rag"]["top_k"] = topk_value
                console.print(f"[green]✓ Top K geändert: {topk_value}[/green]")
            elif topk_value is None:
                console.print("[red]❌ Ungültiger Wert! Top K muss zwischen 1 und 20 liegen.[/red]")

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

            # Safesearch Mode
            current_safesearch = config.get("osint", {}).get("safesearch", "strict")
            console.print(f"\n[dim]Safesearch verbessert die Suchergebnisqualität bei OSINT-Recherchen[/dim]")
            console.print(f"[dim]  • off: Keine Filterung[/dim]")
            console.print(f"[dim]  • moderate: Moderate Filterung (Standard DuckDuckGo)[/dim]")
            console.print(f"[dim]  • strict: Strenge Filterung (empfohlen für beste Qualität)[/dim]")
            new_safesearch = Prompt.ask(
                f"[cyan]Safesearch Mode[/cyan]",
                choices=["off", "moderate", "strict"],
                default=current_safesearch
            )
            if new_safesearch and new_safesearch != current_safesearch:
                config["osint"]["safesearch"] = new_safesearch
                console.print(f"[green]✓ Safesearch Mode geändert: {new_safesearch}[/green]")

        elif category == "memory":
            console.print("\n[bold cyan]═══ Memory Store Einstellungen ═══[/bold cyan]")

            # Ensure memory config exists
            if "memory" not in config:
                config["memory"] = {
                    "enabled": True,
                    "auto_clear_on_clear": False,
                    "max_entries": 1000,
                    "max_file_size_mb": 10,
                    "file_path": "data/memory.json"
                }

            # Enabled
            current_memory_enabled = config.get("memory", {}).get("enabled", True)
            new_memory_enabled = Prompt.ask(
                f"[cyan]Memory Store Enabled (true/false)[/cyan]",
                choices=["true", "false"],
                default=str(current_memory_enabled).lower()
            )
            if new_memory_enabled != str(current_memory_enabled).lower():
                config["memory"]["enabled"] = (new_memory_enabled == "true")
                console.print(f"[green]✓ Memory Store Enabled geändert: {new_memory_enabled}[/green]")

            # Auto Clear on Clear Command
            current_auto_clear = config.get("memory", {}).get("auto_clear_on_clear", False)
            console.print(f"\n[dim]Auto Clear on Clear: Löscht Memory Store bei 'clear' Befehl[/dim]")
            console.print(f"[dim]  • false: Memory bleibt erhalten (empfohlen für persistente Daten)[/dim]")
            console.print(f"[dim]  • true: Memory wird mit gelöscht[/dim]")
            new_auto_clear = Prompt.ask(
                f"[cyan]Auto Clear on Clear (true/false)[/cyan]",
                choices=["true", "false"],
                default=str(current_auto_clear).lower()
            )
            if new_auto_clear != str(current_auto_clear).lower():
                config["memory"]["auto_clear_on_clear"] = (new_auto_clear == "true")
                console.print(f"[green]✓ Auto Clear on Clear geändert: {new_auto_clear}[/green]")

            # Max Entries
            current_max_entries = config.get("memory", {}).get("max_entries", 1000)
            new_max_entries = Prompt.ask(
                f"[cyan]Max Entries (100-10000)[/cyan]",
                default=str(current_max_entries)
            )
            try:
                max_entries_value = int(new_max_entries)
                if 100 <= max_entries_value <= 10000 and max_entries_value != current_max_entries:
                    config["memory"]["max_entries"] = max_entries_value
                    console.print(f"[green]✓ Max Entries geändert: {max_entries_value}[/green]")
            except ValueError:
                console.print("[yellow]Ungültiger Wert, überspringe...[/yellow]")

            # Max File Size MB
            current_max_size = config.get("memory", {}).get("max_file_size_mb", 10)
            new_max_size = Prompt.ask(
                f"[cyan]Max File Size in MB (1-100)[/cyan]",
                default=str(current_max_size)
            )
            try:
                max_size_value = int(new_max_size)
                if 1 <= max_size_value <= 100 and max_size_value != current_max_size:
                    config["memory"]["max_file_size_mb"] = max_size_value
                    console.print(f"[green]✓ Max File Size geändert: {max_size_value} MB[/green]")
            except ValueError:
                console.print("[yellow]Ungültiger Wert, überspringe...[/yellow]")

        elif category == "hallucination":
            console.print("\n[bold cyan]═══ Hallucination Detection Einstellungen ═══[/bold cyan]")
            hallu_config = config.get("hallucination_detection", {})

            # Enabled
            current_enabled = hallu_config.get("enabled", False)
            new_enabled = Prompt.ask(
                f"[cyan]Detection Enabled (true/false)[/cyan]",
                choices=["true", "false"],
                default=str(current_enabled).lower()
            )
            hallu_config["enabled"] = (new_enabled == "true")

            # Detection Level
            current_level = hallu_config.get("detection_level", "medium")
            new_level = Prompt.ask(
                f"[cyan]Detection Level (low/medium/high)[/cyan]",
                choices=["low", "medium", "high"],
                default=current_level
            )
            hallu_config["detection_level"] = new_level

            # Warning Mode
            current_mode = hallu_config.get("warning_mode", "flag_response")
            new_mode = Prompt.ask(
                f"[cyan]Warning Mode (silent/log/flag_response/block)[/cyan]",
                choices=["silent", "log", "flag_response", "block"],
                default=current_mode
            )
            hallu_config["warning_mode"] = new_mode

            # Thresholds
            current_threshold = hallu_config.get("hallucination_threshold", 0.7)
            new_threshold = Prompt.ask(
                f"[cyan]Hallucination Threshold (0.0-1.0)[/cyan]",
                default=str(current_threshold)
            )
            try:
                hallu_config["hallucination_threshold"] = float(new_threshold)
            except ValueError:
                pass

            current_context = hallu_config.get("context_alignment_threshold", 0.4)
            new_context = Prompt.ask(
                f"[cyan]Context Alignment Threshold (0.0-1.0)[/cyan]",
                default=str(current_context)
            )
            try:
                hallu_config["context_alignment_threshold"] = float(new_context)
            except ValueError:
                pass

            # Fact Checking
            current_fact = hallu_config.get("fact_checking_enabled", True)
            new_fact = Prompt.ask(
                f"[cyan]Fact Checking Enabled (true/false)[/cyan]",
                choices=["true", "false"],
                default=str(current_fact).lower()
            )
            hallu_config["fact_checking_enabled"] = (new_fact == "true")

            # Max Processing Time
            current_time = hallu_config.get("max_processing_time", 10.0)
            new_time = Prompt.ask(
                f"[cyan]Max Processing Time (seconds)[/cyan]",
                default=str(current_time)
            )
            try:
                hallu_config["max_processing_time"] = float(new_time)
            except ValueError:
                pass

            config["hallucination_detection"] = hallu_config

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
        "Memory Store:\n"
        "  [yellow]merke email:test@example.com[/yellow]  - Email speichern\n"
        "  [yellow]recall[/yellow] oder [yellow]was hast du gemerkt[/yellow]  - Gespeicherte Daten abrufen\n"
        "  [yellow]forget email:test@example.com[/yellow] - Email löschen\n"
        "  [yellow]forget category:emails[/yellow]        - Alle Emails löschen\n"
        "  [yellow]forget all:true[/yellow]               - Alles löschen\n\n"
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
        raise CrawllamaException(f"Query processing failed: {e}", 1)


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
        raise CrawllamaException("Startup checks failed", 1)

    # Clear cache on startup if configured
    from core.cache import CacheManager
    cache = CacheManager(
        cache_dir=config.get("paths", {}).get("cache_dir", "data/cache"),
        ttl_hours=config.get("cache", {}).get("ttl_hours", 24),
        max_size_mb=config.get("cache", {}).get("max_size_mb", 500)
    )

    clear_on_startup = config.get("cache", {}).get("clear_on_startup", False)
    if clear_on_startup:
        console.print("[cyan]Clearing cache on startup (configured)...[/cyan]")
        cleared_count = cache.clear()
        console.print(f"[green]✓ Cache cleared: {cleared_count} files deleted[/green]")
    else:
        # Just clear expired entries
        console.print("[cyan]Clearing expired cache entries...[/cyan]")
        cleared_count = cache.clear_expired()
        if cleared_count > 0:
            console.print(f"[green]✓ Expired cache cleared: {cleared_count} files deleted[/green]")
        else:
            console.print("[dim]No expired cache entries found[/dim]")

    # Initialize agent
    try:
        agent = SearchAgent(
            config=config,
            enable_web=not args.no_web,
            debug=args.debug
        )
    except Exception as e:
        raise CrawllamaException(f"Failed to initialize agent: {e}", 1)

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
    try:
        main()
    except CrawllamaException as e:
        console.print(f"[red]Error: {e.message}[/red]")
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)
