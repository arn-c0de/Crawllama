"""Interactive settings viewer and editor for the CrawlLama CLI.

Extracted from ``main.py`` to keep the entry point focused on argument
parsing and the run loop. ``main`` re-imports :func:`show_settings` and
:func:`edit_settings` from here.
"""
import re

from rich.prompt import Prompt

from cli.ui import console


class InputValidator:
    """Input validation helper for settings."""

    @staticmethod
    def validate_float(value: str, min_val: float = None, max_val: float = None) -> float | None:
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
    def validate_int(value: str, min_val: int = None, max_val: int = None) -> int | None:
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


def _ask_int_setting(section: dict, key: str, prompt_label: str, current: int,
                     change_label: str, min_val: int | None = None,
                     max_val: int | None = None, unit: str = "") -> None:
    """Prompt for an integer setting and store it on change.

    Warns on non-numeric input; silently keeps the old value when the input
    is out of range or unchanged.
    """
    raw = Prompt.ask(f"[cyan]{prompt_label}[/cyan]", default=str(current))
    try:
        value = int(raw)
    except ValueError:
        console.print("[yellow]Invalid value, skipping...[/yellow]")
        return
    if min_val is not None and value < min_val:
        return
    if max_val is not None and value > max_val:
        return
    if value == current:
        return
    section[key] = value
    console.print(f"[green][OK] {change_label} changed: {value}{unit}[/green]")


def _ask_bool_setting(section: dict, key: str, prompt_label: str, current: bool,
                      change_label: str) -> None:
    """Prompt for a true/false setting and report when it changes."""
    answer = Prompt.ask(
        f"[cyan]{prompt_label}[/cyan]",
        choices=["true", "false"],
        default=str(current).lower()
    )
    if answer != str(current).lower():
        section[key] = (answer == "true")
        console.print(f"[green][OK] {change_label} changed: {answer}[/green]")


def _ask_float_or_keep(section: dict, key: str, prompt_label: str, current: float) -> None:
    """Prompt for a float; keep the existing value if user provides invalid input."""
    raw = Prompt.ask(f"[cyan]{prompt_label}[/cyan]", default=str(current))
    try:
        section[key] = float(raw)
    except ValueError:
        pass  # Keep existing value if user provides invalid input


def _edit_llm_provider(config: dict) -> None:
    """Prompt for the LLM provider."""
    current_provider = config.get("llm", {}).get("provider", "ollama")
    console.print("\n[dim]Available Providers:[/dim]")
    console.print("[dim]  • ollama - Local models (free)[/dim]")
    console.print("[dim]  • openai - GPT-3.5, GPT-4 (API key required)[/dim]")
    console.print("[dim]  • anthropic - Claude 3 (API key required)[/dim]")
    console.print("[dim]  • groq - Mixtral, LLaMA (free with Free Tier)[/dim]")

    new_provider = Prompt.ask(
        "[cyan]LLM Provider[/cyan]",
        choices=["ollama", "openai", "anthropic", "groq"],
        default=current_provider
    )

    if new_provider == current_provider:
        return

    config["llm"]["provider"] = new_provider
    console.print(f"[green][OK] Provider changed: {new_provider}[/green]")

    # Show API key requirements for cloud providers
    if new_provider in ["openai", "anthropic", "groq"]:
        key_name = f"{new_provider.upper()}_API_KEY"
        console.print(f"[yellow]⚠️ {new_provider.title()} requires an API key![/yellow]")
        console.print(f"[dim]Set {key_name} in .env file[/dim]")


def _print_settings_model_suggestions(provider: str, config: dict) -> None:
    """Print provider-specific model suggestions for the settings editor."""
    from cli.bootstrap import _suggest_default_model

    console.print()
    _suggest_default_model(provider, config)


