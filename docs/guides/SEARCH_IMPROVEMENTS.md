# Search Improvements Guide

This document explains the recent search quality improvements in CrawlLama.

## What Was Improved

### 1. Real Provider Fallback
Search now uses a real provider chain:
- DuckDuckGo
- Brave Search (if API key configured)
- Serper (if API key configured)

If one provider returns no results or fails, the next provider is tried automatically.

### 2. Better Country/Language/Region Targeting
Search now supports inline query preferences:
- `country:<value>`
- `lang:<value>`
- `region:<ddgs-region>`

Examples:
- `latest AI regulation country:us`
- `privacy law updates lang:de`
- `startup funding region:uk-en`

These hints are resolved to an effective search region before requesting results.

### 3. Relevance Re-Ranking
After provider results are collected and safety-filtered, CrawlLama re-ranks them using lightweight relevance scoring:
- Exact phrase match in title/snippet
- Query token overlap (title weighted higher than snippet)
- Token coverage bonus
- Domain trust prior (for example `.gov`, `.edu`, `.org`, Wikipedia)

This improves ordering quality without adding heavy dependencies.

### 4. Configurable Ranking Profiles
You can choose ranking behavior with profiles:
- `balanced`
- `strict_factual`
- `osint`
- `auto` (adaptive)

`auto` selects a profile from query intent:
- OSINT-style operators (`email:`, `site:`, `ip:`, etc.) -> `osint`
- Fact/source-oriented wording (`official`, `statistics`, `source`, `law`, etc.) -> `strict_factual`
- Otherwise -> `balanced`

### 5. Parser Improvements for OSINT Queries
The OSINT parser now supports:
- `country:`
- `lang:`
- `region:`

It also fixes email operator parsing so later operators are no longer swallowed in mixed queries.

## Configuration

`config.json` / `config.json.example`:

```json
{
  "search": {
    "region": "de-de",
    "ranking_profile": "auto"
  },
  "osint": {
    "safesearch": "strict",
    "ranking_profile": "auto"
  }
}
```

Profile options:
- `auto`
- `balanced`
- `strict_factual`
- `osint`

## Inline Overrides in Queries

You can override behavior per query.

Region targeting:
- `country:de`
- `lang:en`
- `region:us-en`

Ranking targeting:
- `profile:strict_factual`
- `ranking:osint`

Example:
- `official inflation report profile:strict_factual country:us`

## Logging and Transparency

Search logs now include resolved runtime preferences, for example:
- effective ranking profile
- effective region

This makes it easier to debug why certain results/ranking were used.

## Provider Keys (Optional)

To enable fallback providers:
- `BRAVE_API_KEY`
- `SERPER_API_KEY`

Without keys, DuckDuckGo remains the primary source and fallback will skip unavailable providers.

## Relevant Files

- `tools/web_search.py`
- `core/agent/tools_flow.py`
- `core/agent/osint_flow.py`
- `core/osint/query_parser.py`
- `tools/tool_registry.py`
- `config.json.example`
