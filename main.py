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

VERSION = "1.4.7"

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
from core.langgraph_agent import MultiHopReasoningAgent
from utils.logger import setup_logger
from rich.progress import Progress, BarColumn, TextColumn
import sys
import io

# Force UTF-8 encoding for stdout/stderr to handle Unicode characters
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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


def adjust_config_for_provider(config: dict) -> dict:
    """
    Automatically adjust token limits based on LLM provider.
    
    Local models (Ollama): High limits (16000+ tokens, large context)
    Cloud APIs (OpenAI, Anthropic, Groq): Lower limits (4096 tokens, smaller context)
    
    Note: Adjusts if max_tokens doesn't match the provider's expected default.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Modified config with adjusted limits
    """
    provider = config.get("llm", {}).get("provider", "ollama")
    current_max_tokens = config.get("llm", {}).get("max_tokens")
    
    # Default values for each provider
    DEFAULT_OLLAMA_TOKENS = 16000
    DEFAULT_CLOUD_TOKENS = 2048
    
    # Determine if we need to adjust based on provider
    if provider == "ollama":
        # For Ollama, if max_tokens is too low (cloud default), adjust it
        if current_max_tokens is None or current_max_tokens <= DEFAULT_CLOUD_TOKENS:
            config["llm"]["max_tokens"] = DEFAULT_OLLAMA_TOKENS
            config["security"]["max_context_length"] = 16000
            config["context_limits"] = {
                "small": 4000,
                "medium": 6000,
                "large": 8000,
                "xlarge": 12000,
                "max_storage": 8000
            }
    else:
        # For cloud providers, if max_tokens is too high (ollama default), adjust it
        if current_max_tokens is None or current_max_tokens >= DEFAULT_OLLAMA_TOKENS:
            config["llm"]["max_tokens"] = DEFAULT_CLOUD_TOKENS
            config["security"]["max_context_length"] = 6000
            config["context_limits"] = {
                "small": 1500,
                "medium": 2500,
                "large": 3500,
                "xlarge": 5000,
                "max_storage": 3000
            }
    
    return config


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

    # Check LLM connection based on provider
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "ollama")
    
    if provider == "ollama":
        # Check Ollama connection with a quick check (2 attempts, 5 second timeout)
        import requests
        import time
        base_url = llm_config.get("base_url", "http://127.0.0.1:11434")

        connected = False
        last_error = None

        # Try twice with a short delay between attempts
        for attempt in range(2):
            try:
                response = requests.get(f"{base_url}/api/tags", timeout=5)
                response.raise_for_status()
                console.print("[green][OK] Ollama connection successful[/green]")
                results["ollama"] = {"status": True, "error_msg": ""}
                connected = True
                break
            except Exception as e:
                last_error = e
                if attempt == 0:
                    # Wait a bit before second attempt
                    time.sleep(1)

        if not connected:
            msg = "Ollama is not running or not accessible"
            console.print(f"[yellow][!] {msg}[/yellow]")
            console.print(f"[dim]Attempted URL: {base_url}/api/tags[/dim]")
            if last_error:
                console.print(f"[dim]Error: {type(last_error).__name__}: {str(last_error)[:100]}[/dim]")
            results["ollama"] = {"status": False, "error_msg": msg}
    else:
        # For cloud providers, just check if API key is set
        import os
        key_name = f"{provider.upper()}_API_KEY"
        if os.getenv(key_name):
            console.print(f"[green][OK] {provider.title()} API key configured[/green]")
            results[provider] = {"status": True, "error_msg": ""}
        else:
            msg = f"{provider.title()} API key not found. Please set {key_name} in .env file"
            console.print(f"[yellow][!] {msg}[/yellow]")
            results[provider] = {"status": False, "error_msg": msg}

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
        console.print(f"[red][X] Directory initialization failed: {dir_errors}[/red]")
        results["directories"] = {"status": False, "error_msg": "; ".join(dir_errors)}
    else:
        console.print("[green][OK] Directories initialized[/green]")
        results["directories"] = {"status": True, "error_msg": ""}

    # Validate proxies if configured
    from utils.proxy_validator import ProxyValidator
    proxy_validator = ProxyValidator.load_from_env()
    if proxy_validator.is_configured():
        console.print("[cyan]Validating proxy configuration...[/cyan]")
        proxy_results = proxy_validator.validate_proxies()
        all_valid = all(proxy_results.values())
        if all_valid:
            console.print("[green][OK] Proxy configuration valid[/green]")
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
    table.add_column("Source", style="cyan", width=20)
    table.add_column("Tokens", style="yellow", justify="right", width=12)
    table.add_column("Share", style="dim", justify="right", width=12)

    table.add_row(
        "Conversation",
        f"{conversation_tokens:,}",
        f"{(conversation_tokens/max_tokens*100):.1f}%" if max_tokens > 0 else "0%"
    )
    table.add_row(
        "Search Results",
        f"{search_results_tokens:,}",
        f"{(search_results_tokens/max_tokens*100):.1f}%" if max_tokens > 0 else "0%"
    )
    table.add_row(
        "[bold]Total Used[/bold]",
        f"[bold]{total_used:,}[/bold]",
        f"[bold]{usage_percent:.1f}%[/bold]"
    )
    table.add_row(
        "[green]Available[/green]",
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

    console.print(f"\n[bold]Context Usage:[/bold]")
    console.print(f"[{color}]{'█' * int(usage_percent / 2)}[/{color}]{'░' * int((100 - usage_percent) / 2)} {usage_percent:.1f}%")

    # Session info
    console.print(f"\n[dim]Session Info:[/dim]")
    console.print(f"  • Conversation Entries: {len(agent.conversation_history)}/{agent.max_history}")
    console.print(f"  • Saved Search Results: {len(agent.last_search_results)}")
    if agent.last_search_query:
        console.print(f"  • Last Search: '{agent.last_search_query[:50]}...'")

    # Memory Store info
    try:
        from core.memory_store import get_memory_store
        memory = get_memory_store()
        summary = memory.get_summary()
        
        console.print(f"\n[bold cyan]💾 Memory Store:[/bold cyan]")
        console.print(f"  📧 Emails:      {summary['emails']:,}")
        console.print(f"  📱 Phones:      {summary['phones']:,}")
        console.print(f"  🌐 IPs:         {summary['ips']:,}")
        console.print(f"  👤 Usernames:   {summary['usernames']:,}")
        console.print(f"  🔗 Domains:     {summary['domains']:,}")
        console.print(f"  📝 Notes:       {summary['notes']:,}")
        console.print(f"  [bold]Total:       {summary['total_entries']:,}[/bold]")
    except Exception as e:
        console.print(f"\n[dim]Memory Store: Not available ({e})[/dim]")

    console.print()


def show_settings(config: dict):
    """
    Display current settings in a formatted way.

    Args:
        config: Configuration dictionary
    """
    from rich.table import Table

    table = Table(title="CrawlLama Settings", show_header=True, header_style="bold cyan")
    table.add_column("Category", style="cyan")
    table.add_column("Setting", style="yellow")
    table.add_column("Value", style="green")

    # LLM Settings
    llm_config = config.get("llm", {})
    provider = llm_config.get("provider", "ollama")
    table.add_row("LLM", "Provider", provider)
    table.add_row("", "Model", llm_config.get("model", "N/A"))
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

    # UI Display Settings
    ui_config = config.get("ui", {})
    table.add_row("UI Display", "Show Adaptive Report", str(ui_config.get("show_adaptive_report", "N/A")))

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
    console.print("[dim]Select the category you want to change[/dim]\n")

    # Category selection
    category_choice = Prompt.ask(
        "[cyan]Which category do you want to change?[/cyan]",
        choices=["llm", "search", "rag", "cache", "osint", "memory", "hallucination", "ui", "all"],
        default="all"
    )

    categories = [category_choice] if category_choice != "all" else ["llm", "search", "rag", "cache", "osint", "memory", "hallucination", "ui"]

    for category in categories:
        if category == "llm":
            console.print("\n[bold cyan]=== LLM Settings ===[/bold cyan]")

            # LLM Provider Selection
            current_provider = config.get("llm", {}).get("provider", "ollama")
            console.print(f"\n[dim]Available Providers:[/dim]")
            console.print(f"[dim]  • ollama - Local models (free)[/dim]")
            console.print(f"[dim]  • openai - GPT-3.5, GPT-4 (API key required)[/dim]")
            console.print(f"[dim]  • anthropic - Claude 3 (API key required)[/dim]")
            console.print(f"[dim]  • groq - Mixtral, LLaMA (free with Free Tier)[/dim]")
            
            new_provider = Prompt.ask(
                f"[cyan]LLM Provider[/cyan]",
                choices=["ollama", "openai", "anthropic", "groq"],
                default=current_provider
            )
            
            if new_provider != current_provider:
                config["llm"]["provider"] = new_provider
                console.print(f"[green][OK] Provider changed: {new_provider}[/green]")
                
                # Show API key requirements for cloud providers
                if new_provider in ["openai", "anthropic", "groq"]:
                    key_name = f"{new_provider.upper()}_API_KEY"
                    console.print(f"[yellow]⚠️ {new_provider.title()} requires an API key![/yellow]")
                    console.print(f"[dim]Set {key_name} in .env file[/dim]")

            # LLM Model (adjust suggestions based on provider)
            current_model = config.get("llm", {}).get("model", "qwen2.5:3b")
            
            # Provider-specific model suggestions
            provider = config.get("llm", {}).get("provider", "ollama")
            if provider == "openai":
                console.print(f"\n[dim]OpenAI Models: gpt-3.5-turbo, gpt-4, gpt-4-turbo, gpt-4o-mini (new, cheaper, faster)[/dim]")
            elif provider == "anthropic":
                console.print(f"\n[dim]Anthropic Models: claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307[/dim]")
            elif provider == "groq":
                console.print(f"\n[dim]Groq Models: mixtral-8x7b-32768, llama2-70b-4096, gemma-7b-it[/dim]")
            else:  # ollama
                console.print(f"\n[dim]Ollama Models: qwen2.5:3b, qwen3:8b, deepseek-r1:8b, llama3:7b[/dim]")
            
            new_model = Prompt.ask(
                f"[cyan]LLM Model[/cyan]",
                default=current_model
            )
            
            if new_model and new_model != current_model:
                if InputValidator.validate_model_name(new_model):
                    config["llm"]["model"] = new_model
                    console.print(f"[green][OK] Model changed: {new_model}[/green]")
                else:
                    console.print("[red]❌ Invalid model name! Allowed: Letters, numbers, '.', ':', '-', '_'[/red]")

            # Temperature
            current_temp = config.get("llm", {}).get("temperature", 0.7)
            new_temp = Prompt.ask(
                f"[cyan]Temperature (0.0-1.0)[/cyan]",
                default=str(current_temp)
            )
            
            temp_value = InputValidator.validate_float(new_temp, 0.0, 1.0)
            if temp_value is not None and temp_value != current_temp:
                config["llm"]["temperature"] = temp_value
                console.print(f"[green][OK] Temperature changed: {temp_value}[/green]")
            elif temp_value is None:
                console.print("[red]❌ Invalid value! Temperature must be between 0.0 and 1.0.[/red]")

            # Max Tokens (Context Size)
            current_tokens = config.get("llm", {}).get("max_tokens", 10000)
            new_tokens = Prompt.ask(
                f"[cyan]Max Tokens / Context Size (1000-32000)[/cyan]",
                default=str(current_tokens)
            )
            
            tokens_value = InputValidator.validate_int(new_tokens, 1000, 32000)
            if tokens_value is not None and tokens_value != current_tokens:
                config["llm"]["max_tokens"] = tokens_value
                console.print(f"[green][OK] Max Tokens changed: {tokens_value}[/green]")
                console.print("[dim]Recommendation: RTX 3080+ → 10k-16k, RTX 3060/70 → 6k-8k, CPU → 2k-4k[/dim]")
            elif tokens_value is None:
                console.print("[red]❌ Invalid value! Max Tokens must be between 1000 and 32000.[/red]")

        elif category == "search":
            console.print("\n[bold cyan]=== Search Settings ===[/bold cyan]")

            # Max Results
            current_max = config.get("search", {}).get("max_results", 10)
            new_max = Prompt.ask(
                f"[cyan]Max Search Results (1-100)[/cyan]",
                default=str(current_max)
            )
            
            max_value = InputValidator.validate_int(new_max, 1, 100)
            if max_value is not None and max_value != current_max:
                config["search"]["max_results"] = max_value
                console.print(f"[green][OK] Max Results changed: {max_value}[/green]")
            elif max_value is None:
                console.print("[red]❌ Invalid value! Max Results must be between 1 and 100.[/red]")

            # Region
            current_region = config.get("search", {}).get("region", "de-de")
            new_region = Prompt.ask(
                f"[cyan]Search Region[/cyan]",
                choices=["de-de", "us-en", "wt-wt", "gb-en", "fr-fr"],
                default=current_region
            )
            if new_region and new_region != current_region:
                config["search"]["region"] = new_region
                console.print(f"[green][OK] Region changed: {new_region}[/green]")

        elif category == "rag":
            console.print("\n[bold cyan]=== RAG Settings ===[/bold cyan]")

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
                f"[cyan]Enable RAG? (y/n)[/cyan]",
                default="y" if current_rag else "n",
                choices=["y", "n"]
            )
            new_rag = rag_choice.lower() == "y"
            if new_rag != current_rag:
                config["rag"]["enabled"] = new_rag
                console.print(f"[green][OK] RAG {'enabled' if new_rag else 'disabled'}[/green]")

            # Embedding Model
            current_model = config.get("rag", {}).get("embedding_model", "nomic-embed-text")
            new_model = Prompt.ask(
                f"[cyan]Embedding Model[/cyan]",
                default=current_model
            )
            if new_model != current_model:
                config["rag"]["embedding_model"] = new_model
                console.print(f"[green][OK] Embedding Model changed: {new_model}[/green]")

            # Top K
            current_topk = config.get("rag", {}).get("top_k", 5)
            new_topk = Prompt.ask(
                f"[cyan]Top K (Number of RAG documents, 1-20)[/cyan]",
                default=str(current_topk)
            )
            
            topk_value = InputValidator.validate_int(new_topk, 1, 20)
            if topk_value is not None and topk_value != current_topk:
                config["rag"]["top_k"] = topk_value
                console.print(f"[green][OK] Top K changed: {topk_value}[/green]")
            elif topk_value is None:
                console.print("[red]❌ Invalid value! Top K must be between 1 and 20.[/red]")

        elif category == "cache":
            console.print("\n[bold cyan]=== Cache Settings ===[/bold cyan]")

            # Cache Enabled
            current_cache = config.get("cache", {}).get("enabled", True)
            cache_choice = Prompt.ask(
                f"[cyan]Enable cache? (y/n)[/cyan]",
                default="y" if current_cache else "n",
                choices=["y", "n"]
            )
            new_cache = cache_choice.lower() == "y"
            if new_cache != current_cache:
                config["cache"]["enabled"] = new_cache
                console.print(f"[green][OK] Cache {'enabled' if new_cache else 'disabled'}[/green]")

        elif category == "osint":
            console.print("\n[bold cyan]=== OSINT Settings ===[/bold cyan]")

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
                    console.print(f"[green][OK] OSINT Max Results changed: {osint_max_value}[/green]")
            except ValueError:
                console.print("[yellow]Invalid value, skipping...[/yellow]")

            # Email Search Limit
            current_email_limit = config.get("osint", {}).get("email_search_limit", 50)
            new_email_limit = Prompt.ask(
                f"[cyan]Email Search Limit per hour[/cyan]",
                default=str(current_email_limit)
            )
            try:
                email_limit_value = int(new_email_limit)
                if email_limit_value != current_email_limit:
                    config["osint"]["email_search_limit"] = email_limit_value
                    console.print(f"[green][OK] Email Search Limit changed: {email_limit_value}[/green]")
            except ValueError:
                console.print("[yellow]Invalid value, skipping...[/yellow]")

            # Phone Search Limit
            current_phone_limit = config.get("osint", {}).get("phone_search_limit", 50)
            new_phone_limit = Prompt.ask(
                f"[cyan]Phone Search Limit per hour[/cyan]",
                default=str(current_phone_limit)
            )
            try:
                phone_limit_value = int(new_phone_limit)
                if phone_limit_value != current_phone_limit:
                    config["osint"]["phone_search_limit"] = phone_limit_value
                    console.print(f"[green][OK] Phone Search Limit changed: {phone_limit_value}[/green]")
            except ValueError:
                console.print("[yellow]Invalid value, skipping...[/yellow]")

            # General OSINT Limit
            current_general_limit = config.get("osint", {}).get("general_osint_limit", 100)
            new_general_limit = Prompt.ask(
                f"[cyan]General OSINT Limit per hour[/cyan]",
                default=str(current_general_limit)
            )
            try:
                general_limit_value = int(new_general_limit)
                if general_limit_value != current_general_limit:
                    config["osint"]["general_osint_limit"] = general_limit_value
                    console.print(f"[green][OK] General OSINT Limit changed: {general_limit_value}[/green]")
            except ValueError:
                console.print("[yellow]Invalid value, skipping...[/yellow]")

            # Safesearch Mode
            current_safesearch = config.get("osint", {}).get("safesearch", "strict")
            console.print(f"\n[dim]Safesearch improves search result quality for OSINT investigations[/dim]")
            console.print(f"[dim]  • off: No filtering[/dim]")
            console.print(f"[dim]  • moderate: Moderate filtering (default DuckDuckGo)[/dim]")
            console.print(f"[dim]  • strict: Strict filtering (recommended for best quality)[/dim]")
            new_safesearch = Prompt.ask(
                f"[cyan]Safesearch Mode[/cyan]",
                choices=["off", "moderate", "strict"],
                default=current_safesearch
            )
            if new_safesearch and new_safesearch != current_safesearch:
                config["osint"]["safesearch"] = new_safesearch
                console.print(f"[green][OK] Safesearch Mode changed: {new_safesearch}[/green]")

        elif category == "memory":
            console.print("\n[bold cyan]=== Memory Store Settings ===[/bold cyan]")

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
                console.print(f"[green][OK] Memory Store Enabled changed: {new_memory_enabled}[/green]")

            # Auto Clear on Clear Command
            current_auto_clear = config.get("memory", {}).get("auto_clear_on_clear", False)
            console.print(f"\n[dim]Auto Clear on Clear: Clears Memory Store on 'clear' command[/dim]")
            console.print(f"[dim]  • false: Memory persists (recommended for persistent data)[/dim]")
            console.print(f"[dim]  • true: Memory is cleared[/dim]")
            new_auto_clear = Prompt.ask(
                f"[cyan]Auto Clear on Clear (true/false)[/cyan]",
                choices=["true", "false"],
                default=str(current_auto_clear).lower()
            )
            if new_auto_clear != str(current_auto_clear).lower():
                config["memory"]["auto_clear_on_clear"] = (new_auto_clear == "true")
                console.print(f"[green][OK] Auto Clear on Clear changed: {new_auto_clear}[/green]")

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
                    console.print(f"[green][OK] Max Entries changed: {max_entries_value}[/green]")
            except ValueError:
                console.print("[yellow]Invalid value, skipping...[/yellow]")

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
                    console.print(f"[green][OK] Max File Size changed: {max_size_value} MB[/green]")
            except ValueError:
                console.print("[yellow]Invalid value, skipping...[/yellow]")

        elif category == "hallucination":
            console.print("\n[bold cyan]=== Hallucination Detection Settings ===[/bold cyan]")
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
                pass  # Keep existing value if user provides invalid input

            current_context = hallu_config.get("context_alignment_threshold", 0.4)
            new_context = Prompt.ask(
                f"[cyan]Context Alignment Threshold (0.0-1.0)[/cyan]",
                default=str(current_context)
            )
            try:
                hallu_config["context_alignment_threshold"] = float(new_context)
            except ValueError:
                pass  # Keep existing value if user provides invalid input

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
                pass  # Keep existing value if user provides invalid input

            config["hallucination_detection"] = hallu_config

        elif category == "ui":
            console.print("\n[bold cyan]=== UI Display Settings ===[/bold cyan]")

            # Ensure UI config exists
            if "ui" not in config:
                config["ui"] = {
                    "show_adaptive_report": True
                }

            # Show Adaptive Report
            current_show_report = config.get("ui", {}).get("show_adaptive_report", True)
            console.print(f"\n[dim]Adaptive Intelligence Report: Shows details after each query[/dim]")
            console.print(f"[dim]  • Complexity level (LOW/MID/HIGH)[/dim]")
            console.print(f"[dim]  • Selected Agent (SearchAgent/MultiHopReasoningAgent)[/dim]")
            console.print(f"[dim]  • Reasoning for agent selection[/dim]")
            console.print(f"[dim]  • Confidence score[/dim]")
            console.print(f"[dim]  • Processing time and attempts[/dim]")
            new_show_report = Prompt.ask(
                f"[cyan]Show Adaptive Intelligence Report (y/n)[/cyan]",
                choices=["y", "n"],
                default="y" if current_show_report else "n"
            )
            if new_show_report != ("y" if current_show_report else "n"):
                config["ui"]["show_adaptive_report"] = (new_show_report == "y")
                console.print(f"[green][OK] Adaptive Report {'enabled' if new_show_report == 'y' else 'disabled'}[/green]")

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
        console.print(f"[green][OK] Configuration saved: {config_path}[/green]")
        return True
    except Exception as e:
        console.print(f"[red][X] Error saving: {e}[/red]")
        return False