def _edit_llm_model(config: dict) -> None:
    """Prompt for the LLM model (with provider-specific suggestions)."""
    current_model = config.get("llm", {}).get("model", "qwen2.5:3b")
    provider = config.get("llm", {}).get("provider", "ollama")
    _print_settings_model_suggestions(provider, config)

    new_model = Prompt.ask("[cyan]LLM Model[/cyan]", default=current_model)

    if not new_model or new_model == current_model:
        return
    if InputValidator.validate_model_name(new_model):
        config["llm"]["model"] = new_model
        console.print(f"[green][OK] Model changed: {new_model}[/green]")
    else:
        console.print("[red]❌ Invalid model name! Allowed: Letters, numbers, '.', ':', '-', '_'[/red]")


def _edit_llm_temperature(config: dict) -> None:
    """Prompt for the LLM temperature."""
    current_temp = config.get("llm", {}).get("temperature", 0.7)
    new_temp = Prompt.ask(
        "[cyan]Temperature (0.0-1.0)[/cyan]",
        default=str(current_temp)
    )

    temp_value = InputValidator.validate_float(new_temp, 0.0, 1.0)
    if temp_value is not None and temp_value != current_temp:
        config["llm"]["temperature"] = temp_value
        console.print(f"[green][OK] Temperature changed: {temp_value}[/green]")
    elif temp_value is None:
        console.print("[red]❌ Invalid value! Temperature must be between 0.0 and 1.0.[/red]")


def _edit_llm_max_tokens(config: dict) -> None:
    """Prompt for the max tokens / context size."""
    current_tokens = config.get("llm", {}).get("max_tokens", 10000)
    new_tokens = Prompt.ask(
        "[cyan]Max Tokens / Context Size (1000-32000)[/cyan]",
        default=str(current_tokens)
    )

    tokens_value = InputValidator.validate_int(new_tokens, 1000, 32000)
    if tokens_value is not None and tokens_value != current_tokens:
        config["llm"]["max_tokens"] = tokens_value
        console.print(f"[green][OK] Max Tokens changed: {tokens_value}[/green]")
        console.print("[dim]Recommendation: RTX 3080+ → 10k-16k, RTX 3060/70 → 6k-8k, CPU → 2k-4k[/dim]")
    elif tokens_value is None:
        console.print("[red]❌ Invalid value! Max Tokens must be between 1000 and 32000.[/red]")


def _edit_llm_settings(config: dict) -> None:
    """Edit all LLM settings interactively."""
    console.print("\n[bold cyan]=== LLM Settings ===[/bold cyan]")
    _edit_llm_provider(config)
    _edit_llm_model(config)
    _edit_llm_temperature(config)
    _edit_llm_max_tokens(config)


def _edit_search_settings(config: dict) -> None:
    """Edit search settings interactively."""
    console.print("\n[bold cyan]=== Search Settings ===[/bold cyan]")

    # Max Results
    current_max = config.get("search", {}).get("max_results", 10)
    new_max = Prompt.ask(
        "[cyan]Max Search Results (1-100)[/cyan]",
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
        "[cyan]Search Region[/cyan]",
        choices=["de-de", "us-en", "wt-wt", "gb-en", "fr-fr"],
        default=current_region
    )
    if new_region and new_region != current_region:
        config["search"]["region"] = new_region
        console.print(f"[green][OK] Region changed: {new_region}[/green]")


def _edit_rag_settings(config: dict) -> None:
    """Edit RAG settings interactively."""
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
        "[cyan]Enable RAG? (y/n)[/cyan]",
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
        "[cyan]Embedding Model[/cyan]",
        default=current_model
    )
    if new_model != current_model:
        config["rag"]["embedding_model"] = new_model
        console.print(f"[green][OK] Embedding Model changed: {new_model}[/green]")

    # Top K
    current_topk = config.get("rag", {}).get("top_k", 5)
    new_topk = Prompt.ask(
        "[cyan]Top K (Number of RAG documents, 1-20)[/cyan]",
        default=str(current_topk)
    )

    topk_value = InputValidator.validate_int(new_topk, 1, 20)
    if topk_value is not None and topk_value != current_topk:
        config["rag"]["top_k"] = topk_value
        console.print(f"[green][OK] Top K changed: {topk_value}[/green]")
    elif topk_value is None:
        console.print("[red]❌ Invalid value! Top K must be between 1 and 20.[/red]")


