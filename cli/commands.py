"""Interactive-mode command handlers (/help, /clear, /settings, /export, ...)."""
import json
import logging

from rich.panel import Panel
from rich.prompt import Prompt

from _version import __version__ as VERSION
from cli.bootstrap import save_config
from cli.context_display import show_context_status
from cli.settings_editor import edit_settings, show_settings
from cli.ui import console
from core.agent import SearchAgent

logger = logging.getLogger(__name__)


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


def _clear_agent_cache(agent: SearchAgent) -> int:
    """Clear the agent's own cache (configured directory and in-memory LRU)."""
    if agent.cache is not None:
        return agent.cache.clear()
    from core.cache import CacheManager
    return CacheManager.from_config(agent.config).clear()


def _clear_cache(agent: SearchAgent) -> None:
    """Clear the cache and report the number of deleted files."""
    count = _clear_agent_cache(agent)
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
    cache_count = _clear_agent_cache(agent)
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
        _clear_cache(agent)
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

