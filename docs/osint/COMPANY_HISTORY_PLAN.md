# Company History Intelligence — Implementation Plan

**Status:** Approved / not yet implemented
**Target module:** `core/osint/company_history.py`
**Related:** [`COMPANY_INTELLIGENCE.md`](COMPANY_INTELLIGENCE.md)

---

## Context

CrawlLama already has a **Company Intelligence** module (`core/osint/company_intel.py`) that
builds a *present-day* OSINT report for a firm (business signals, leadership, structure, risk)
and enriches the likely official domain via `DomainIntelligence`. It has no **temporal**
dimension: it cannot see previous websites, past leadership, discontinued products, rebrandings,
or old legal/contact info.

This feature adds a **historical** counterpart: retrieve archived snapshots of a company's site
from the Internet Archive (Wayback Machine), diff them across time, and produce a structured,
sourced, confidence-scored **change timeline** — with verified facts (directly observed in a
snapshot) kept separate from inferred changes (interpreted, e.g. "likely rebranding").

**Proposed usage**

```text
company-history:"Example Corp" from:2015 to:2026
```

**Design decisions (confirmed):**
- **Archive source:** Wayback only *now*, behind a small pluggable `ArchiveProvider` interface
  so archive.today / Common Crawl can be added later without touching diff/timeline logic.
- **Inference:** deterministic heuristics produce *verified facts*; an **optional, off-by-default**
  LLM pass labels *inferred changes*. Tests stay fully network-free and it works with no LLM backend.

The design mirrors the existing company-intel feature so it slots into the same routing, caching,
rate-limiting, REST, CLI, test, and docs conventions.

---

## Architecture & reuse

