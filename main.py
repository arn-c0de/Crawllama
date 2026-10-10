"""CrawlLama - Local AI Search and Answer Agent

A fully local AI system that intelligently answers user queries by combining:
- Ollama (local LLM) for text understanding
- Autonomous web research with structured tool calls
- RAG (Retrieval-Augmented Generation) for context-based answers
"""
import argparse
import io
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from _version import __version__ as VERSION
from cli.settings_editor import edit_settings, show_settings
from cli.ui import console
from core.agent import SearchAgent
from core.agent.constants import QUICK_RESULT_REFERENCE_PATTERN, has_osint_operators
from core.langgraph_agent import MultiHopReasoningAgent, create_multihop_agent
from utils.cli_input import read_user_input
from utils.logger import Logger

# Force UTF-8 encoding for stdout/stderr to handle Unicode characters
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class CrawllamaException(Exception):
    """Custom exception for Crawllama application errors."""

    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code
        self.message = message


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def fetch_local_ollama_models(config: dict) -> tuple[list[str], str]:
    """Fetch locally downloaded Ollama models from Ollama API."""
    llm_config = config.get("llm", {})
    base_url = llm_config.get("base_url", "http://127.0.0.1:11434").rstrip("/")

    try:
        import requests
        response = requests.get(f"{base_url}/api/tags", timeout=3)
        response.raise_for_status()
        payload = response.json() if response.content else {}
        models = payload.get("models", [])

        names = []
        for model in models:
            name = str(model.get("name", "")).strip()
            if name:
                names.append(name)

        # Deduplicate while preserving order
        deduped = list(dict.fromkeys(names))
        return deduped, ""
    except Exception as e:
        return [], str(e)


def load_config(config_path: str = "config.json") -> dict:
    """Load configuration from JSON file."""
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise CrawllamaException(f"Config file not found: {config_path}", 1) from None
    except json.JSONDecodeError as e:
        raise CrawllamaException(f"Invalid JSON in config file: {e}", 1) from e


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


def save_config(config: dict, config_path: str = "config.json"):
    """
    Save configuration to JSON file.

    Args:
        config: Configuration dictionary
        config_path: Path to config file
    """
    try:
        # Atomic write (tmp + rename): a crash mid-write cannot truncate the
        # existing config file.
        tmp_path = f"{config_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, config_path)
        console.print(f"[green][OK] Configuration saved: {config_path}[/green]")
        return True
    except Exception as e:
        console.print(f"[red][X] Error saving: {e}[/red]")
        return False


# ---------------------------------------------------------------------------
# Startup checks
# ---------------------------------------------------------------------------

def _check_ollama_connection(llm_config: dict) -> dict:
    """Check Ollama connection with a quick check (2 attempts, 5 second timeout)."""
    import time

    import requests
    base_url = llm_config.get("base_url", "http://127.0.0.1:11434")

    last_error = None
    # Try twice with a short delay between attempts
    for attempt in range(2):
        try:
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            response.raise_for_status()
            console.print("[green][OK] Ollama connection successful[/green]")
            return {"status": True, "error_msg": ""}
        except Exception as e:
            last_error = e
            if attempt == 0:
                # Wait a bit before second attempt
                time.sleep(1)

    msg = "Ollama is not running or not accessible"
    console.print(f"[yellow][!] {msg}[/yellow]")
    console.print(f"[dim]Attempted URL: {base_url}/api/tags[/dim]")
    if last_error:
        console.print(f"[dim]Error: {type(last_error).__name__}: {str(last_error)[:100]}[/dim]")
    return {"status": False, "error_msg": msg}


def _check_cloud_api_key(provider: str) -> dict:
    """For cloud providers, just check if the API key is set."""
    import os
    key_name = f"{provider.upper()}_API_KEY"
    if os.getenv(key_name):
        console.print(f"[green][OK] {provider.title()} API key configured[/green]")
        return {"status": True, "error_msg": ""}

    msg = f"{provider.title()} API key not found. Please set {key_name} in .env file"
    console.print(f"[yellow][!] {msg}[/yellow]")
    return {"status": False, "error_msg": msg}


def _check_directories(config: dict) -> dict:
    """Create the data directories from config and report failures."""
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
        return {"status": False, "error_msg": "; ".join(dir_errors)}

    console.print("[green][OK] Directories initialized[/green]")
    return {"status": True, "error_msg": ""}


def _check_proxies() -> dict:
    """Validate proxies if configured."""
    from utils.proxy_validator import ProxyValidator
    from utils.tor_mode import get_tor_config, is_tor_enabled

    if is_tor_enabled():
        # Tor mode already verified the circuit on startup; the regular proxy
        # validation would only report its own SOCKS settings back.
        console.print(f"[green][OK] Tor mode active ({get_tor_config().proxy_url})[/green]")
        return {"status": True, "error_msg": ""}

    proxy_validator = ProxyValidator.load_from_env()

    if not proxy_validator.is_configured():
        console.print("[dim]No proxy configured (direct connection)[/dim]")
        return {"status": True, "error_msg": ""}

    console.print("[cyan]Validating proxy configuration...[/cyan]")
    proxy_results = proxy_validator.validate_proxies()
    if all(proxy_results.values()):
        console.print("[green][OK] Proxy configuration valid[/green]")
        return {"status": True, "error_msg": ""}

    msg = "Some proxies failed validation (will proceed without proxy)"
    console.print(f"[yellow]⚠ {msg}[/yellow]")
    return {"status": False, "error_msg": msg}