def interactive_mode(agent: SearchAgent, adaptive_processor=None, multihop_agent=None):
    """
    Run agent in interactive mode with Adaptive Agent Selection.

    Args:
        agent: Initialized SearchAgent instance
        adaptive_processor: AdaptiveQueryProcessor for intelligent agent selection (REQUIRED)
        multihop_agent: MultiHopReasoningAgent for complex queries
    """
    import logging
    logger = logging.getLogger("crawllama")
    
    # Adaptive mode is always enabled
    if not adaptive_processor:
        console.print("[red][X] ERROR: Adaptive System is not available![/red]")
        console.print("[yellow]The Adaptive System is required. Please check initialization.[/yellow]")
        return
    # Check OSINT terms acceptance on startup
    from core.osint import OSINTCompliance
    compliance = OSINTCompliance(config=agent.config)

    if not compliance.check_terms_accepted("default"):
        console.print("\n[bold yellow]=== OSINT Features Available ===[/bold yellow]")
        console.print("[dim]CrawlLama v1.2 includes OSINT features for Email/Phone Intelligence.[/dim]")
        console.print("[dim]Operators: email:, phone:, site:, inurl:, etc.[/dim]\n")

        console.print(compliance.display_terms())

        accept_choice = Prompt.ask(
            "\n[cyan]Would you like to accept the OSINT Terms of Use?[/cyan]",
            choices=["accept", "decline"],
            default="accept"
        )

        if accept_choice.lower() == "accept":
            compliance.accept_terms("default")
            console.print("[green][OK] OSINT Terms accepted. You can now use OSINT features![/green]")
            console.print("[dim]Examples: email:test@example.com, phone:\"+49 151 12345678\", site:github.com[/dim]\n")
        else:
            console.print("[yellow]⚠ OSINT Features will not be activated.[/yellow]")
            console.print("[dim]You can continue to use normal search.[/dim]\n")

    # Show current version at startup
    console.print(Panel.fit(
        f"[bold cyan]CrawlLama v{VERSION} - AI Search Agent with Adaptive Intelligence[/bold cyan]\n"
        "Intelligent agent selection based on query complexity.\n\n"
        f"[dim]Version: {VERSION} | [green]Adaptive Mode: ALWAYS ON[/green][/dim]\n\n"
        "[bold yellow][AI] How it works:[/bold yellow]\n"
        "  • [green]LOW[/green] complexity  → SearchAgent (fast, direct)\n"
        "  • [yellow]MID[/yellow] complexity  → MultiHop (1 hop, reasoning)\n"
        "  • [red]HIGH[/red] complexity → MultiHop (up to 5 hops, deep analysis)\n"
        "  • Automatic escalation on low confidence\n"
        "  • Resource-aware degradation\n\n"
        "Commands:\n"
        "  [yellow]help[/yellow]        - Show complete help\n"
        "  [yellow]clear[/yellow]       - Reset session (history + cache)\n"
        "  [yellow]stats[/yellow]       - Show statistics\n"
        "  [yellow]settings[/yellow]    - View/change settings\n"
        "  [yellow]export[/yellow]      - Export memory\n"
        "  [yellow]exit, quit[/yellow]  - Exit\n\n"
        "[dim]Tip: Every query is automatically analyzed for optimal agent selection![/dim]",
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
                console.print("[yellow]Goodbye![/yellow]")
                break

            elif query.lower() in ["help", "hilfe", "?"]:
                # Show help menu with all commands
                console.print(Panel.fit(
                    "[bold cyan]CrawlLama - Help & Commands[/bold cyan]\n\n"
                    "[bold yellow]🔧 System Commands:[/bold yellow]\n"
                    "  [cyan]help, hilfe, ?[/cyan]     - Show this help\n"
                    "  [cyan]clear[/cyan]              - Reset session (history + cache)\n"
                    "  [cyan]clear-cache[/cyan]        - Clear cache only\n"
                    "  [cyan]clear-memory[/cyan]       - Clear memory store only\n"
                    "  [cyan]clear-all[/cyan]          - Clear everything (session + cache + memory)\n"
                    "  [cyan]save[/cyan]               - Save session manually\n"
                    "  [cyan]load[/cyan]               - Reload session\n"
                    "  [cyan]export, speichere ab[/cyan] - Export memory as file\n"
                    "  [cyan]stats[/cyan]              - Show agent statistics\n"
                    "  [cyan]status[/cyan]             - Show context usage\n"
                    "  [cyan]settings[/cyan]           - View/change settings\n"
                    "  [cyan]restart[/cyan]            - Restart agent (reload config)\n"
                    "  [cyan]exit, quit[/cyan]         - Exit program\n\n"
                    "[bold yellow][AI] Adaptive Intelligence (Always Active):[/bold yellow]\n"
                    "  [dim]Automatically selects best agent based on query complexity:[/dim]\n"
                    "  [dim]• [green]LOW[/green] complexity  → SearchAgent (fast, direct answers)[/dim]\n"
                    "  [dim]• [yellow]MID[/yellow] complexity  → MultiHopAgent (1 hop, moderate reasoning)[/dim]\n"
                    "  [dim]• [red]HIGH[/red] complexity → MultiHopAgent (up to 5 hops, deep analysis)[/dim]\n"
                    "  [dim]Features: Confidence-based escalation, resource monitoring, automatic fallback[/dim]\n\n"
                    "[bold yellow]💾 Memory Store:[/bold yellow]\n"
                    "  [cyan]remember email:...[/cyan] - Store email\n"
                    "  [cyan]remember phone:...[/cyan] - Store phone number\n"
                    "  [cyan]remember ip:...[/cyan]    - Store IP address\n"
                    "  [cyan]remember note:...[/cyan]  - Store note\n"
                    "  [cyan]recall[/cyan]             - Show all stored data\n"
                    "  [cyan]recall emails[/cyan]      - Show emails only\n"
                    "  [cyan]forget email:...[/cyan]   - Delete specific email\n"
                    "  [cyan]forget category:emails[/cyan] - Delete all emails\n"
                    "  [cyan]clear-memory[/cyan]       - Clear entire memory store\n"
                    "  [cyan]export[/cyan]             - Export memory to file (JSON + TXT)\n\n"
                    "[bold yellow][Search] OSINT Operators:[/bold yellow]\n"
                    "  [cyan]email:test@example.com[/cyan]  - Email Intelligence\n"
                    "  [cyan]phone:+491234567890[/cyan]     - Phone Intelligence\n"
                    "  [cyan]ip:8.8.8.8[/cyan]              - IP Intelligence\n"
                    "  [cyan]domain:example.com[/cyan]      - Domain Intelligence\n"
                    "  [cyan]username:johndoe[/cyan]        - Social Media Check\n"
                    "  [cyan]site:github.com python[/cyan]  - Search on domain\n"
                    "  [cyan]inurl:admin[/cyan]             - URL contains term\n"
                    "  [cyan]filetype:pdf[/cyan]            - Filter by file type\n\n"
                    "[bold yellow]✨ Special Syntax:[/bold yellow]\n"
                    "  [cyan]< question[/cyan]  - Use context only (no web search)\n"
                    "  [dim]Example: \"< who is he?\" uses conversation history only[/dim]\n\n"
                    "[bold yellow]📚 Examples:[/bold yellow]\n"
                    "  [dim]• What is Python?[/dim]\n"
                    "  [dim]• email:test@gmail.com[/dim]\n"
                    "  [dim]• site:github.com AI projects[/dim]\n"
                    "  [dim]• remember email:admin@example.com[/dim]\n"
                    "  [dim]• export (saves memory to data/exports/)[/dim]\n"
                    "  [dim]• < summarize source 1[/dim]\n",
                    border_style="cyan"
                ))
                continue

            elif query.lower() == "clear":
                # Clear session data
                stats = agent.clear_session()
                console.clear()
                console.print(f"[green][OK] Session reset:[/green]")
                console.print(f"  • {stats['conversation_entries']} conversation entries deleted")
                console.print(f"  • {stats['search_results']} search results deleted")
                console.print(f"  • {stats['cache_files']} cache files deleted")
                
                # Show memory cleared if auto_clear_on_clear is enabled
                if stats.get('memory_entries', 0) > 0:
                    console.print(f"  • {stats['memory_entries']} memory entries deleted")
                
                continue

            elif query.lower() == "stats":
                stats = agent.get_stats()
                console.print("\n[bold]Agent Statistics:[/bold]")
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
                console.print(f"[green]Cache cleared: {count} files deleted[/green]")
                continue

            elif query.lower() in ["clear-memory", "memory-clear"]:
                # Clear only memory store (without session/cache)
                deleted_count = agent.clear_memory()
                if deleted_count > 0:
                    console.print(f"[green][OK] Memory Store cleared: {deleted_count} entries removed[/green]")
                else:
                    console.print(f"[yellow]⚠ Memory Store is already empty[/yellow]")
                continue

            elif query.lower() == "clear-all":
                # Clear everything: session, cache, and memory
                console.clear()
                console.print("[cyan]Clearing all data...[/cyan]\n")

                # Clear session (conversation history + search results)
                stats = agent.clear_session()
                console.print(f"[green][OK] Session cleared:[/green]")
                console.print(f"  • {stats['conversation_entries']} conversation entries deleted")
                console.print(f"  • {stats['search_results']} search results deleted")

                # Clear cache
                from core.cache import CacheManager
                cache = CacheManager()
                cache_count = cache.clear()
                console.print(f"[green][OK] Cache cleared: {cache_count} files deleted[/green]")

                # Clear memory store (force clear regardless of auto_clear_on_clear setting)
                memory_count = agent.clear_memory()
                console.print(f"[green][OK] Memory Store cleared: {memory_count} entries deleted[/green]")

                console.print(f"\n[bold green]✓ All data cleared successfully![/bold green]\n")
                continue

            elif query.lower() == "save":
                # Manually save session
                success = agent.save_session()
                if success:
                    console.print(f"[green][OK] Session saved:[/green]")
                    console.print(f"  • {len(agent.conversation_history)} conversation entries")
                    console.print(f"  • {len(agent.last_search_results)} search results")
                    console.print(f"  • File: data/session.json")
                else:
                    console.print(f"[red][X] Error saving session[/red]")
                continue

            elif query.lower() == "load":
                # Reload session
                success = agent.load_session()
                if success:
                    console.print(f"[green][OK] Session loaded:[/green]")
                    console.print(f"  • {len(agent.conversation_history)} conversation entries")
                    console.print(f"  • {len(agent.last_search_results)} search results")
                else:
                    console.print(f"[yellow]⚠ No saved session found[/yellow]")
                continue
            
            elif query.lower() in ["export", "export-memory", "speichere ab"]:
                # Export memory snapshot
                from core.memory_store import get_memory_store
                memory = get_memory_store()
                
                result = memory.export_memory_snapshot()
                
                if result.get('success'):
                    console.print(f"[green][OK] Memory exported:[/green]")
                    console.print(f"  • JSON: {result['json_file']}")
                    console.print(f"  • Text: {result['txt_file']}")
                    console.print(f"  • Timestamp: {result['timestamp']}")
                    console.print(f"  • Total entries: {result['total_entries']}")
                    console.print(f"\n[dim]Categories:[/dim]")
                    for category, count in result['categories'].items():
                        if count > 0:
                            console.print(f"    • {category}: {count}")
                else:
                    console.print(f"[red][X] Error exporting: {result.get('error', 'Unknown')}[/red]")
                continue

            elif query.lower() == "settings":
                # Settings menu
                show_settings(agent.config)

                edit_choice = Prompt.ask(
                    "\n[cyan]Do you want to change the settings?[/cyan]",
                    choices=["y", "n"],
                    default="n"
                )

                if edit_choice.lower() == "y":
                    agent.config = edit_settings(agent.config)

                    save_choice = Prompt.ask(
                        "\n[cyan]Save settings?[/cyan]",
                        choices=["y", "n"],
                        default="y"
                    )

                    if save_choice.lower() == "y":
                        save_config(agent.config)

                        restart_choice = Prompt.ask(
                            "\n[cyan]Restart agent to apply changes?[/cyan]",
                            choices=["y", "n"],
                            default="y"
                        )

                        if restart_choice.lower() == "y":
                            console.print("[yellow]Agent is restarting...[/yellow]")
                            return "RESTART"  # Signal to restart agent
                        else:
                            console.print("[yellow]⚠ Some changes will only take effect after a restart.[/yellow]")

                continue

            elif query.lower() == "restart":
                # Restart agent
                console.print("[yellow]Agent is restarting...[/yellow]")

                # Ask if session should be saved
                save_choice = Prompt.ask(
                    "[cyan]Save session before restart?[/cyan]",
                    choices=["y", "n"],
                    default="y"
                )

                if save_choice.lower() == "y":
                    agent.save_session()
                    console.print("[green][OK] Session saved[/green]")

                return "RESTART"  # Signal to restart agent

            # Process query with Adaptive System
            console.print("\n[dim][Search] Analyzing query complexity...[/dim]\n")

            try:
                # Check for OSINT queries FIRST - they should always use SearchAgent
                osint_operators = ["email:", "phone:", "domain:", "ip:", "username:"]
                is_osint_query = any(op in query.lower() for op in osint_operators)
                
                # Check for result references (quelle/source N) - they should also use SearchAgent directly
                # Pattern: quelle N, source N, quelle N M, etc.
                is_result_reference = bool(re.search(r'\b(quelle|source|ergebnis|result)s?\s+\d+', query.lower()))
                
                if is_osint_query:
                    # Force OSINT queries to use SearchAgent directly (bypass adaptive routing)
                    logger.info("OSINT query detected - using SearchAgent directly")
                    answer = agent.query(query, use_tools=True)
                    result = {
                        "answer": answer,
                        "confidence": 1.0,
                        "strategy": {
                            "complexity": "osint",
                            "agent_type": "SearchAgent",
                            "use_multihop": False,
                            "use_tools": True,
                            "max_hops": 0,
                            "reasoning": ["OSINT query - bypassed adaptive routing"]
                        },
                        "metadata": {
                            "complexity_analysis": {},
                            "resource_status": {},
                            "attempts": 1,
                            "escalation_history": [],
                            "elapsed_time": 0.0
                        }
                    }
                elif is_result_reference:
                    # Force result references to use SearchAgent directly (bypass adaptive routing)
                    logger.info("Result reference detected - using SearchAgent directly")
                    answer = agent.query(query, use_tools=True)
                    result = {
                        "answer": answer,
                        "confidence": 1.0,
                        "strategy": {
                            "complexity": "result_reference",
                            "agent_type": "SearchAgent",
                            "use_multihop": False,
                            "use_tools": True,
                            "max_hops": 0,
                            "reasoning": ["Result reference - bypassed adaptive routing"]
                        },
                        "metadata": {
                            "complexity_analysis": {},
                            "resource_status": {},
                            "attempts": 1,
                            "escalation_history": [],
                            "elapsed_time": 0.0
                        }
                    }
                else:
                    # Use adaptive query processor (ALWAYS for normal queries)
                    result = adaptive_processor.process_query(
                        query=query,
                        force_complexity=None,
                        enable_escalation=True
                    )

                # Display response with metadata
                console.print(Markdown(result["answer"]))

                # Show adaptive metadata (if enabled in config)
                if agent.config.get("ui", {}).get("show_adaptive_report", True):
                    console.print("\n[dim]━━━ Adaptive Intelligence Report ━━━[/dim]")
                    strategy = result["strategy"]
                    metadata = result["metadata"]

                    # Show complexity and agent selection
                    complexity_color = {
                        "low": "green",
                        "mid": "yellow",
                        "high": "red"
                    }.get(strategy["complexity"], "white")

                    console.print(f"[dim]Complexity:[/dim] [{complexity_color}]{strategy['complexity'].upper()}[/{complexity_color}]")
                    console.print(f"[dim]Selected Agent:[/dim] [cyan]{strategy['agent_type']}[/cyan]")
                    console.print(f"[dim]Reasoning:[/dim] {strategy['reasoning']}")

                    # Show confidence if available
                    if result.get("confidence"):
                        confidence = result["confidence"]
                        conf_color = "green" if confidence > 0.7 else "yellow" if confidence > 0.5 else "red"
                        console.print(f"[dim]Confidence:[/dim] [{conf_color}]{confidence:.2%}[/{conf_color}]")

                    # Show escalation history if any
                    if metadata.get("escalation_history"):
                        console.print(f"\n[dim]Escalation History:[/dim]")
                        for esc in metadata["escalation_history"]:
                            console.print(f"  [dim]Attempt {esc['attempt']}:[/dim] {esc['from_agent']} → {esc['to_agent']}")
                            console.print(f"  [dim]Reason:[/dim] {esc['reason']}")

                    # Show timing and attempts
                    console.print(f"[dim]Attempts:[/dim] {metadata['attempts']}")
                    console.print(f"[dim]Processing Time:[/dim] {metadata['elapsed_time']:.2f}s")
                    console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]\n")

            except Exception as e:
                # Check if it's a connection error to Ollama
                error_msg = str(e).lower()
                if "connection" in error_msg or "max retries exceeded" in error_msg or "11434" in error_msg:
                    console.print(f"\n[red][X] LLM Provider is not available[/red]")
                    console.print("[yellow]⚠️ Ollama is not running. Please either:[/yellow]")
                    console.print("  [cyan]1.[/cyan] Start Ollama: Run 'ollama serve' in another terminal")
                    console.print("  [cyan]2.[/cyan] Configure cloud provider: Type 'settings'\n")
                else:
                    console.print(f"[red][X] Query processing failed: {e}[/red]")
                    console.print("[dim]Please check system logs for details.[/dim]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Use 'exit' to quit.[/yellow]")
            continue
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


def direct_query_mode(agent: SearchAgent, query: str, adaptive_processor=None):
    """
    Process single query and exit.

    Args:
        agent: Initialized SearchAgent instance
        query: Query string
        adaptive_processor: AdaptiveQueryProcessor for intelligent agent selection (optional, fallback to standard agent)
    """
    import logging
    logger = logging.getLogger("crawllama")
    
    try:
        console.print(f"[cyan]Query:[/cyan] {query}\n")
        
        # Check for OSINT queries FIRST - they should always use SearchAgent
        osint_operators = ["email:", "phone:", "domain:", "ip:", "username:"]
        is_osint_query = any(op in query.lower() for op in osint_operators)
        
        # Check for result references (quelle/source N)
        is_result_reference = bool(re.search(r'\b(quelle|source|ergebnis|result)s?\s+\d+', query.lower()))
        
        if is_osint_query:
            # Force OSINT queries to use SearchAgent directly (bypass adaptive routing)
            logger.info("OSINT query detected - using SearchAgent directly")
            response = agent.query(query, use_tools=True)
            console.print(Markdown(response))
        elif is_result_reference:
            # Force result references to use SearchAgent directly (bypass adaptive routing)
            logger.info("Result reference detected - using SearchAgent directly")
            response = agent.query(query, use_tools=True)
            console.print(Markdown(response))
        elif adaptive_processor:
            # Use Adaptive System
            console.print("[dim][Search] Analyzing query complexity...[/dim]\n")
            result = adaptive_processor.process_query(
                query=query,
                force_complexity=None,
                enable_escalation=True
            )
            console.print(Markdown(result["answer"]))

            # Show brief metadata (if enabled in config)
            if agent.config.get("ui", {}).get("show_adaptive_report", True):
                console.print(f"\n[dim]Complexity: {result['strategy']['complexity'].upper()} | "
                             f"Agent: {result['strategy']['agent_type']} | "
                             f"Time: {result['metadata']['elapsed_time']:.2f}s[/dim]")
        else:
            # Fallback to standard agent
            response = agent.query(query)
            console.print(Markdown(response))

    except Exception as e:
        raise CrawllamaException(f"Query processing failed: {e}", 1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="CrawlLama - Local Search and Answer Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Interactive mode
  %(prog)s "What is Python?"                  # Direct question
  %(prog)s --no-web "Explain photosynthesis"  # Offline mode
  %(prog)s --model qwen2.5:3b "Question"      # Different model
        """
    )

    parser.add_argument(
        "query",
        nargs="*",
        help="Direct question (optional, starts interactive mode if empty)"
    )

    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to configuration file (default: config.json)"
    )

    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Offline mode (no web search)"
    )

    parser.add_argument(
        "--model",
        help="Override LLM model (e.g. qwen2.5:3b, gpt-4o-mini)"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show agent statistics and exit"
    )

    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear cache and exit"
    )

    parser.add_argument(
        "--setup-keys",
        action="store_true",
        help="Interactive setup for API keys"
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

    # Check for config.json existence before loading
    config_path = args.config
    if not Path(config_path).is_file():
        console.print(Panel("[bold red]Configuration file 'config.json' not found![/bold red]\n\nPlease run the setup first:\n- On Windows: [bold]run.bat[/bold]\n- On Linux/Mac: [bold]run.sh[/bold]", title="Setup Required", style="red"))
        console.print("[bold]Press Enter to exit...[/bold]")
        try:
            sys.stdin.readline()
        except (EOFError, OSError) as e:
            # stdin not available in non-interactive environment — log and exit
            console.print("[bold yellow]No interactive input available; exiting.[/bold yellow]")
            console.print(f"[dim]stdin readline failed: {e}[/dim]")
        sys.exit(1)
    config = load_config(config_path)
    
    # Automatically adjust token limits based on provider (local vs cloud)
    original_max_tokens = config.get("llm", {}).get("max_tokens")
    config = adjust_config_for_provider(config)
    
    # Save config if max_tokens was adjusted
    if config.get("llm", {}).get("max_tokens") != original_max_tokens:
        save_config(config, config_path)

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
    startup_results = startup_check(config)

    # Check for critical failures (directories)
    if startup_results.get("directories", {}).get("status") == False:
        raise CrawllamaException("Critical: Directory initialization failed", 1)

    # Show warning if Ollama is not available and ask user what to do
    ollama_unavailable = startup_results.get("ollama", {}).get("status") == False
    if ollama_unavailable:
        # Suppress retry warnings from tenacity to avoid spam
        import logging
        logging.getLogger("tenacity").setLevel(logging.ERROR)
        logging.getLogger("crawllama").setLevel(logging.ERROR)
        console.print("\n" + "="*70)
        console.print(Panel.fit(
            "[bold yellow]⚠️  LLM Provider Not Available[/bold yellow]\n\n"
            f"[yellow]Ollama is not running or not accessible.[/yellow]\n\n"
            "[bold cyan]Options:[/bold cyan]\n"
            "  1. [cyan]Start Ollama:[/cyan] Run 'ollama serve' in another terminal and restart this app\n"
            "  2. [cyan]Switch to Cloud Provider:[/cyan] Configure a cloud provider now:\n"
            "     • OpenAI (GPT-3.5, GPT-4)\n"
            "     • Anthropic (Claude 3)\n"
            "     • Groq (Mixtral, LLaMA - free tier available)",
            title="Warning",
            border_style="yellow"
        ))
        console.print("="*70 + "\n")

        # Ask user if they want to configure cloud provider now
        choice = Prompt.ask(
            "[cyan]Do you want to configure a cloud provider now?[/cyan]",
            choices=["yes", "no", "exit"],
            default="yes"
        )

        if choice == "yes":
            # Direct LLM provider configuration
            console.print("\n[bold cyan]Configure LLM Provider:[/bold cyan]\n")

            # LLM Provider Selection
            current_provider = config.get("llm", {}).get("provider", "ollama")
            console.print(f"[dim]Available Providers:[/dim]")
            console.print(f"  [dim]• ollama - Local models (free, requires Ollama running)[/dim]")
            console.print(f"  [dim]• openai - GPT-3.5, GPT-4 (API key required)[/dim]")
            console.print(f"  [dim]• anthropic - Claude 3 (API key required)[/dim]")
            console.print(f"  [dim]• groq - Mixtral, LLaMA (free tier available)[/dim]\n")

            new_provider = Prompt.ask(
                f"[cyan]Select LLM Provider[/cyan]",
                choices=["ollama", "openai", "anthropic", "groq"],
                default="openai"
            )

            config["llm"]["provider"] = new_provider
            console.print(f"[green][OK] Provider changed to: {new_provider}[/green]\n")

            # Model selection based on provider
            if new_provider == "openai":
                console.print(f"[dim]OpenAI Models: gpt-3.5-turbo, gpt-4, gpt-4-turbo, gpt-4o-mini (new, cheaper, faster)[/dim]")
                default_model = "gpt-4o-mini"
            elif new_provider == "anthropic":
                console.print(f"[dim]Anthropic Models: claude-3-opus-20240229, claude-3-sonnet-20240229, claude-3-haiku-20240307[/dim]")
                default_model = "claude-3-haiku-20240307"
            elif new_provider == "groq":
                console.print(f"[dim]Groq Models: mixtral-8x7b-32768, llama2-70b-4096, gemma-7b-it[/dim]")
                default_model = "mixtral-8x7b-32768"
            else:  # ollama
                console.print(f"[dim]Ollama Models: qwen2.5:3b, qwen3:8b, deepseek-r1:8b, llama3:7b[/dim]")
                default_model = "qwen3:8b"

            new_model = Prompt.ask(
                f"[cyan]Select Model[/cyan]",
                default=default_model
            )

            config["llm"]["model"] = new_model
            console.print(f"[green][OK] Model changed to: {new_model}[/green]\n")

            # Show API key instructions for cloud providers
            if new_provider in ["openai", "anthropic", "groq"]:
                key_name = f"{new_provider.upper()}_API_KEY"
                console.print(f"[yellow]⚠️ Important: Set your API key in .env file:[/yellow]")
                console.print(f"[cyan]{key_name}=your_api_key_here[/cyan]\n")

            # Auto-adjust token limits
            config = adjust_config_for_provider(config)

            # Save configuration
            save_choice = Prompt.ask(
                "[cyan]Save settings and restart?[/cyan]",
                choices=["y", "n"],
                default="y"
            )

            if save_choice.lower() == "y":
                save_config(config)
                console.print("[green][OK] Settings saved! Please restart the application.[/green]")
                sys.exit(0)
            else:
                console.print("[yellow]Settings not saved. Application will exit.[/yellow]")
                sys.exit(0)
        elif choice == "exit":
            console.print("[yellow]Exiting...[/yellow]")
            sys.exit(0)
        else:
            console.print("\n[yellow]⚠️ Continuing without working LLM. Queries will fail until you configure a provider.[/yellow]")
            console.print("[dim]Type 'settings' to configure a provider later.[/dim]\n")

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
        console.print(f"[green][OK] Cache cleared: {cleared_count} files deleted[/green]")
    else:
        # Just clear expired entries
        console.print("[cyan]Clearing expired cache entries...[/cyan]")
        cleared_count = cache.clear_expired()
        if cleared_count > 0:
            console.print(f"[green][OK] Expired cache cleared: {cleared_count} files deleted[/green]")
        else:
            console.print("[dim]No expired cache entries found[/dim]")

    # Initialize standard agent
    try:
        agent = SearchAgent(
            config=config,
            enable_web=not args.no_web,
            debug=args.debug
        )
        console.print("[green][OK] SearchAgent initialized[/green]")
    except Exception as e:
        raise CrawllamaException(f"Failed to initialize agent: {e}", 1)

    # Initialize multi-hop agent (optional, for adaptive mode)
    multihop_agent = None
    try:
        multihop_agent = MultiHopReasoningAgent(
            config=config,
            max_hops=3,
            confidence_threshold=0.7
        )
        console.print("[green][OK] MultiHopAgent initialized[/green]")
    except Exception as e:
        console.print(f"[yellow]⚠ MultiHopAgent not available: {e}[/yellow]")
        console.print("[dim]Adaptive mode will be limited[/dim]")

    # Initialize Adaptive System (REQUIRED for v1.4.4+)
    adaptive_processor = None
    if not multihop_agent:
        raise CrawllamaException(
            "MultiHopAgent initialization failed. Adaptive System requires both SearchAgent and MultiHopAgent.",
            1
        )

    try:
        from core.adaptive_integration import initialize_adaptive_system
        from core.cloud_llm_client import get_llm_client
        from core.health import get_system_monitor, get_performance_tracker

        # Get LLM client for complexity detection (supports both local and cloud)
        llm_config = config.get("llm", {})
        provider = llm_config.get("provider", "ollama")
        
        if provider == "ollama":
            from core.llm_client import OllamaClient
            llm = OllamaClient(
                base_url=llm_config.get("base_url", "http://127.0.0.1:11434"),
                model=llm_config.get("model", "qwen2.5:3b"),
                timeout=llm_config.get("timeout", 120)
            )
        else:
            # Use cloud LLM client
            llm = get_llm_client(
                provider=provider,
                model=llm_config.get("model", "gpt-3.5-turbo"),
                temperature=llm_config.get("temperature", 0.7),
                max_tokens=llm_config.get("max_tokens", 4096)
            )

        # Initialize monitoring (optional)
        system_monitor = None
        performance_tracker = None
        try:
            system_monitor = get_system_monitor()
            performance_tracker = get_performance_tracker()
            console.print("[green][OK] System monitoring initialized[/green]")
        except Exception:
            console.print("[yellow]⚠ System monitoring unavailable (optional)[/yellow]")
            pass  # Continue without monitoring

        # Initialize adaptive system
        adaptive_manager, adaptive_processor = initialize_adaptive_system(
            llm=llm,
            agent=agent,
            multihop_agent=multihop_agent,
            system_monitor=system_monitor,
            performance_tracker=performance_tracker
        )
        console.print("[green][OK] Adaptive Hopping System initialized[/green]")
        console.print("[bold green][AI] Adaptive Intelligence: ACTIVE[/bold green]")
        console.print("[dim]All queries will be automatically analyzed for optimal agent selection[/dim]\n")

    except Exception as e:
        raise CrawllamaException(
            f"Adaptive System initialization failed: {e}\nThis feature is required in v{VERSION}.",
            1
        )

    # Handle stats display
    if args.stats:
        stats = agent.get_stats()
        console.print("\n[bold]Agent Statistics:[/bold]")
        console.print(json.dumps(stats, indent=2, ensure_ascii=False))
        return

    # Run in appropriate mode
    if args.query:
        # Direct query mode
        query = " ".join(args.query)
        direct_query_mode(agent, query, adaptive_processor)
    else:
        # Interactive mode with restart support
        while True:
            result = interactive_mode(agent, adaptive_processor, multihop_agent)

            if result == "RESTART":
                # Reload configuration
                console.print("[cyan]Reloading configuration...[/cyan]")
                config = load_config(args.config)

                # Override model if specified
                if args.model:
                    config["llm"]["model"] = args.model

                # Reinitialize agents
                try:
                    console.print("[cyan]Reinitializing agents...[/cyan]")

                    # Reinitialize standard agent
                    agent = SearchAgent(
                        config=config,
                        enable_web=not args.no_web,
                        debug=args.debug
                    )
                    console.print("[green][OK] SearchAgent restarted[/green]")

                    # Reinitialize multi-hop agent
                    multihop_agent = None
                    try:
                        multihop_agent = MultiHopReasoningAgent(
                            config=config,
                            max_hops=3,
                            confidence_threshold=0.7
                        )
                        console.print("[green][OK] MultiHopAgent restarted[/green]")
                    except Exception as e:
                        console.print(f"[yellow]⚠ MultiHopAgent not available: {e}[/yellow]")

                    # Reinitialize Adaptive System
                    adaptive_processor = None
                    if agent and multihop_agent:
                        try:
                            from core.adaptive_integration import initialize_adaptive_system
                            from core.cloud_llm_client import get_llm_client
                            from core.health import get_system_monitor, get_performance_tracker

                            llm_config = config.get("llm", {})
                            provider = llm_config.get("provider", "ollama")
                            
                            if provider == "ollama":
                                from core.llm_client import OllamaClient
                                llm = OllamaClient(
                                    base_url=llm_config.get("base_url", "http://127.0.0.1:11434"),
                                    model=llm_config.get("model", "qwen2.5:3b"),
                                    timeout=llm_config.get("timeout", 120)
                                )
                            else:
                                # Use cloud LLM client
                                llm = get_llm_client(
                                    provider=provider,
                                    model=llm_config.get("model", "gpt-3.5-turbo"),
                                    temperature=llm_config.get("temperature", 0.7),
                                    max_tokens=llm_config.get("max_tokens", 4096)
                                )

                            system_monitor = None
                            performance_tracker = None
                            try:
                                system_monitor = get_system_monitor()
                                performance_tracker = get_performance_tracker()
                            except Exception as e:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.warning(f"Failed to initialize system monitoring components: {e}")
                                # Continue with None values as fallback

                            adaptive_manager, adaptive_processor = initialize_adaptive_system(
                                llm=llm,
                                agent=agent,
                                multihop_agent=multihop_agent,
                                system_monitor=system_monitor,
                                performance_tracker=performance_tracker
                            )
                            console.print("[green][OK] Adaptive System restarted[/green]")
                        except Exception as e:
                            console.print(f"[yellow]⚠ Adaptive System not available: {e}[/yellow]")

                    console.print("[green][OK] All agents successfully restarted![/green]\n")
                except Exception as e:
                    console.print(f"[red]Error restarting: {e}[/red]")
                    console.print("[yellow]Continuing with old agents...[/yellow]\n")
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