def _edit_cache_settings(config: dict) -> None:
    """Edit cache settings interactively."""
    console.print("\n[bold cyan]=== Cache Settings ===[/bold cyan]")

    # Cache Enabled
    current_cache = config.get("cache", {}).get("enabled", True)
    cache_choice = Prompt.ask(
        "[cyan]Enable cache? (y/n)[/cyan]",
        default="y" if current_cache else "n",
        choices=["y", "n"]
    )
    new_cache = cache_choice.lower() == "y"
    if new_cache != current_cache:
        config["cache"]["enabled"] = new_cache
        console.print(f"[green][OK] Cache {'enabled' if new_cache else 'disabled'}[/green]")


def _edit_osint_settings(config: dict) -> None:
    """Edit OSINT settings interactively."""
    console.print("\n[bold cyan]=== OSINT Settings ===[/bold cyan]")

    # Ensure osint config exists
    if "osint" not in config:
        config["osint"] = {
            "max_results": 20,
            "email_search_limit": 50,
            "phone_search_limit": 50,
            "general_osint_limit": 100
        }
    osint = config["osint"]

    _ask_int_setting(osint, "max_results", "OSINT Max Results (1-50)",
                     osint.get("max_results", 20), "OSINT Max Results",
                     min_val=1, max_val=50)
    _ask_int_setting(osint, "email_search_limit", "Email Search Limit per hour",
                     osint.get("email_search_limit", 50), "Email Search Limit")
    _ask_int_setting(osint, "phone_search_limit", "Phone Search Limit per hour",
                     osint.get("phone_search_limit", 50), "Phone Search Limit")
    _ask_int_setting(osint, "general_osint_limit", "General OSINT Limit per hour",
                     osint.get("general_osint_limit", 100), "General OSINT Limit")

    # Safesearch Mode
    current_safesearch = osint.get("safesearch", "strict")
    console.print("\n[dim]Safesearch improves search result quality for OSINT investigations[/dim]")
    console.print("[dim]  • off: No filtering[/dim]")
    console.print("[dim]  • moderate: Moderate filtering (default DuckDuckGo)[/dim]")
    console.print("[dim]  • strict: Strict filtering (recommended for best quality)[/dim]")
    new_safesearch = Prompt.ask(
        "[cyan]Safesearch Mode[/cyan]",
        choices=["off", "moderate", "strict"],
        default=current_safesearch
    )
    if new_safesearch and new_safesearch != current_safesearch:
        osint["safesearch"] = new_safesearch
        console.print(f"[green][OK] Safesearch Mode changed: {new_safesearch}[/green]")


def _edit_memory_settings(config: dict) -> None:
    """Edit memory store settings interactively."""
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
    memory = config["memory"]

    _ask_bool_setting(memory, "enabled", "Memory Store Enabled (true/false)",
                      memory.get("enabled", True), "Memory Store Enabled")

    console.print("\n[dim]Auto Clear on Clear: Clears Memory Store on 'clear' command[/dim]")
    console.print("[dim]  • false: Memory persists (recommended for persistent data)[/dim]")
    console.print("[dim]  • true: Memory is cleared[/dim]")
    _ask_bool_setting(memory, "auto_clear_on_clear", "Auto Clear on Clear (true/false)",
                      memory.get("auto_clear_on_clear", False), "Auto Clear on Clear")

    _ask_int_setting(memory, "max_entries", "Max Entries (100-10000)",
                     memory.get("max_entries", 1000), "Max Entries",
                     min_val=100, max_val=10000)
    _ask_int_setting(memory, "max_file_size_mb", "Max File Size in MB (1-100)",
                     memory.get("max_file_size_mb", 10), "Max File Size",
                     min_val=1, max_val=100, unit=" MB")


