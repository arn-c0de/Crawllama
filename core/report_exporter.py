"""Report exporter for saving generated OSINT/research reports to file."""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.secure_config import SecureConfig

EXPORT_DIR = Path("data/exports")
REPORT_KEY_PATH = Path(".encryption_key")


def _generate_filepath(fmt: str) -> Path:
    """Return a timestamped export path inside EXPORT_DIR."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    # Reports may contain private OSINT/PII data — keep the dir owner-only.
    _chmod_quietly(EXPORT_DIR, 0o700)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return EXPORT_DIR / f"report-{ts}.{fmt}.enc"


def _chmod_quietly(path: Path, mode: int) -> None:
    """Best-effort permission tightening; ignore platforms that don't support it."""
    try:
        path.chmod(mode)
    except OSError:
        pass


def _strip_rich_markup(text: str) -> str:
    """Remove Rich console markup tags (e.g. [bold], [/cyan]) from text."""
    return re.sub(r"\[/?[^\]]*\]", "", text)


def _write_encrypted_report(path: Path, body: str) -> None:
    """Encrypt a report and create its file with owner-only permissions."""
    config = SecureConfig(encryption_key_path=REPORT_KEY_PATH)
    encrypted_body = config.encrypt_value(body)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as report_file:
        report_file.write(encrypted_body)
    _chmod_quietly(path, 0o600)


def decrypt_report(path: str | Path) -> str:
    """Decrypt and return an exported report without writing plaintext to disk."""
    encrypted_body = Path(path).read_text(encoding="utf-8")
    config = SecureConfig(encryption_key_path=REPORT_KEY_PATH)
    return config.decrypt_value(encrypted_body)


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
    """Export the latest report encrypted at rest with the local Fernet key.

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

    _write_encrypted_report(out_path, body)
    return {"success": True, "path": str(out_path), "format": fmt}
