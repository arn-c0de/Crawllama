"""CrawlLama - Local AI Search and Answer Agent

A fully local AI system that intelligently answers user queries by combining:
- Ollama (local LLM) for text understanding
- Autonomous web research with structured tool calls
- RAG (Retrieval-Augmented Generation) for context-based answers
"""
import argparse
import io
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.markdown import Markdown
from rich.prompt import Prompt

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from _version import __version__ as VERSION
from cli.bootstrap import (
    _clean_cache_on_startup,
    _configure_logging,
    _handle_unavailable_ollama,
    _initialize_tor_mode_or_exit,
    _load_and_adjust_config,
    _require_config_file,
    _verify_ollama_model_installed,
    startup_check,
)
from cli.commands import (
    _clear_cache,
    _handle_interactive_command,
    _print_interactive_banner,
)
from cli.errors import CrawllamaException
from cli.ui import console
from core.agent import SearchAgent
from core.agent.constants import QUICK_RESULT_REFERENCE_PATTERN, has_osint_operators
from core.langgraph_agent import MultiHopReasoningAgent, create_multihop_agent
from utils.cli_input import read_user_input

# Force UTF-8 encoding for stdout/stderr to handle Unicode characters
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


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


def _load_runtime_config(args: argparse.Namespace) -> dict:
    """Load config.json with provider-based adjustments and the --model override.

    Shared by startup and the /settings restart, so a provider switch gets the
    same token/context adjustments after a restart as on a fresh start.
    """
    config = _load_and_adjust_config(args.config)
    if args.model:
        config.setdefault("llm", {})["model"] = args.model
    return config


def _reinitialize_agents(config: dict, args: argparse.Namespace, require_adaptive: bool = False) -> tuple:
    """
    Re-create all agents after a settings change.

    Raises if the SearchAgent fails, or - when ``require_adaptive`` is set
    because the adaptive system was running before - if it cannot be
    rebuilt; interactive mode cannot run without it, so the caller then
    keeps the old agents instead of exiting.
    """
    # Reinitialize standard agent
    agent = SearchAgent(
        config=config,
        enable_web=not args.no_web,
        debug=args.debug
    )
    console.print("[green][OK] SearchAgent restarted[/green]")

    # Reinitialize multi-hop agent
    # Same factory as at startup, so hop/threshold settings match
    multihop_agent = _create_multihop_agent(config)

    # Reinitialize Adaptive System
    adaptive_processor = None
    if agent and multihop_agent:
        adaptive_processor = _restart_adaptive_processor(config, agent, multihop_agent)

    if require_adaptive and adaptive_processor is None:
        raise RuntimeError("Adaptive System could not be restarted")

    return agent, multihop_agent, adaptive_processor


def _run_interactive_with_restart(args: argparse.Namespace, agent: SearchAgent,
                                  multihop_agent, adaptive_processor) -> None:
    """Run interactive mode, restarting the agents when requested."""
    while True:
        result = interactive_mode(agent, adaptive_processor, multihop_agent)

        if result != "RESTART":
            # Normal exit
            break

        try:
            console.print("[cyan]Reloading configuration...[/cyan]")
            config = _load_runtime_config(args)
            console.print("[cyan]Reinitializing agents...[/cyan]")
            agent, multihop_agent, adaptive_processor = _reinitialize_agents(
                config, args, require_adaptive=adaptive_processor is not None
            )
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
    config = _load_runtime_config(args)

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