Layering already in the repo (reuse, don't reinvent):

| Concern | Reuse |
| --- | --- |
| HTTP (SSRF-safe, rate-limited, robots, circuit breaker) | `utils/safe_fetch.py` → `SafeFetcher` / `safe_get`, pinned via `allowed_domains={"web.archive.org"}` + `requests_per_second` |
| Caching (TTL + LRU, JSON) | `core/cache.py` → `CacheManager` — cache CDX listings + parsed extractions, **never raw HTML** |
| Safe HTML parsing | `beautifulsoup4` (already a core dep) + `utils/text_cleaner.py` |
| Company/domain helpers | `core/osint/company_intel.py`: `_pick_likely_company_domain`, `_extract_leadership`, `_extract_host`, `_url_matches_domain`, `extract_company_name`, `_extract_inline_operator` |
| Operator parsing | `core/osint/query_parser.py` → `SearchQuery` + `OSINTQueryParser` |
| Routing seam | `core/agent/tools_flow.py` (`check_company_osint_intent` → `handle_company_query`), `core/agent/osint_flow.py` (`handle_company_query`, `_save_company_session`) |
| REST pattern | `app.py` `CompanyOSINTRequest` + `/osint/company` (validators, `sanitize_query`, `asyncio.to_thread`, sanitized errors) |
| Test pattern | `tests/osint/test_company_intel.py` (monkeypatch search/fetch — no live net) |

---

## New files

### 1. `core/osint/archive_provider.py`
- `class ArchiveProvider` (interface): `list_snapshots(url, from_year, to_year) -> list[Snapshot]`,
  `fetch_snapshot(snapshot) -> str | None`.
- `@dataclass Snapshot`: `timestamp` (YYYYMMDDhhmmss), `original_url`, `mimetype`, `statuscode`,
  `digest`, `archive_url` (permalink), `provider` name.
- `class WaybackProvider(ArchiveProvider)`:
  - **CDX listing:** `GET http://web.archive.org/cdx/search/cdx` with
    `output=json`, `fl=timestamp,original,mimetype,statuscode,digest`,
    `filter=statuscode:200`, `filter=mimetype:text/html`, `collapse=timestamp:6`
    (≈one snapshot per year), `from=`/`to=` (YYYY), bounded `limit`.
  - **Snapshot fetch:** `http://web.archive.org/web/<timestamp>id_/<original_url>` — the `id_`
    suffix returns raw archived bytes without Wayback's rewriting/toolbar (cleaner + safer to diff).
  - **Coverage listing (cheap, no snapshot fetch):** `coverage(url) -> ArchiveCoverage` — a single
    lightweight CDX call over the *full* range (no `from`/`to`) returning **which years have
    snapshots and how many**, plus first/last capture. Uses CDX aggregation params so no HTML is
    downloaded: `fl=timestamp`, `collapse=timestamp:4` for the year buckets, and a separate
    `showNumPages`/count pass (or client-side count of the collapsed rows) for per-year totals.
  - Uses a **dedicated `SafeFetcher(allowed_domains={"web.archive.org"}, requests_per_second=…)`**.
  - Bounds: max snapshots per run, max response bytes, per-run wall-clock cap (all config-driven).
  - CDX/JSON parsing is pure + unit-testable (first row is the header).

- `@dataclass ArchiveCoverage`: `domain`, `first_snapshot` (date), `last_snapshot` (date),
  `total_snapshots`, `years: dict[int, int]` (year → snapshot count), `provider`. JSON-serializable.

### 2. `core/osint/company_history.py`
- `class CompanyHistoryIntelligence` (config dict like `CompanyIntelligence`):
  - `is_history_intent(query) -> bool` — true on `company-history:` operator or natural phrases
    ("history of", "historical", "previous website", "rebranding", "über die Jahre", "im laufe der jahre").
  - `is_coverage_intent(query) -> bool` — true on `archive-coverage:` operator or phrases like
    "which years", "welche jahre", "available snapshots", "verfügbare snapshots", "wann archiviert".
  - `list_coverage(company_name, domain=None) -> dict` — resolve the domain, call
    `provider.coverage()`, and return the `ArchiveCoverage` payload. **Discovery step**: run this
    first when the available date range is unknown, then pick a `from:`/`to:` window for the full diff.
  - `format_coverage(coverage) -> str` — compact markdown: first/last capture, total, and a
    per-year table/sparkline of snapshot counts (e.g. `2004 ▏3   2005 ▍12   …`).
  - `analyze(company_name, domain=None, from_year=None, to_year=None, ...) -> dict` — resolve domain
    (reuse company-intel domain pick / memory), list snapshots, fetch+extract, diff, build timeline.
    If `from_year`/`to_year` are omitted, auto-discover the full available range via `coverage()`
    first (then clamp to the configured max snapshot budget).
  - `_extract_snapshot(html, snapshot) -> dict` — BeautifulSoup: title, meta description, visible
    text (scripts/styles stripped), headings, outbound domains, emails/phones (regex), imprint/legal
    block, leadership names (reuse `_extract_leadership`), product/service tokens. Size-capped.
  - `_build_timeline(extractions, current) -> list[TimelineEvent]` — diff consecutive snapshots
    (+ current live page via existing DomainIntelligence/page reader) into events:
    `rebrand | domain-change | leadership | product | contact | legal`. Each event:
    `date, category, description, sources[archive permalinks], confidence, kind: verified|inferred`.
  - `_score_confidence(...)` — factors: statuscode 200, digest actually changed (not identical),
    number of corroborating snapshots, direct-observation vs pattern-match.
  - `_infer_changes(...)` — **optional** LLM pass (guarded by `history.use_llm`, default False),
    reusing `core.llm_client`; produces `kind="inferred"` events only. Off ⇒ heuristic-only.
  - `format_report(data) -> str` — markdown like company-intel, with **explicit** "✅ Verified facts"
    and "≈ Inferred changes" sections, each event showing date, source permalink(s), confidence.
- `@dataclass TimelineEvent` (JSON-serializable via `asdict`).

### 3. `tests/osint/test_company_history.py`
Network-free (monkeypatch provider `list_snapshots`/`fetch_snapshot`):
- intent detection (history + coverage); operator parse (`company-history:"Example Corp" from:2015 to:2026`,
  `archive-coverage:"Example Corp"`);
- CDX JSON → `Snapshot` parsing (incl. header row, bad rows);
- CDX JSON → `ArchiveCoverage` (per-year counts, first/last, empty-domain case);
- HTML → extraction (fixture HTML); two-snapshot diff → expected events;
- confidence scoring + verified/inferred separation; report formatting;
- year clamping (Wayback starts 1996; upper bound = current year).

### 4. `docs/osint/COMPANY_HISTORY.md`
Mirror `docs/osint/COMPANY_INTELLIGENCE.md`: quick-start prompts, integration flow, public API,
operators, config keys, safety notes.

---

## Modified files

### `core/osint/query_parser.py`
- Add fields to `SearchQuery`: `company_history: str | None`, `year_from: int | None`,
  `year_to: int | None`.
- Add operators: `company-history:(?:"([^"]+)"|([^\s]+))`, `archive-coverage:(?:"([^"]+)"|([^\s]+))`,
  `from:(\d{4})`, `to:(\d{4})`. (`from`/`to` map to `year_from`/`year_to`; only meaningful
  alongside a history query.) Add `archive_coverage: str | None` field for the coverage/discovery mode.
- Wire into `parse()` next to the existing `_extract_*_operator` calls.

### `core/agent/tools_flow.py`
- `check_company_history_intent(query)` → `CompanyHistoryIntelligence.is_history_intent(query)`.
- `check_archive_coverage_intent(query)` → `CompanyHistoryIntelligence.is_coverage_intent(query)`.
- In `query_with_tools`, route **coverage intent first** (cheapest, discovery), then history intent,
  then the plain company check — most-specific → least-specific.

### `core/agent/osint_flow.py`
- `handle_company_history_query(query)` — parse operator/inline hints, run analysis, format,
  persist likely domain + a `type: "company_history"` session entry (mirror
  `handle_company_query` / `_save_company_session`). Guard imports with the existing
  `safe_execute` pattern.
- Add the thin `agent._handle_company_history_query` delegator where `_handle_company_osint_query`
  lives (grep `_handle_company_osint_query` in `core/agent/agent.py`).

### `app.py`
- `class CompanyHistoryRequest(BaseModel)`: `company_name`, optional `domain`, `from_year`,
  `to_year`, `region`, `lang` — reuse the `CompanyOSINTRequest` validators; add year validators
  (int, 1996 ≤ y ≤ current year).
- `POST /osint/company/history` (with `Depends(check_rate_limit)`): synthesize a
  `company-history:"…" from:… to:…` query, run via `asyncio.to_thread(agent.query, …)`, return
  `{status, company_name, domain, timeline:[…structured…], report, elapsed_time}`. Sanitized error
  handling identical to `osint_company`.
- `GET /osint/company/history/coverage` (query params `company_name`, optional `domain`): the
  **discovery** endpoint — returns the `ArchiveCoverage` payload
  `{status, domain, first_snapshot, last_snapshot, total_snapshots, years:{…}, report}` so a
  client can see which years exist before requesting the full diff. Cheap (one CDX call, no HTML).

### `main.py`
- History + coverage natural-language queries already flow through `is_osint_query` → agent routing
  once `tools_flow` handles them; add help/usage lines for the `company-history:` and
  `archive-coverage:` operators next to the existing OSINT operator help (show that
  `archive-coverage:"X"` lists which years have snapshots).

### `README.md` / `CHANGELOG.md` / `_version.py`
- Add feature bullet under OSINT features; changelog entry; version bump per repo convention.

---

## Safety (aligns with the repo's recent CodeQL/Bandit hardening)
- **SSRF:** archive fetches restricted to `web.archive.org` via a domain-pinned `SafeFetcher`.
- **Safe HTML:** BeautifulSoup only (no eval/exec), scripts/styles stripped, response byte cap,
  snapshot-count cap, per-run time cap.
- **Input:** reuse `sanitize_query` + regex validators for company/domain/year; years clamped.
- **Politeness:** dedicated rate limiter (default ~1 rps) + `CacheManager` so re-runs don't re-hit IA.
- No secrets / no API key required.

---

## Acceptance criteria mapping

| Issue requirement | Covered by |
| --- | --- |
| Wayback Machine integration | `WaybackProvider` (CDX + snapshot fetch) |
| **Discover available snapshot years for a domain** | `WaybackProvider.coverage()` → `ArchiveCoverage`; `archive-coverage:` operator + `GET /osint/company/history/coverage` |
| Historical snapshot comparison | `_extract_snapshot` + `_build_timeline` diffing |
| Company change timeline | `TimelineEvent[]` (rebrand/domain/leadership/product/contact/legal) |
| Sources, dates, confidence | Each event carries archive permalinks, date, `_score_confidence` |
| Verified vs inferred separation | `kind: verified\|inferred`; explicit report sections |
| Caching, rate limiting, safe HTML | `CacheManager`, dedicated `SafeFetcher`, BeautifulSoup bounds |
| CLI + REST support | `company-history:` operator + `POST /osint/company/history` |
| Tests + documentation | `tests/osint/test_company_history.py`, `docs/osint/COMPANY_HISTORY.md` |

---

## Verification
1. **Unit tests:** `pytest tests/osint/test_company_history.py -q` (all network mocked) — green.
2. **Full OSINT suite regression:** `pytest tests/osint -q`.
3. **Coverage/discovery smoke (manual, optional):** CLI `archive-coverage:"Mozilla"` (or
   `GET /osint/company/history/coverage?company_name=Mozilla`) → confirm it lists first/last capture,
   total, and per-year snapshot counts *without* fetching any HTML.
4. **Live smoke (manual, optional):** CLI `company-history:"Mozilla" from:2005 to:2012` against a
   domain with rich history → confirm timeline renders with dated archive permalinks and a
   verified/inferred split.
5. **REST smoke:** start API (`run_api.sh`), `POST /osint/company/history`
   `{"company_name":"Mozilla","from_year":2005,"to_year":2012}` → structured `timeline` + `report`.
6. **Cache/rate-limit check:** re-run the same query → second run served from cache (log shows
   `Cache hit`), no repeated IA requests.
