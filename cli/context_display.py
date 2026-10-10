"""Context-status display for the interactive CLI (token usage, session info)."""

from rich.table import Table

from cli.ui import console
from core.agent import SearchAgent


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