def _initialize_tor_mode_or_exit(config: dict) -> None:
    """Activate and verify Tor mode if enabled; abort startup on failure."""
    from utils.tor_mode import TorError, initialize_tor_mode

    try:
        tor_config = initialize_tor_mode(config)
    except TorError as e:
        raise CrawllamaException(f"Tor mode startup failed: {e}", 1) from e

    if tor_config.enabled:
        console.print(
            f"[green][OK] Tor mode active — all web traffic is routed via {tor_config.proxy_url}[/green]"
        )


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
        results["ollama"] = _check_ollama_connection(llm_config)
    else:
        results[provider] = _check_cloud_api_key(provider)

    results["directories"] = _check_directories(config)
    results["proxy"] = _check_proxies()
    return results


# ---------------------------------------------------------------------------
# Context status display
# ---------------------------------------------------------------------------

def _count_session_tokens(agent: SearchAgent) -> tuple[int, int]:
    """Count tokens used by the conversation history and saved search results."""
    conversation_tokens = 0
    for entry in agent.session.conversation_history:
        conversation_tokens += agent.context_manager.estimate_tokens(entry.get("query", ""))
        conversation_tokens += agent.context_manager.estimate_tokens(entry.get("response", ""))

    search_results_tokens = 0
    for result in agent.session.last_search_results:
        if isinstance(result, dict):
            search_results_tokens += agent.context_manager.estimate_tokens(
                result.get("title", "") + " " + result.get("snippet", "")
            )
    return conversation_tokens, search_results_tokens


def _build_context_table(conversation_tokens: int, search_results_tokens: int,
                         total_used: int, available_tokens: int,
                         max_tokens: int, usage_percent: float):
    """Build the context usage table."""
    from rich.table import Table

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
    return table


def _print_usage_bar(usage_percent: float) -> None:
    """Print a colored visual progress bar for the context usage."""
    # Determine color based on usage
    if usage_percent < 50:
        color = "green"
    elif usage_percent < 80:
        color = "yellow"
    else:
        color = "red"

    console.print("\n[bold]Context Usage:[/bold]")
    console.print(f"[{color}]{'█' * int(usage_percent / 2)}[/{color}]{'░' * int((100 - usage_percent) / 2)} {usage_percent:.1f}%")


def _print_session_info(agent: SearchAgent) -> None:
    """Print conversation and search result counts for the current session."""
    console.print("\n[dim]Session Info:[/dim]")
    console.print(
        f"  • Conversation Entries: {len(agent.session.conversation_history)}/{agent.session.max_history}"
    )
    console.print(f"  • Saved Search Results: {len(agent.session.last_search_results)}")
    if agent.session.last_search_query:
        console.print(f"  • Last Search: '{agent.session.last_search_query[:50]}...'")


def _print_memory_summary() -> None:
    """Print a summary of the memory store contents."""
    try:
        from core.memory_store import get_memory_store
        memory = get_memory_store()
        summary = memory.get_summary()

        console.print("\n[bold cyan]💾 Memory Store:[/bold cyan]")
        console.print(f"  📧 Emails:      {summary['emails']:,}")
        console.print(f"  📱 Phones:      {summary['phones']:,}")
        console.print(f"  🌐 IPs:         {summary['ips']:,}")
        console.print(f"  👤 Usernames:   {summary['usernames']:,}")
        console.print(f"  🔗 Domains:     {summary['domains']:,}")
        console.print(f"  📝 Notes:       {summary['notes']:,}")
        console.print(f"  [bold]Total:       {summary['total_entries']:,}[/bold]")
    except Exception as e:
        console.print(f"\n[dim]Memory Store: Not available ({e})[/dim]")


def show_context_status(agent: SearchAgent):
    """
    Display current context usage and available tokens.

    Args:
        agent: SearchAgent instance
    """
    # Use prompt budget (actual context budget) instead of response max_tokens
    max_tokens = max(1, agent.context_manager.prompt_budget)

    conversation_tokens, search_results_tokens = _count_session_tokens(agent)
    total_used = conversation_tokens + search_results_tokens
    available_tokens = max_tokens - total_used
    usage_percent = (total_used / max_tokens * 100) if max_tokens > 0 else 0

    console.print("\n")
    console.print(_build_context_table(
        conversation_tokens, search_results_tokens,
        total_used, available_tokens, max_tokens, usage_percent
    ))
    _print_usage_bar(usage_percent)
    _print_session_info(agent)
    _print_memory_summary()
    console.print()


# ---------------------------------------------------------------------------
# Query routing helpers (shared by interactive and direct query mode)
# ---------------------------------------------------------------------------

def _is_osint_query(agent: SearchAgent, query: str) -> bool:
    """Check whether the query uses OSINT operators or has OSINT intent."""
    return has_osint_operators(query) or agent.tools_flow.check_company_osint_intent(query)


