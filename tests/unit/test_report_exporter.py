"""Tests for core/report_exporter.py"""
import re
import sys
from pathlib import Path
import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.report_exporter import export_report, _generate_filepath, _strip_rich_markup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_HISTORY = [
    {
        "query": "analyse company acme corp",
        "response": "## Company Intelligence\n\n- **Company:** ACME Corp\n\nSome OSINT findings here.",
    }
]


# ---------------------------------------------------------------------------
# Path / filename generation
# ---------------------------------------------------------------------------


def test_generate_filepath_md(tmp_path, monkeypatch):
    import core.report_exporter as mod
    monkeypatch.setattr(mod, "EXPORT_DIR", tmp_path)
    path = mod._generate_filepath("md")
    assert path.suffix == ".md"
    assert path.parent == tmp_path
    # Filename matches report-YYYYMMDD-HHMMSS.md
    assert re.match(r"report-\d{8}-\d{6}\.md", path.name)


def test_generate_filepath_txt(tmp_path, monkeypatch):
    import core.report_exporter as mod
    monkeypatch.setattr(mod, "EXPORT_DIR", tmp_path)
    path = mod._generate_filepath("txt")
    assert path.suffix == ".txt"
    assert re.match(r"report-\d{8}-\d{6}\.txt", path.name)


def test_generate_filepath_creates_dir(tmp_path, monkeypatch):
    import core.report_exporter as mod
    target = tmp_path / "nested" / "exports"
    monkeypatch.setattr(mod, "EXPORT_DIR", target)
    mod._generate_filepath("md")
    assert target.exists()


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------


def test_export_md_success(tmp_path, monkeypatch):
    import core.report_exporter as mod
    monkeypatch.setattr(mod, "EXPORT_DIR", tmp_path)

    result = export_report(SAMPLE_HISTORY, "md")

    assert result["success"] is True
    assert result["format"] == "md"
    path = Path(result["path"])
    assert path.exists()
    assert path.suffix == ".md"

    content = path.read_text(encoding="utf-8")
    assert "# Report: analyse company acme corp" in content
    assert "ACME Corp" in content
    assert "OSINT sources" in content  # disclaimer


def test_export_md_default_format(tmp_path, monkeypatch):
    """fmt defaults to 'md' when not specified."""
    import core.report_exporter as mod
    monkeypatch.setattr(mod, "EXPORT_DIR", tmp_path)

    result = export_report(SAMPLE_HISTORY)

    assert result["success"] is True
    assert result["format"] == "md"
    assert Path(result["path"]).suffix == ".md"


# ---------------------------------------------------------------------------
# Plain-text export
# ---------------------------------------------------------------------------


def test_export_txt_success(tmp_path, monkeypatch):
    import core.report_exporter as mod
    monkeypatch.setattr(mod, "EXPORT_DIR", tmp_path)

    result = export_report(SAMPLE_HISTORY, "txt")

    assert result["success"] is True
    assert result["format"] == "txt"
    path = Path(result["path"])
    assert path.exists()
    assert path.suffix == ".txt"

    content = path.read_text(encoding="utf-8")
    assert "REPORT: analyse company acme corp" in content
    assert "ACME Corp" in content
    assert "DISCLAIMER" in content


def test_export_txt_strips_rich_markup(tmp_path, monkeypatch):
    import core.report_exporter as mod
    monkeypatch.setattr(mod, "EXPORT_DIR", tmp_path)

    history = [{"query": "test", "response": "[bold]Hello[/bold] [cyan]World[/cyan]"}]
    result = export_report(history, "txt")

    content = Path(result["path"]).read_text(encoding="utf-8")
    assert "[bold]" not in content
    assert "[cyan]" not in content
    assert "Hello" in content
    assert "World" in content


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_export_no_history():
    result = export_report([], "md")
    assert result["success"] is False
    assert "No report available" in result["error"]


def test_export_empty_response():
    history = [{"query": "something", "response": ""}]
    result = export_report(history, "md")
    assert result["success"] is False
    assert "empty" in result["error"]


def test_export_unknown_format():
    result = export_report(SAMPLE_HISTORY, "pdf")
    assert result["success"] is False
    assert "pdf" in result["error"]


def test_export_missing_response_key():
    """History entry without 'response' key returns error."""
    history = [{"query": "test"}]
    result = export_report(history, "md")
    assert result["success"] is False


# ---------------------------------------------------------------------------
# _strip_rich_markup helper
# ---------------------------------------------------------------------------


def test_strip_rich_markup_basic():
    assert _strip_rich_markup("[bold]Hello[/bold]") == "Hello"


def test_strip_rich_markup_nested():
    assert _strip_rich_markup("[bold][cyan]Hi[/cyan][/bold]") == "Hi"


def test_strip_rich_markup_no_markup():
    text = "Plain text without markup."
    assert _strip_rich_markup(text) == text