def _edit_hallucination_settings(config: dict) -> None:
    """Edit hallucination detection settings interactively."""
    console.print("\n[bold cyan]=== Hallucination Detection Settings ===[/bold cyan]")
    hallu_config = config.get("hallucination_detection", {})

    # Enabled
    new_enabled = Prompt.ask(
        "[cyan]Detection Enabled (true/false)[/cyan]",
        choices=["true", "false"],
        default=str(hallu_config.get("enabled", False)).lower()
    )
    hallu_config["enabled"] = (new_enabled == "true")

    # Detection Level
    hallu_config["detection_level"] = Prompt.ask(
        "[cyan]Detection Level (low/medium/high)[/cyan]",
        choices=["low", "medium", "high"],
        default=hallu_config.get("detection_level", "medium")
    )

    # Warning Mode
    hallu_config["warning_mode"] = Prompt.ask(
        "[cyan]Warning Mode (silent/log/flag_response/block)[/cyan]",
        choices=["silent", "log", "flag_response", "block"],
        default=hallu_config.get("warning_mode", "flag_response")
    )

    # Thresholds
    _ask_float_or_keep(hallu_config, "hallucination_threshold",
                       "Hallucination Threshold (0.0-1.0)",
                       hallu_config.get("hallucination_threshold", 0.7))
    _ask_float_or_keep(hallu_config, "context_alignment_threshold",
                       "Context Alignment Threshold (0.0-1.0)",
                       hallu_config.get("context_alignment_threshold", 0.4))

    # Fact Checking
    new_fact = Prompt.ask(
        "[cyan]Fact Checking Enabled (true/false)[/cyan]",
        choices=["true", "false"],
        default=str(hallu_config.get("fact_checking_enabled", True)).lower()
    )
    hallu_config["fact_checking_enabled"] = (new_fact == "true")

    # Max Processing Time
    _ask_float_or_keep(hallu_config, "max_processing_time",
                       "Max Processing Time (seconds)",
                       hallu_config.get("max_processing_time", 10.0))

    config["hallucination_detection"] = hallu_config


def _edit_ui_settings(config: dict) -> None:
    """Edit UI display settings interactively."""
    console.print("\n[bold cyan]=== UI Display Settings ===[/bold cyan]")

    # Ensure UI config exists
    if "ui" not in config:
        config["ui"] = {
            "show_adaptive_report": True
        }

    # Show Adaptive Report
    current_show_report = config.get("ui", {}).get("show_adaptive_report", True)
    console.print("\n[dim]Adaptive Intelligence Report: Shows details after each query[/dim]")
    console.print("[dim]  • Complexity level (LOW/MID/HIGH)[/dim]")
    console.print("[dim]  • Selected Agent (SearchAgent/MultiHopReasoningAgent)[/dim]")
    console.print("[dim]  • Reasoning for agent selection[/dim]")
    console.print("[dim]  • Confidence score[/dim]")
    console.print("[dim]  • Processing time and attempts[/dim]")
    new_show_report = Prompt.ask(
        "[cyan]Show Adaptive Intelligence Report (y/n)[/cyan]",
        choices=["y", "n"],
        default="y" if current_show_report else "n"
    )
    if new_show_report != ("y" if current_show_report else "n"):
        config["ui"]["show_adaptive_report"] = (new_show_report == "y")
        console.print(f"[green][OK] Adaptive Report {'enabled' if new_show_report == 'y' else 'disabled'}[/green]")


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

    all_categories = ["llm", "search", "rag", "cache", "osint", "memory", "hallucination", "ui"]

    # Category selection
    category_choice = Prompt.ask(
        "[cyan]Which category do you want to change?[/cyan]",
        choices=all_categories + ["all"],
        default="all"
    )
    categories = all_categories if category_choice == "all" else [category_choice]

    editors = {
        "llm": _edit_llm_settings,
        "search": _edit_search_settings,
        "rag": _edit_rag_settings,
        "cache": _edit_cache_settings,
        "osint": _edit_osint_settings,
        "memory": _edit_memory_settings,
        "hallucination": _edit_hallucination_settings,
        "ui": _edit_ui_settings,
    }
    for category in categories:
        editors[category](config)

    return config
