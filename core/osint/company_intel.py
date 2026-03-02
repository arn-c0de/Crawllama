"""Company intelligence module for firm-level OSINT workflows."""

from __future__ import annotations

import re
from typing import Dict, List, Set
from urllib.parse import urlparse

from tools.web_search import search_with_fallback, resolve_region_from_preferences
from core.osint.domain_intel import DomainIntelligence


CORPORATE_SUFFIXES = {
    "ag", "gmbh", "mbh", "se", "kg", "kgaa", "ug", "gbr",
    "inc", "llc", "ltd", "plc", "corp", "co", "company", "corporation",
    "s.a.", "sa", "n.v.", "nv", "oy", "ab", "spa", "srl"
}

COMPANY_KEYWORDS = {
    "firma", "unternehmen", "company", "corporate", "konzern",
    "vorstand", "management", "board", "ownership", "eigentum",
    "subsidiary", "tochter", "holding", "struktur", "structure",
}

COMPANY_ACTION_PATTERNS = (
    r"^(?:analysiere|analyse|prüfe|recherchiere|suche|finde|investigate|analyze|research)\s+(?:die\s+|das\s+|den\s+|the\s+)?(?:firma|unternehmen|company)\b",
    r"^(?:firma|unternehmen|company)\s+",
)

GENERIC_PLATFORM_DOMAINS = {
    "linkedin.com", "wikipedia.org", "crunchbase.com", "reuters.com", "bloomberg.com",
    "x.com", "twitter.com", "instagram.com", "facebook.com", "youtube.com",
    "reddit.com", "github.com", "glassdoor.com", "indeed.com", "youtube.com",
}

RISK_TERMS = {
    "lawsuit", "litigation", "fine", "penalty", "sanction", "investigation",
    "breach", "data leak", "fraud", "insolvency", "bankruptcy", "compliance",
    "whistleblower", "kartell", "geldstrafe", "sanktion", "ermittlung"
}

# Business directory and aggregator sites – not company official domains.
GENERIC_BUSINESS_DIRECTORIES = {
    "implisense.com", "kompany.de", "meinestadt.de", "northdata.de",
    "opencorporates.com", "firmenwissen.de", "creditreform.de", "dnb.com",
    "zoominfo.com", "gelbeseiten.de", "handelsregister.de", "unternehmensregister.de",
    "ebra.de", "moneyhouse.de", "bizapedia.com", "gleif.org",
}


