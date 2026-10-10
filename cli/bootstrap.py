"""Startup bootstrap for the CLI: config loading, provider setup, env checks."""
import json
import logging
import os
import sys
from pathlib import Path

from rich.panel import Panel
from rich.prompt import Prompt

from cli.errors import CrawllamaException
from cli.ui import console
from utils.logger import Logger

logger = logging.getLogger(__name__)


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

