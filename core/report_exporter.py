"""Report exporter for saving generated OSINT/research reports to file."""
import re
from datetime import datetime
from pathlib import Path
from typing import Any

EXPORT_DIR = Path("data/exports")


def _generate_filepath(fmt: str) -> Path:
    """Return a timestamped export path inside EXPORT_DIR."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return EXPORT_DIR / f"report-{ts}.{fmt}"


def _strip_rich_markup(text: str) -> str:
    """Remove Rich console markup tags (e.g. [bold], [/cyan]) from text."""
    return re.sub(r"\[/?[^\]]*\]", "", text)


def _build_markdown(query: str, content: str, timestamp: str) -> str:
    return (
        f"# Report: {query}\n\n"
        f"*Generated: {timestamp}*\n\n"
        "---\n\n"
        f"{content}\n\n"
        "---\n\n"
        "*This report is based on publicly available OSINT sources. "
        "All information was collected from open internet sources at the time of research.*\n"
    )


def _build_plaintext(query: str, content: str, timestamp: str) -> str:
    sep = "=" * 60
    clean = _strip_rich_markup(content)
    return (
        f"{sep}\n"
        f"REPORT: {query}\n"
        f"Generated: {timestamp}\n"
        f"{sep}\n\n"
        f"{clean}\n\n"
        f"{sep}\n"
        "DISCLAIMER: This report is based on publicly available OSINT sources.\n"
        "All information was collected from open internet sources at the time of research.\n"
        f"{sep}\n"
    )


def export_report(
    conversation_history: list[dict[str, Any]],
    fmt: str = "md",
) -> dict[str, Any]:
    """Export the latest report from conversation history to a file.

    Args:
        conversation_history: List of {"query": ..., "response": ...} dicts
            (agent.session.conversation_history).
        fmt: Output format — "md" for Markdown, "txt" for plain text.

    Returns:
        On success: {"success": True, "path": str, "format": str}
        On failure: {"success": False, "error": str}
    """
    if not conversation_history:
        return {"success": False, "error": "No report available. Run a query first."}

    last = conversation_history[-1]
    query = last.get("query", "Untitled report")
    content = last.get("response", "")

    if not content:
        return {"success": False, "error": "Last response is empty — nothing to export."}

    if fmt not in ("md", "txt"):
        return {"success": False, "error": f"Unknown format '{fmt}'. Use 'md' or 'txt'."}

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out_path = _generate_filepath(fmt)

    body = _build_markdown(query, content, timestamp) if fmt == "md" else _build_plaintext(query, content, timestamp)

    out_path.write_text(body, encoding="utf-8")
    return {"success": True, "path": str(out_path), "format": fmt}