def _is_result_reference(query: str) -> bool:
    """Check whether the query references a numbered search result."""
    return bool(QUICK_RESULT_REFERENCE_PATTERN.search(query.lower()))


def _direct_search_result(answer: str, complexity: str, reasoning: str) -> dict:
    """Build a result dict for queries that bypassed adaptive routing."""
    return {
        "answer": answer,
        "confidence": 1.0,
        "strategy": {
            "complexity": complexity,
            "agent_type": "SearchAgent",
            "use_multihop": False,
            "use_tools": True,
            "max_hops": 0,
            "reasoning": [reasoning]
        },
        "metadata": {
            "complexity_analysis": {},
            "resource_status": {},
            "attempts": 1,
            "escalation_history": [],
            "elapsed_time": 0.0
        }
    }


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def _ensure_osint_terms_accepted(agent: SearchAgent) -> None:
    """Check OSINT terms acceptance on startup and prompt if needed."""
    from core.osint import OSINTCompliance
    compliance = OSINTCompliance(config=agent.config)

    if compliance.check_terms_accepted("default"):
        return

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


def _print_interactive_banner() -> None:
    """Show the interactive mode welcome banner with the current version."""
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
        "Commands [dim](slash-prefixed)[/dim]:\n"
        "  [yellow]/help[/yellow]        - Show complete help\n"
        "  [yellow]/clear[/yellow]       - Reset session (history + cache)\n"
        "  [yellow]/stats[/yellow]       - Show statistics\n"
        "  [yellow]/settings[/yellow]    - View/change settings\n"
        "  [yellow]/export[/yellow]      - Export memory\n"
        "  [yellow]/exit, /quit[/yellow] - Exit\n\n"
        "[dim]Tip: Every query is automatically analyzed for optimal agent selection![/dim]",
        border_style="cyan"
    ))