class CompanyIntelligence:
    """Aggregates company-level OSINT from existing search and intel modules."""

    def __init__(self, config: Dict | None = None):
        self.config = config or {}
        self.domain_intelligence = DomainIntelligence()

    @staticmethod
    def is_company_intent(query: str) -> bool:
        query = (query or "").strip()
        if not query:
            return False

        lower = query.lower()
        # Strong explicit company-action patterns.
        if any(re.search(pattern, lower) for pattern in COMPANY_ACTION_PATTERNS):
            return True

        # Strong legal/corporate suffix signals.
        if re.search(r"\b(" + "|".join(re.escape(s) for s in CORPORATE_SUFFIXES) + r")\b", lower):
            return True

        # Board/ownership structure words with an explicit company mention.
        has_company_word = any(word in lower for word in {"company", "firma", "unternehmen"})
        has_structure_word = any(word in lower for word in {"vorstand", "board", "ownership", "holding", "subsidiary", "struktur"})
        if has_company_word and has_structure_word:
            return True

        return False

    @staticmethod
    def extract_company_name(query: str) -> str:
        text = (query or "").strip().strip('"').strip("'")
        if not text:
            return ""

        text = re.sub(
            r"^(?:analysiere|analyse|prüfe|recherchiere|suche|finde|investigate|analyze|research)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"^(?:die|das|den|the)\s+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(?:firma|unternehmen|company)\s*:?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:country|region|lang):[^\s]+", "", text, flags=re.IGNORECASE)

        split_pattern = (
            r"\b(vorstand|management|board|ownership|eigentum|struktur|structure|"
            r"subsidiaries|tochter|risiken|risks|compliance|daten|details|info)\b"
        )
        parts = re.split(split_pattern, text, maxsplit=1, flags=re.IGNORECASE)
        company_name = parts[0].strip(" ,.:;")

        return company_name

    def analyze_company(self, query: str) -> Dict:
        company_name = self.extract_company_name(query)
        if not company_name:
            return {"error": "No company name could be extracted from query."}

        osint_config = self.config.get("osint", {})
        search_config = self.config.get("search", {})

        max_results = min(max(5, osint_config.get("context_max_results", 6)), 10)
        default_region = search_config.get("region", "de-de")
        region = resolve_region_from_preferences(
            default_region=default_region,
            region=self._extract_inline_operator(query, "region"),
            country=self._extract_inline_operator(query, "country"),
            lang=self._extract_inline_operator(query, "lang"),
        )
        safesearch = osint_config.get("safesearch", "strict")
        ranking_profile = osint_config.get(
            "ranking_profile",
            search_config.get("ranking_profile", "osint"),
        )
        safe_company_name = self._escape_search_term(company_name)

        discovery_queries = {
            "profile": f'"{safe_company_name}" official website company profile',
            "leadership": f'"{safe_company_name}" CEO OR CFO OR Vorstand OR Geschäftsführung',
            "structure": f'"{safe_company_name}" subsidiaries OR holding OR Tochtergesellschaften',
            "risk": f'"{safe_company_name}" lawsuit OR fine OR sanction OR compliance',
        }

        categorized_sources: Dict[str, List[Dict]] = {}
        all_sources: List[Dict] = []
        seen_urls: Set[str] = set()

        for category, search_query in discovery_queries.items():
            results = search_with_fallback(
                search_query,
                max_results=max_results,
                region=region,
                safesearch=safesearch,
                ranking_profile=ranking_profile,
            ) or []

            category_results = []
            for item in results:
                url = item.get("url", "").strip()
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                source = {
                    "category": category,
                    "title": item.get("title", "No title"),
                    "url": url,
                    "snippet": item.get("snippet", ""),
                }
                category_results.append(source)
                all_sources.append(source)
            categorized_sources[category] = category_results

        domains = self._extract_domains([s["url"] for s in all_sources])
        likely_domain = self._pick_likely_company_domain(company_name, domains)
        domain_intel = self.domain_intelligence.analyze_domain(likely_domain) if likely_domain else {}

        leadership = self._extract_leadership(all_sources, company_name)
        risk_signals = self._extract_risk_signals(all_sources, company_name)
        structure_signals = self._extract_structure_signals(all_sources, company_name)

        return {
            "query": query,
            "company_name": company_name,
            "official_domain": likely_domain,
            "domains": domains,
            "leadership_signals": leadership,
            "structure_signals": structure_signals,
            "risk_signals": risk_signals,
            "sources_by_category": categorized_sources,
            "source_count": len(all_sources),
            "domain_intelligence": domain_intel,
        }

    def format_report(self, data: Dict) -> str:
        if data.get("error"):
            return f"⚠️ Company intelligence failed: {data['error']}"

        lines = [
            "═══ Company Intelligence ═══",
            "",
            f"**Company:** {data.get('company_name', 'Unknown')}",
            f"**Source Count:** {data.get('source_count', 0)}",
        ]

        if data.get("official_domain"):
            lines.append(f"**Likely Official Domain:** {data['official_domain']}")

        leadership = data.get("leadership_signals", [])
        if leadership:
            lines.append("\n**Leadership Signals:**")
            for entry in leadership[:6]:
                lines.append(f"  • {entry}")

        structures = data.get("structure_signals", [])
        if structures:
            lines.append("\n**Structure Signals:**")
            for entry in structures[:6]:
                lines.append(f"  • {entry}")

        risk_signals = data.get("risk_signals", [])
        if risk_signals:
            lines.append("\n**Risk Signals:**")
            for entry in risk_signals[:6]:
                lines.append(f"  • {entry}")

        profile_sources = data.get("sources_by_category", {}).get("profile", [])
        if profile_sources:
            lines.append("\n**Top Sources:**")
            for idx, src in enumerate(profile_sources[:5], 1):
                lines.append(f"  [{idx}] {src.get('title', 'No title')}")
                lines.append(f"      {src.get('url', '')}")

        return "\n".join(lines)

    @staticmethod
    def _company_name_parts(company_name: str) -> List[str]:
        """Return significant words from the company name for text relevance checks."""
        lower = company_name.lower()
        for suffix in CORPORATE_SUFFIXES:
            lower = re.sub(rf"(?<!\w){re.escape(suffix)}(?!\w)\.?", "", lower)
        parts = [w.strip(".,&;") for w in lower.split() if len(w.strip(".,&;")) >= 3]
        return parts or [company_name.lower()[:30]]

    @staticmethod
    def _text_contains_company(text: str, name_parts: List[str]) -> bool:
        lower_text = text.lower()
        return any(part in lower_text for part in name_parts)

    def _extract_domains(self, urls: List[str]) -> List[str]:
        domains: Set[str] = set()
        for url in urls:
            host = urlparse(url).netloc.lower().strip()
            host = host.replace("www.", "")
            if host:
                domains.add(host)
        return sorted(domains)

    def _pick_likely_company_domain(self, company_name: str, domains: List[str]) -> str:
        if not domains:
            return ""

        normalized_company = re.sub(r"[^a-z0-9]", "", company_name.lower())
        best_domain = ""
        best_score = -1

        all_generic = GENERIC_PLATFORM_DOMAINS | GENERIC_BUSINESS_DIRECTORIES
        for domain in domains:
            base = domain.split(".")[0]
            score = 0
            if any(domain.endswith(d) for d in all_generic):
                score -= 2
            if normalized_company and normalized_company in re.sub(r"[^a-z0-9]", "", base):
                score += 4
            if len(base) >= 4:
                score += 1
            if score > best_score:
                best_domain = domain
                best_score = score

        # Only return a domain when there's a confident match (positive score).
        return best_domain if best_score > 0 else ""

    def _extract_leadership(self, sources: List[Dict], company_name: str = "") -> List[str]:
        name_parts = self._company_name_parts(company_name) if company_name else []
        pattern = re.compile(
            r"\b(CEO|CFO|CTO|COO|Chair(?:man|woman)?|Vorstand|Geschäftsführer(?:in)?)\b",
            re.IGNORECASE,
        )
        matches: List[str] = []
        for source in sources:
            text = f"{source.get('title', '')} {source.get('snippet', '')}"
            if not pattern.search(text):
                continue
            if name_parts and not self._text_contains_company(text, name_parts):
                continue
            matches.append(text[:160].strip())
        return self._deduplicate_preserve_order(matches)

    def _extract_structure_signals(self, sources: List[Dict], company_name: str = "") -> List[str]:
        terms = ("subsidiary", "holding", "group", "tochter", "beteiligung", "ownership")
        name_parts = self._company_name_parts(company_name) if company_name else []
        signals = []
        for source in sources:
            text = f"{source.get('title', '')} {source.get('snippet', '')}"
            lowered = text.lower()
            if not any(term in lowered for term in terms):
                continue
            if name_parts and not self._text_contains_company(text, name_parts):
                continue
            signals.append(text[:160].strip())
        return self._deduplicate_preserve_order(signals)

    def _extract_risk_signals(self, sources: List[Dict], company_name: str = "") -> List[str]:
        name_parts = self._company_name_parts(company_name) if company_name else []
        signals = []
        for source in sources:
            text = f"{source.get('title', '')} {source.get('snippet', '')}"
            lowered = text.lower()
            if not any(term in lowered for term in RISK_TERMS):
                continue
            if name_parts and not self._text_contains_company(text, name_parts):
                continue
            signals.append(text[:160].strip())
        return self._deduplicate_preserve_order(signals)

    def _deduplicate_preserve_order(self, values: List[str]) -> List[str]:
        seen = set()
        deduped = []
        for value in values:
            normalized = value.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(value)
        return deduped

    def _extract_inline_operator(self, query: str, operator: str) -> str:
        match = re.search(rf"(?:^|\s){re.escape(operator)}:([^\s]+)", query, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    def _escape_search_term(self, value: str) -> str:
        return re.sub(r'["`]+', " ", value).strip()
