# Export Report Guide

Save any generated OSINT or research report from the CLI to a local file for archiving, sharing, or downstream use.

### Version
**1.0.0** – Introduced in 1.4.9 (Issue #39)

---

## Overview

After CrawlLama generates a report in the terminal, the output exists only in the current session.
The `export-report` command writes the **latest generated report** to a file under `data/exports/` in either **Markdown** or **plain text** format.

---

## Commands

| Command | Output format | File extension |
|---|---|---|
| `export-report md` | Markdown (headings, lists, links) | `.md` |
| `export-report txt` | Plain text (section separators) | `.txt` |

Both commands default to Markdown when no format argument is given.

---

## Usage

### 1. Run a research query

```
> analyse company acme corp
```

CrawlLama returns the full report in the terminal.

### 2. Export the report

```
> export-report md
[OK] Report exported (MD):
  • Saved: data/exports/report-20260305-143021.md
```

```
> export-report txt
[OK] Report exported (TXT):
  • Saved: data/exports/report-20260305-143025.txt
```

---

## Output Path

Files are always written to:

```
data/exports/report-YYYYMMDD-HHMMSS.{md,txt}
```

The directory is created automatically if it does not exist.

---

## File Format

### Markdown (`.md`)

```markdown
# Report: analyse company acme corp

*Generated: 2026-03-05 14:30:21*

---

## Company Intelligence

- **Company:** ACME Corp
- **Source Count:** 7
...

---

*This report is based on publicly available OSINT sources.
All information was collected from open internet sources at the time of research.*
```

### Plain Text (`.txt`)

```
============================================================
REPORT: analyse company acme corp
Generated: 2026-03-05 14:30:25
============================================================

Company Intelligence

Company: ACME Corp
Source Count: 7
...

============================================================
DISCLAIMER: This report is based on publicly available OSINT sources.
All information was collected from open internet sources at the time of research.
============================================================
```

> **Note:** The plain text exporter automatically strips Rich console markup tags (e.g. `[bold]`, `[cyan]`) from the output so the file is clean readable text.

---

## Error Handling

| Situation | Message |
|---|---|
| No query has been run yet | `Export failed: No report available. Run a query first.` |
| Last response was empty | `Export failed: Last response is empty — nothing to export.` |
| Unknown format passed | `Export failed: Unknown format 'xyz'. Use 'md' or 'txt'.` |

---

## Security

- Only content already generated in the current session is exported — no internal config, prompts, or API keys are included.
- Source URLs from OSINT research are preserved as-is for traceability.
- The disclaimer that output is based on public OSINT sources is appended to every export.

---

## Implementation

| Component | Location |
|---|---|
| Export logic | `core/report_exporter.py` |
| CLI command handler | `main.py` — `interactive_mode()` |
| Unit tests | `tests/unit/test_report_exporter.py` |

### Public API (`core/report_exporter.py`)

```python
from core.report_exporter import export_report

result = export_report(
    conversation_history,  # agent.session.conversation_history
    fmt="md",              # "md" or "txt"
)

if result["success"]:
    print(result["path"])   # e.g. "data/exports/report-20260305-143021.md"
    print(result["format"]) # "md"
else:
    print(result["error"])
```

---

## Related

- [`export`](../guides/CLI_PROVIDER_SELECTION.md) — export the memory store (different from reports)
- [OSINT Usage](../osint/OSINT_USAGE.md) — how reports are generated
- [Company Intelligence](../osint/COMPANY_INTELLIGENCE.md) — company OSINT report structure