def _print_help() -> None:
    """Show the help menu with all commands."""
    console.print(Panel.fit(
        "[bold cyan]CrawlLama - Help & Commands[/bold cyan]\n\n"
        "[bold yellow]🔧 System Commands [dim](slash-prefixed)[/dim]:[/bold yellow]\n"
        "  [cyan]/help, /hilfe, /?[/cyan]  - Show this help\n"
        "  [cyan]/clear[/cyan]             - Reset session (history + cache)\n"
        "  [cyan]/clear-cache[/cyan]       - Clear cache only\n"
        "  [cyan]/clear-memory[/cyan]      - Clear memory store only\n"
        "  [cyan]/clear-all[/cyan]         - Clear everything (session + cache + memory)\n"
        "  [cyan]/save[/cyan]              - Save session manually\n"
        "  [cyan]/load[/cyan]              - Reload session\n"
        "  [cyan]/export, /speichere ab[/cyan] - Export memory as file\n"
        "  [cyan]/export-report md[/cyan]  - Export last report as Markdown\n"
        "  [cyan]/export-report txt[/cyan] - Export last report as plain text\n"
        "  [cyan]/stats[/cyan]             - Show agent statistics\n"
        "  [cyan]/status[/cyan]            - Show context usage\n"
        "  [cyan]/settings[/cyan]          - View/change settings\n"
        "  [cyan]/restart[/cyan]           - Restart agent (reload config)\n"
        "  [cyan]/exit, /quit[/cyan]        - Exit program\n\n"
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
        "  [cyan]/clear-memory[/cyan]      - Clear entire memory store\n"
        "  [cyan]/export[/cyan]            - Export memory to file (JSON + TXT)\n\n"
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


def _cmd_clear_session(agent: SearchAgent) -> None:
    """Clear session data."""
    stats = agent.clear_session()
    console.clear()
    console.print("[green][OK] Session reset:[/green]")
    console.print(f"  • {stats['conversation_entries']} conversation entries deleted")
    console.print(f"  • {stats['search_results']} search results deleted")
    console.print(f"  • {stats['cache_files']} cache files deleted")

    # Show memory cleared if auto_clear_on_clear is enabled
    if stats.get('memory_entries', 0) > 0:
        console.print(f"  • {stats['memory_entries']} memory entries deleted")


def _cmd_show_stats(agent: SearchAgent) -> None:
    """Show agent statistics."""
    stats = agent.get_stats()
    console.print("\n[bold]Agent Statistics:[/bold]")
    console.print(json.dumps(stats, indent=2))


def _clear_cache() -> None:
    """Clear the cache and report the number of deleted files."""
    from core.cache import CacheManager
    cache = CacheManager()
    count = cache.clear()
    console.print(f"[green]Cache cleared: {count} files deleted[/green]")


def _cmd_clear_memory(agent: SearchAgent) -> None:
    """Clear only memory store (without session/cache)."""
    deleted_count = agent.clear_memory()
    if deleted_count > 0:
        console.print(f"[green][OK] Memory Store cleared: {deleted_count} entries removed[/green]")
    else:
        console.print("[yellow]⚠ Memory Store is already empty[/yellow]")


def _cmd_clear_all(agent: SearchAgent) -> None:
    """Clear everything: session, cache, and memory."""
    console.clear()
    console.print("[cyan]Clearing all data...[/cyan]\n")

    # Clear session (conversation history + search results)
    stats = agent.clear_session()
    console.print("[green][OK] Session cleared:[/green]")
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

    console.print("\n[bold green]✓ All data cleared successfully![/bold green]\n")


def _cmd_save_session(agent: SearchAgent) -> None:
    """Manually save the session."""
    success = agent.save_session()
    if success:
        console.print("[green][OK] Session saved:[/green]")
        console.print(f"  • {len(agent.session.conversation_history)} conversation entries")
        console.print(f"  • {len(agent.session.last_search_results)} search results")
        console.print("  • File: data/session.json")
    else:
        console.print("[red][X] Error saving session[/red]")


def _cmd_load_session(agent: SearchAgent) -> None:
    """Reload the session from disk."""
    success = agent.load_session()
    if success:
        console.print("[green][OK] Session loaded:[/green]")
        console.print(f"  • {len(agent.session.conversation_history)} conversation entries")
        console.print(f"  • {len(agent.session.last_search_results)} search results")
    else:
        console.print("[yellow]⚠ No saved session found[/yellow]")


def _cmd_export_memory() -> None:
    """Export a memory snapshot to file."""
    from core.memory_store import get_memory_store
    memory = get_memory_store()

    result = memory.export_memory_snapshot()

    if result.get('success'):
        console.print("[green][OK] Memory exported:[/green]")
        console.print(f"  • JSON: {result['json_file']}")
        console.print(f"  • Text: {result['txt_file']}")
        console.print(f"  • Timestamp: {result['timestamp']}")
        console.print(f"  • Total entries: {result['total_entries']}")
        console.print("\n[dim]Categories:[/dim]")
        for category, count in result['categories'].items():
            if count > 0:
                console.print(f"    • {category}: {count}")
    else:
        console.print(f"[red][X] Error exporting: {result.get('error', 'Unknown')}[/red]")


def _cmd_export_report(agent: SearchAgent, query: str) -> None:
    """Export the latest report to a .md or .txt file."""
    from core.report_exporter import export_report
    parts = query.strip().split()
    fmt = parts[1].lower() if len(parts) > 1 and parts[1].lower() in ("md", "txt") else "md"

    result = export_report(agent.session.conversation_history, fmt)

    if result["success"]:
        console.print(f"[green][OK] Report exported ({result['format'].upper()}):[/green]")
        console.print(f"  • Saved: {result['path']}")
    else:
        console.print(f"[red][X] Export failed: {result['error']}[/red]")


def _cmd_settings(agent: SearchAgent) -> str | None:
    """Show the settings menu. Returns 'RESTART' if the agent should restart."""
    show_settings(agent.config)

    edit_choice = Prompt.ask(
        "\n[cyan]Do you want to change the settings?[/cyan]",
        choices=["y", "n"],
        default="n"
    )
    if edit_choice.lower() != "y":
        return None

    agent.config = edit_settings(agent.config)

    save_choice = Prompt.ask(
        "\n[cyan]Save settings?[/cyan]",
        choices=["y", "n"],
        default="y"
    )
    if save_choice.lower() != "y":
        return None

    save_config(agent.config)

    restart_choice = Prompt.ask(
        "\n[cyan]Restart agent to apply changes?[/cyan]",
        choices=["y", "n"],
        default="y"
    )
    if restart_choice.lower() == "y":
        console.print("[yellow]Agent is restarting...[/yellow]")
        return "RESTART"  # Signal to restart agent

    console.print("[yellow]⚠ Some changes will only take effect after a restart.[/yellow]")
    return None


def _cmd_restart(agent: SearchAgent) -> None:
    """Offer to save the session before the agent restarts."""
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


def _handle_interactive_command(agent: SearchAgent, query: str) -> str | None:
    """
    Handle built-in interactive commands.

    Returns:
        "exit" to leave the loop, "restart" to restart the agent,
        "handled" if a command was processed, or None for normal queries.
    """
    command = query.lower()

    if command in ["exit", "quit"]:
        console.print("[yellow]Goodbye![/yellow]")
        return "exit"

    # "hilfe" is the German help keyword (kept to parse German user input)
    if command in ["help", "hilfe", "?"]:
        _print_help()
        return "handled"

    if command == "clear":
        _cmd_clear_session(agent)
        return "handled"

    if command == "stats":
        _cmd_show_stats(agent)
        return "handled"

    if command == "status":
        show_context_status(agent)
        return "handled"

    if command == "clear-cache":
        _clear_cache()
        return "handled"

    if command in ["clear-memory", "memory-clear"]:
        _cmd_clear_memory(agent)
        return "handled"

    if command == "clear-all":
        _cmd_clear_all(agent)
        return "handled"

    if command == "save":
        _cmd_save_session(agent)
        return "handled"

    if command == "load":
        _cmd_load_session(agent)
        return "handled"

    # "speichere ab" is the German export keyword (kept to parse German user input)
    if command in ["export", "export-memory", "speichere ab"]:
        _cmd_export_memory()
        return "handled"

    if command.startswith("export-report"):
        _cmd_export_report(agent, query)
        return "handled"

    if command == "settings":
        if _cmd_settings(agent) == "RESTART":
            return "restart"
        return "handled"

    if command == "restart":
        _cmd_restart(agent)
        return "restart"

    return None


def _print_adaptive_report(result: dict) -> None:
    """Print the Adaptive Intelligence Report for a query result."""
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
        console.print("\n[dim]Escalation History:[/dim]")
        for esc in metadata["escalation_history"]:
            console.print(f"  [dim]Attempt {esc['attempt']}:[/dim] {esc['from_agent']} → {esc['to_agent']}")
            console.print(f"  [dim]Reason:[/dim] {esc['reason']}")

    # Show timing and attempts
    console.print(f"[dim]Attempts:[/dim] {metadata['attempts']}")
    console.print(f"[dim]Processing Time:[/dim] {metadata['elapsed_time']:.2f}s")
    console.print("[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]\n")


def _print_query_failure(e: Exception) -> None:
    """Print an error message for a failed query, with hints for connection issues."""
    error_msg = str(e).lower()
    if "connection" in error_msg or "max retries exceeded" in error_msg or "11434" in error_msg:
        console.print("\n[red][X] LLM Provider is not available[/red]")
        console.print("[yellow]⚠️ Ollama is not running. Please either:[/yellow]")
        console.print("  [cyan]1.[/cyan] Start Ollama: Run 'ollama serve' in another terminal")
        console.print("  [cyan]2.[/cyan] Configure cloud provider: Type '/settings'\n")
    else:
        console.print(f"[red][X] Query processing failed: {e}[/red]")
        console.print("[dim]Please check system logs for details.[/dim]")


def _process_interactive_query(agent: SearchAgent, adaptive_processor, query: str) -> None:
    """Process a normal (non-command) query with the Adaptive System."""
    import logging
    logger = logging.getLogger("crawllama")

    console.print("\n[dim][Search] Analyzing query complexity...[/dim]\n")

    try:
        # OSINT queries and result references always use SearchAgent directly
        # (bypass adaptive routing).
        if _is_osint_query(agent, query):
            logger.info("OSINT query detected - using SearchAgent directly")
            answer = agent.query(query, use_tools=True)
            result = _direct_search_result(answer, "osint", "OSINT query - bypassed adaptive routing")
        elif _is_result_reference(query):
            logger.info("Result reference detected - using SearchAgent directly")
            answer = agent.query(query, use_tools=True)
            result = _direct_search_result(answer, "result_reference", "Result reference - bypassed adaptive routing")
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
            _print_adaptive_report(result)

    except Exception as e:
        _print_query_failure(e)


def interactive_mode(agent: SearchAgent, adaptive_processor=None, multihop_agent=None):
    """
    Run agent in interactive mode with Adaptive Agent Selection.

    Args:
        agent: Initialized SearchAgent instance
        adaptive_processor: AdaptiveQueryProcessor for intelligent agent selection (REQUIRED)
        multihop_agent: MultiHopReasoningAgent for complex queries
    """
    # Adaptive mode is always enabled
    if not adaptive_processor:
        console.print("[red][X] ERROR: Adaptive System is not available![/red]")
        console.print("[yellow]The Adaptive System is required. Please check initialization.[/yellow]")
        return

    _ensure_osint_terms_accepted(agent)
    _print_interactive_banner()

    while True:
        try:
            # Get user input
            query = read_user_input()

            if not query.strip():
                continue

            # Built-in commands are slash-only: "settings" is treated as a normal
            # query, while "/settings" runs the command. Everything after the
            # leading slash is dispatched to the command handler; if it is not a
            # known command it still falls through to normal query processing.
            query = query.strip()
            if query.startswith("/"):
                query = query[1:].lstrip()

                action = _handle_interactive_command(agent, query)
                if action == "exit":
                    break
                if action == "restart":
                    return "RESTART"  # Signal to restart agent
                if action == "handled":
                    continue

            _process_interactive_query(agent, adaptive_processor, query)

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Use '/exit' to quit.[/yellow]")
            continue
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


# ---------------------------------------------------------------------------
# Direct query mode
# ---------------------------------------------------------------------------

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

        if _is_osint_query(agent, query):
            # Force OSINT queries to use SearchAgent directly (bypass adaptive routing)
            logger.info("OSINT query detected - using SearchAgent directly")
            response = agent.query(query, use_tools=True)
            console.print(Markdown(response))
        elif _is_result_reference(query):
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
        raise CrawllamaException(f"Query processing failed: {e}", 1) from e


# ---------------------------------------------------------------------------
# Main entry point helpers
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
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

    return parser


def _require_config_file(config_path: str) -> None:
    """Exit with a setup hint if the configuration file does not exist."""
    if Path(config_path).is_file():
        return

    console.print(Panel(
        "[bold red]Configuration file 'config.json' not found![/bold red]\n\n"
        "Please run the setup first:\n"
        "- On Windows: [bold]run.bat[/bold]\n"
        "- On Linux/Mac: [bold]run.sh[/bold]",
        title="Setup Required",
        style="red"
    ))
    console.print("[bold]Press Enter to exit...[/bold]")
    try:
        sys.stdin.readline()
    except (EOFError, OSError) as e:
        # stdin not available in non-interactive environment — log and exit
        console.print("[bold yellow]No interactive input available; exiting.[/bold yellow]")
        console.print(f"[dim]stdin readline failed: {e}[/dim]")
    sys.exit(1)


def _load_and_adjust_config(config_path: str) -> dict:
    """Load the config and auto-adjust token limits based on the provider."""
    config = load_config(config_path)

    # Automatically adjust token limits based on provider (local vs cloud)
    original_max_tokens = config.get("llm", {}).get("max_tokens")
    config = adjust_config_for_provider(config)

    # Save config if max_tokens was adjusted
    if config.get("llm", {}).get("max_tokens") != original_max_tokens:
        save_config(config, config_path)

    return config


def _configure_logging(config: dict, debug: bool) -> None:
    """Set up the application logger from the config."""
    log_config = config.get("logging", {})
    Logger.configure(
        log_file=log_config.get("file", "logs/app.log"),
        level="DEBUG" if debug else log_config.get("level", "INFO"),
    )
    Logger.get("crawllama")


def _suggest_default_model(provider: str, config: dict) -> str:
    """Print model suggestions for the provider and return a sensible default."""
    if provider == "openai":
        console.print("[dim]OpenAI Models: gpt-4o-mini (fast, cheap), gpt-4o, gpt-4.1, gpt-4.1-mini[/dim]")
        return "gpt-4o-mini"
    if provider == "anthropic":
        console.print("[dim]Anthropic Models: claude-opus-4-8 (most capable), claude-sonnet-4-6 (balanced), claude-haiku-4-5 (fast, cheap)[/dim]")
        return "claude-opus-4-8"
    if provider == "groq":
        console.print("[dim]Groq Models: llama-3.3-70b-versatile, llama-3.1-8b-instant, openai/gpt-oss-20b[/dim]")
        return "llama-3.3-70b-versatile"

    # ollama
    local_models, fetch_error = fetch_local_ollama_models(config)
    suggested_models = ["qwen2.5:3b", "qwen3:8b", "deepseek-r1:8b", "llama3:7b"]

    if local_models:
        console.print(f"[dim]Ollama Models (local): {', '.join(local_models)}[/dim]")
        default_model = local_models[0]
    else:
        console.print("[dim]Ollama Models (local): none detected[/dim]")
        if fetch_error:
            console.print(f"[dim]Could not fetch local models: {fetch_error[:120]}[/dim]")
        default_model = "qwen3:8b"

    console.print(f"[dim]Ollama Models (suggested): {', '.join(suggested_models)}[/dim]")
    return default_model


def _configure_provider_interactively(config: dict) -> None:
    """Direct LLM provider configuration when Ollama is unavailable. Always exits."""
    console.print("\n[bold cyan]Configure LLM Provider:[/bold cyan]\n")

    # LLM Provider Selection
    console.print("[dim]Available Providers:[/dim]")
    console.print("  [dim]• ollama - Local models (free, requires Ollama running)[/dim]")
    console.print("  [dim]• openai - GPT-3.5, GPT-4 (API key required)[/dim]")
    console.print("  [dim]• anthropic - Claude 3 (API key required)[/dim]")
    console.print("  [dim]• groq - Mixtral, LLaMA (free tier available)[/dim]\n")

    new_provider = Prompt.ask(
        "[cyan]Select LLM Provider[/cyan]",
        choices=["ollama", "openai", "anthropic", "groq"],
        default="openai"
    )

    config["llm"]["provider"] = new_provider
    console.print(f"[green][OK] Provider changed to: {new_provider}[/green]\n")

    # Model selection based on provider
    default_model = _suggest_default_model(new_provider, config)
    new_model = Prompt.ask(
        "[cyan]Select Model[/cyan]",
        default=default_model
    )

    config["llm"]["model"] = new_model
    console.print(f"[green][OK] Model changed to: {new_model}[/green]\n")

    # Show API key instructions for cloud providers
    if new_provider in ["openai", "anthropic", "groq"]:
        key_name = f"{new_provider.upper()}_API_KEY"
        console.print("[yellow]⚠️ Important: Set your API key in .env file:[/yellow]")
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


def _handle_unavailable_ollama(config: dict) -> None:
    """Warn that Ollama is down and ask the user what to do. May exit."""
    # Suppress retry warnings from tenacity to avoid spam
    import logging
    logging.getLogger("tenacity").setLevel(logging.ERROR)
    logging.getLogger("crawllama").setLevel(logging.ERROR)

    console.print("\n" + "="*70)
    console.print(Panel.fit(
        "[bold yellow]⚠️  LLM Provider Not Available[/bold yellow]\n\n"
        "[yellow]Ollama is not running or not accessible.[/yellow]\n\n"
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
        _configure_provider_interactively(config)  # always exits
    elif choice == "exit":
        console.print("[yellow]Exiting...[/yellow]")
        sys.exit(0)
    else:
        console.print("\n[yellow]⚠️ Continuing without working LLM. Queries will fail until you configure a provider.[/yellow]")
        console.print("[dim]Type '/settings' to configure a provider later.[/dim]\n")


def _prompt_for_installed_model(config: dict, config_path: str, local_models: list[str]) -> None:
    """Let the user pick one of the locally installed Ollama models."""
    new_model = Prompt.ask(
        "[cyan]Select an installed model[/cyan]",
        choices=local_models,
        default=local_models[0],
    )
    config["llm"]["model"] = new_model
    console.print(f"[green][OK] Model changed to: {new_model}[/green]")

    save_choice = Prompt.ask(
        "[cyan]Save this choice to config.json?[/cyan]",
        choices=["y", "n"],
        default="y",
    )
    if save_choice.lower() == "y":
        save_config(config, config_path)
        console.print("[green][OK] Saved to config.json[/green]\n")
    else:
        console.print("[dim]Using the selection for this session only.[/dim]\n")


def _verify_ollama_model_installed(config: dict, config_path: str) -> None:
    """
    Verify the selected Ollama model is actually installed.

    Ollama returns HTTP 404 ("model not found") from /api/generate at query
    time when the configured model was never pulled, which is confusing.
    Catch it here and let the user pick from the locally available models
    instead.
    """
    selected_model = config.get("llm", {}).get("model", "")
    local_models, fetch_error = fetch_local_ollama_models(config)

    if local_models and selected_model not in local_models:
        console.print("\n" + "=" * 70)
        console.print(Panel.fit(
            "[bold yellow]⚠️  Selected Ollama model not installed[/bold yellow]\n\n"
            f"[yellow]Configured model:[/yellow] [bold]{selected_model or '(none)'}[/bold]\n"
            "[yellow]It is not available in Ollama, so queries would fail with a 404.[/yellow]\n\n"
            "[bold cyan]Installed models:[/bold cyan]\n  • " + "\n  • ".join(local_models),
            title="Model Selection",
            border_style="yellow",
        ))
        console.print("=" * 70)

        if sys.stdin.isatty():
            _prompt_for_installed_model(config, config_path, local_models)
        else:
            # Non-interactive (scripted) run: fall back to the first installed
            # model for this session so the query can still proceed.
            config["llm"]["model"] = local_models[0]
            console.print(
                f"[yellow]Non-interactive run: falling back to '{local_models[0]}' "
                "for this session.[/yellow]\n"
            )
    elif not local_models:
        console.print(Panel.fit(
            "[bold yellow]⚠️  No Ollama models installed[/bold yellow]\n\n"
            "[yellow]Pull one before querying, e.g.:[/yellow]\n"
            f"  [cyan]ollama pull {selected_model or 'llama3.1:8b'}[/cyan]"
            + (f"\n\n[dim]Note: {fetch_error[:120]}[/dim]" if fetch_error else ""),
            title="Model Selection",
            border_style="yellow",
        ))


def _clean_cache_on_startup(config: dict) -> None:
    """Clear cache on startup if configured; otherwise just remove expired entries."""
    from core.cache import CacheManager
    cache = CacheManager(
        cache_dir=config.get("paths", {}).get("cache_dir", "data/cache"),
        ttl_hours=config.get("cache", {}).get("ttl_hours", 24),
        max_size_mb=config.get("cache", {}).get("max_size_mb", 500)
    )

    if config.get("cache", {}).get("clear_on_startup", False):
        console.print("[cyan]Clearing cache on startup (configured)...[/cyan]")
        cleared_count = cache.clear()
        console.print(f"[green][OK] Cache cleared: {cleared_count} files deleted[/green]")
        return

    # Just clear expired entries
    console.print("[cyan]Clearing expired cache entries...[/cyan]")
    cleared_count = cache.clear_expired()
    if cleared_count > 0:
        console.print(f"[green][OK] Expired cache cleared: {cleared_count} files deleted[/green]")
    else:
        console.print("[dim]No expired cache entries found[/dim]")


def _create_search_agent(config: dict, args: argparse.Namespace) -> SearchAgent:
    """Initialize the standard SearchAgent."""
    try:
        agent = SearchAgent(
            config=config,
            enable_web=not args.no_web,
            debug=args.debug
        )
        console.print("[green][OK] SearchAgent initialized[/green]")
        return agent
    except Exception as e:
        raise CrawllamaException(f"Failed to initialize agent: {e}", 1) from e


def _create_multihop_agent(config: dict) -> MultiHopReasoningAgent | None:
    """Initialize the multi-hop agent (optional, for adaptive mode)."""
    try:
        multihop_agent = create_multihop_agent(config)
        console.print("[green][OK] MultiHopAgent initialized[/green]")
        return multihop_agent
    except Exception as e:
        console.print(f"[yellow]⚠ MultiHopAgent not available: {e}[/yellow]")
        console.print("[dim]Adaptive mode will be limited[/dim]")
        return None


def _create_llm_client(config: dict):
    """Create the LLM client used for complexity detection (local or cloud)."""
    from core.cloud_llm_client import create_llm_client_from_config

    return create_llm_client_from_config(config.get("llm", {}))


def _build_adaptive_processor(config: dict, agent: SearchAgent, multihop_agent):
    """Build the adaptive query processor (shared by create/restart paths).

    Wires the complexity-detection LLM, optional system monitoring and the
    adaptive manager. Raises on hard failure; callers decide how to surface it.
    """
    from core.adaptive_integration import initialize_adaptive_system
    from core.health import get_performance_tracker, get_system_monitor

    # LLM client for complexity detection (supports both local and cloud).
    llm = _create_llm_client(config)

    # System monitoring is optional - degrade quietly if it is unavailable.
    system_monitor = None
    performance_tracker = None
    try:
        system_monitor = get_system_monitor()
        performance_tracker = get_performance_tracker()
    except Exception:
        console.print("[yellow]⚠ System monitoring unavailable (optional)[/yellow]")

    _adaptive_manager, adaptive_processor = initialize_adaptive_system(
        llm=llm,
        agent=agent,
        multihop_agent=multihop_agent,
        system_monitor=system_monitor,
        performance_tracker=performance_tracker
    )
    return adaptive_processor


def _create_adaptive_processor(config: dict, agent: SearchAgent,
                               multihop_agent: MultiHopReasoningAgent | None):
    """Initialize the Adaptive System (REQUIRED for v1.4.4+)."""
    if not multihop_agent:
        raise CrawllamaException(
            "MultiHopAgent initialization failed. Adaptive System requires both SearchAgent and MultiHopAgent.",
            1
        )

    try:
        adaptive_processor = _build_adaptive_processor(config, agent, multihop_agent)
        console.print("[green][OK] Adaptive Hopping System initialized[/green]")
        console.print("[bold green][AI] Adaptive Intelligence: ACTIVE[/bold green]")
        console.print("[dim]All queries will be automatically analyzed for optimal agent selection[/dim]\n")
        return adaptive_processor
    except Exception as e:
        raise CrawllamaException(
            f"Adaptive System initialization failed: {e}\nThis feature is required in v{VERSION}.",
            1
        ) from e


def _restart_adaptive_processor(config: dict, agent: SearchAgent, multihop_agent):
    """Re-create the adaptive processor after a restart. Returns None if unavailable."""
    try:
        adaptive_processor = _build_adaptive_processor(config, agent, multihop_agent)
        console.print("[green][OK] Adaptive System restarted[/green]")
        return adaptive_processor
    except Exception as e:
        console.print(f"[yellow]⚠ Adaptive System not available: {e}[/yellow]")
        return None


def _reinitialize_agents(config: dict, args: argparse.Namespace) -> tuple:
    """
    Re-create all agents after a settings change.

    Raises if the SearchAgent fails; the multi-hop agent and the adaptive
    processor degrade to None on failure.
    """
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
        adaptive_processor = _restart_adaptive_processor(config, agent, multihop_agent)

    return agent, multihop_agent, adaptive_processor


def _run_interactive_with_restart(args: argparse.Namespace, agent: SearchAgent,
                                  multihop_agent, adaptive_processor) -> None:
    """Run interactive mode, restarting the agents when requested."""
    while True:
        result = interactive_mode(agent, adaptive_processor, multihop_agent)

        if result != "RESTART":
            # Normal exit
            break

        # Reload configuration
        console.print("[cyan]Reloading configuration...[/cyan]")
        config = load_config(args.config)

        # Override model if specified
        if args.model:
            config["llm"]["model"] = args.model

        try:
            console.print("[cyan]Reinitializing agents...[/cyan]")
            agent, multihop_agent, adaptive_processor = _reinitialize_agents(config, args)
            console.print("[green][OK] All agents successfully restarted![/green]\n")
        except Exception as e:
            console.print(f"[red]Error restarting: {e}[/red]")
            console.print("[yellow]Continuing with old agents...[/yellow]\n")


def main():
    """Main entry point."""
    args = _build_arg_parser().parse_args()

    # Handle API key setup
    if args.setup_keys:
        from utils.secure_config import SecureConfig
        config_manager = SecureConfig()
        config_manager.setup_interactive()
        return

    # Load environment variables
    load_dotenv()

    # Check for config.json existence before loading
    _require_config_file(args.config)
    config = _load_and_adjust_config(args.config)

    # Override model if specified
    if args.model:
        config["llm"]["model"] = args.model

    _configure_logging(config, args.debug)

    # Tor mode must be active (and verified) before any other component can
    # make a web request; an unreachable Tor network aborts startup.
    _initialize_tor_mode_or_exit(config)

    # Handle cache clearing
    if args.clear_cache:
        _clear_cache()
        return

    # Startup checks
    startup_results = startup_check(config)

    # Check for critical failures (directories)
    if startup_results.get("directories", {}).get("status") is False:
        raise CrawllamaException("Critical: Directory initialization failed", 1)

    # Show warning if Ollama is not available and ask user what to do
    ollama_unavailable = startup_results.get("ollama", {}).get("status") is False
    if ollama_unavailable:
        _handle_unavailable_ollama(config)

    provider = config.get("llm", {}).get("provider", "ollama")
    if provider == "ollama" and not ollama_unavailable:
        _verify_ollama_model_installed(config, args.config)

    _clean_cache_on_startup(config)

    # Initialize agents and the Adaptive System
    agent = _create_search_agent(config, args)
    multihop_agent = _create_multihop_agent(config)
    adaptive_processor = _create_adaptive_processor(config, agent, multihop_agent)

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
        _run_interactive_with_restart(args, agent, multihop_agent, adaptive_processor)


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
