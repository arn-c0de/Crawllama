# Company Intelligence Module - Developer Documentation

**Module:** `core/osint/company_intel.py`  
**Last Updated:** 2026-02-27

---

## LLM Agent Commands (Quick Start)

Use these prompts directly in the agent:

```text
Analyze company Siemens AG
analysiere firma BMW AG vorstand und struktur
Research company Apple Inc ownership and risks
Investigate company NVIDIA Corporation country:US lang:en
```

Notes:
- No explicit OSINT operator is required for company mode.
- Optional inline hints supported: `country:`, `region:`, `lang:`.

---

## Overview

The Company Intelligence module builds a company-focused OSINT report from plain-language queries (without requiring explicit operators like `domain:` or `site:`).

It performs five category searches, deduplicates sources, extracts key signals (business, leadership, structure, risk), and enriches the likely company domain through `DomainIntelligence`.

### Main Use Case

Use this module when a query is clearly company-centric, for example:
- `Analyze company Siemens AG`
- `analysiere firma BMW AG vorstand und struktur`
- `Company Apple Inc ownership`

---

## Integration Flow

The module is integrated into the agent flow as follows:

1. `ToolsFlow.check_company_osint_intent(query)` calls `CompanyIntelligence.is_company_intent(query)`.
2. If intent is detected and no explicit OSINT operators are present, `OSINTFlow.handle_company_query(query)` is used.
3. `CompanyIntelligence.analyze_company(query)` builds the structured intelligence payload.
4. `CompanyIntelligence.format_report(data)` renders a human-readable report.
5. The likely official domain is persisted in memory for follow-up queries.

Relevant files:
- `core/agent/tools_flow.py`
- `core/agent/osint_flow.py`
- `core/osint/company_intel.py`

---

## Public API

### `CompanyIntelligence(config: Dict | None = None)`

Initializes the module with optional application config.

Expected config keys:
- `search.region` (default: `de-de`)
- `search.ranking_profile` (fallback if OSINT profile is missing)
- `osint.context_max_results` (clamped to `5..10`, default effective value: `6`)
- `osint.safesearch` (default: `strict`)
- `osint.ranking_profile` (default: `osint`)

### `is_company_intent(query: str) -> bool`

Detects whether a query likely targets company intelligence.

Current heuristics:
- Action patterns in German/English (e.g. `analyze company ...`, `analysiere firma ...`)
- Corporate suffixes (`AG`, `GmbH`, `Inc`, `LLC`, ...)
- Combined company + structure keywords (`company` + `board/ownership/holding/...`)

### `extract_company_name(query: str) -> str`

Extracts the company name from natural language by stripping:
- leading action verbs
- articles (`the`, `die`, `das`, `den`)
- prefixes (`company`, `firma`, `unternehmen`)
- inline operators (`country:`, `region:`, `lang:`)
- trailing signal terms (`board`, `ownership`, `struktur`, `risks`, ...)

Returns an empty string if no usable name remains.

### `analyze_company(query: str) -> Dict`

Builds structured intelligence from search and domain analysis.

Processing steps:
1. Extract company name
2. Resolve search region from inline operators and defaults
3. Run category queries (`leadership`, `structure`, `risk`, `profile`, `business`)
4. Deduplicate URLs across categories
5. Extract domains and pick likely official domain
6. Run domain enrichment via `DomainIntelligence`
7. Extract signal snippets for business, leadership, structure, and risk

Returns a dictionary payload (see Output Schema).

### `format_report(data: Dict) -> str`

Formats analysis output as a readable report with:
- company name
- source count
- likely official domain
- top business/leadership/structure/risk signals
- top sources

If analysis contains an error, returns a warning string.

---

## Discovery Queries

The module generates five fixed discovery queries using the extracted company name:

- `"<company>" CEO OR CFO OR Vorstand OR Geschäftsführer executive team`
- `"<company>" subsidiaries OR holding OR Tochtergesellschaften`
- `"<company>" lawsuit OR fine OR sanction OR compliance`
- `"<company>" about us products services what we do`
- `"<company>" Geschäftsfeld products services solutions was macht`

Each query is executed through `search_with_fallback(...)`.

---

## Output Schema

`analyze_company()` returns this structure:

```json
{
  "query": "original user query",
  "company_name": "Siemens AG",
  "official_domain": "siemens.com",
  "domains": ["reuters.com", "siemens.com"],
  "business_signals": ["..."],
  "leadership_signals": ["..."],
  "structure_signals": ["..."],
  "risk_signals": ["..."],
  "sources_by_category": {
    "leadership": [],
    "structure": [],
    "risk": [],
    "profile": [{ "category": "profile", "title": "...", "url": "...", "snippet": "..." }],
    "business": []
  },
  "source_count": 4,
  "domain_intelligence": {}
}
```

Error case:

```json
{ "error": "No company name could be extracted from query." }
```

---

## Domain Selection Logic

Candidate domains are extracted from all result URLs and scored:

- `-2` if domain matches known generic platforms or business directories (`linkedin.com`, `wikipedia.org`, `reuters.com`, etc.)
- `+4` if normalized company name matches normalized domain base
- `+1` if domain base length is at least 4
- `+1` if the TLD is a common official one (`com`, `de`, `net`, `org`, `eu`, `io`)

Best-scoring domain is selected as `official_domain` (only when its score is positive; otherwise no domain is returned).

---

## Signal Extraction

Signals are extracted from combined `title + snippet` text and deduplicated case-insensitively.

- Leadership: `CEO`, `CFO`, `CTO`, `COO`, `Chairman/Chairwoman`, `Vorstand`, `Geschäftsführer(in)`
- Structure: `subsidiary`, `holding`, `group`, `tochter`, `beteiligung`, `ownership`
- Risk: lawsuit/compliance/sanction/fraud/insolvency and German equivalents (`kartell`, `geldstrafe`, `sanktion`, `ermittlung`, ...)

---

## Example Usage

```python
from core.osint.company_intel import CompanyIntelligence

intel = CompanyIntelligence(
    config={
        "search": {"region": "de-de", "ranking_profile": "osint"},
        "osint": {"context_max_results": 6, "safesearch": "strict"}
    }
)

analysis = intel.analyze_company("Analyze company Siemens AG board and structure")
report = intel.format_report(analysis)

print(analysis["official_domain"])
print(report)
```

---

## Testing

Current tests are in:
- `tests/osint/test_company_intel.py`

Run only this test file:

```bash
pytest tests/osint/test_company_intel.py -q
```

Covered behaviors:
- intent detection
- company name extraction
- mocked end-to-end analysis flow
- report formatting

---

## Limitations

- Uses keyword heuristics (not full NER), so unusual company names can be misdetected.
- Signal extraction is snippet-based and may include noisy context.
- Domain selection is heuristic and can be wrong for very generic names.
- Search quality depends on provider availability and ranking profile.

---

## Security and Compliance Notes

- Company intelligence executes inside the OSINT compliance flow.
- Queries are subject to terms acceptance and policy checks.
- Output should be treated as investigative leads, not legal conclusions.
