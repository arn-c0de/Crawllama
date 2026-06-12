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

# Financial news / market data sites – useful as sources but should NOT
# be used to derive leadership names (they publish news about executives,
# not verified org-chart data).
FINANCIAL_NEWS_DOMAINS = {
    "marketscreener.com", "finanznachrichten.de", "handelsblatt.com",
    "boerse.de", "boerse-online.de", "finanzen.net", "wallstreet-online.de",
    "aktiencheck.de", "4-traders.com", "boersennews.de", "comdirect.de",
    "onvista.de", "seeking-alpha.com", "seekingalpha.com", "fool.com",
    "motleyfool.com", "nasdaq.com", "marketwatch.com", "finance.yahoo.com",
    "investing.com", "thestreet.com", "benzinga.com", "zacks.com",
}

RISK_TERMS = {
    "lawsuit", "litigation", "fine", "penalty", "sanction", "investigation",
    "breach", "data leak", "fraud", "insolvency", "bankruptcy", "compliance",
    "whistleblower", "kartell", "geldstrafe", "sanktion", "ermittlung"
}
LEADERSHIP_TERMS = {
    "ceo", "cfo", "cto", "coo", "chairman", "chairwoman", "vorstand",
    "geschäftsführer", "geschäftsführerin", "management", "executive",
}
STRUCTURE_TERMS = {
    "subsidiary", "subsidiaries", "holding", "group", "tochter",
    "tochtergesellschaft", "tochtergesellschaften", "beteiligung", "ownership",
}

# Business directory and aggregator sites – not company official domains.
GENERIC_BUSINESS_DIRECTORIES = {
    "implisense.com", "kompany.de", "meinestadt.de", "northdata.de",
    "opencorporates.com", "firmenwissen.de", "creditreform.de", "dnb.com",
    "zoominfo.com", "gelbeseiten.de", "handelsregister.de", "unternehmensregister.de",
    "ebra.de", "moneyhouse.de", "bizapedia.com", "gleif.org",
    "creditsafe.com", "automa.net", "electronicspecifier.com",
    "sur.ly", "redirect.ly",
}

# Generic words that should not count as company identifiers.
_GENERIC_NAME_WORDS = {
    "system", "systems", "group", "holding", "services", "solutions",
    "global", "international", "management", "digital", "tech", "technologies",
}

# Categories to retry via the likely official domain when the initial
# specialized searches return no results for them.
DOMAIN_FALLBACK_CATEGORIES = ("business", "leadership", "structure", "risk")


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
        # Strip German/English prepositions left after action verbs (e.g. "suche nach X").
        text = re.sub(r"^(?:nach|über|zu|für|von|über|an|bei|about|for|on)\s+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^(?:die|das|den|der|dem|the)\s+", "", text, flags=re.IGNORECASE)
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

        search_params = self._build_search_params(query)
        name_parts = self._company_name_parts(company_name)

        categorized_sources, all_sources = self._run_discovery_searches(
            company_name, name_parts, search_params
        )

        domains = self._extract_domains(all_sources)
        likely_domain = self._pick_likely_company_domain(company_name, domains)

        if likely_domain:
            self._run_domain_fallback_searches(
                company_name, name_parts, likely_domain,
                categorized_sources, all_sources, search_params,
            )

        domain_intel = self.domain_intelligence.analyze_domain(likely_domain) if likely_domain else {}

        return {
            "query": query,
            "company_name": company_name,
            "official_domain": likely_domain,
            "domains": domains,
            "business_signals": self._extract_business_signals(all_sources, company_name),
            "leadership_signals": self._extract_leadership(all_sources, company_name),
            "structure_signals": self._extract_structure_signals(all_sources, company_name),
            "risk_signals": self._extract_risk_signals(all_sources, company_name),
            "sources_by_category": categorized_sources,
            "source_count": len({src.get("url", "") for src in all_sources if src.get("url", "")}),
            "domain_intelligence": domain_intel,
        }

    def _build_search_params(self, query: str) -> Dict:
        """Resolve search configuration (region, safesearch, etc.) for one analysis run."""
        osint_config = self.config.get("osint", {})
        search_config = self.config.get("search", {})
        return {
            "max_results": min(max(5, osint_config.get("context_max_results", 6)), 10),
            "region": resolve_region_from_preferences(
                default_region=search_config.get("region", "de-de"),
                region=self._extract_inline_operator(query, "region"),
                country=self._extract_inline_operator(query, "country"),
                lang=self._extract_inline_operator(query, "lang"),
            ),
            "safesearch": osint_config.get("safesearch", "strict"),
            "ranking_profile": osint_config.get(
                "ranking_profile",
                search_config.get("ranking_profile", "osint"),
            ),
        }

    def _search(self, search_query: str, search_params: Dict) -> List[Dict]:
        return search_with_fallback(
            search_query,
            max_results=search_params["max_results"],
            region=search_params["region"],
            safesearch=search_params["safesearch"],
            ranking_profile=search_params["ranking_profile"],
        ) or []

    def _run_discovery_searches(self, company_name, name_parts, search_params):
        """Run the per-category discovery searches and collect filtered sources."""
        safe_company_name = self._escape_search_term(company_name)
        # Query specialized categories first so category labels remain informative
        # even when result URLs overlap across categories.
        discovery_queries = {
            "leadership": f'"{safe_company_name}" CEO OR CFO OR Vorstand OR Geschäftsführer executive team',
            "structure": f'"{safe_company_name}" subsidiaries OR holding OR Tochtergesellschaften',
            "risk": f'"{safe_company_name}" lawsuit OR fine OR sanction OR compliance',
            "profile": f'"{safe_company_name}" about us products services what we do',
            "business": f'"{safe_company_name}" Geschäftsfeld products services solutions was macht',
        }

        categorized_sources: Dict[str, List[Dict]] = {}
        all_sources: List[Dict] = []

        for category, search_query in discovery_queries.items():
            results = self._search(search_query, search_params)
            category_results = []
            seen_urls_in_category: Set[str] = set()
            for item in results:
                source = self._build_relevant_source(category, item, name_parts, seen_urls_in_category)
                if source is None:
                    continue
                category_results.append(source)
                all_sources.append(source)
            categorized_sources[category] = category_results

        return categorized_sources, all_sources

    def _build_relevant_source(self, category, item, name_parts, seen_urls):
        """Validate one search result and return a source dict, or None to skip it."""
        url = item.get("url", "").strip()
        if not url or url in seen_urls:
            return None
        title = item.get("title", "No title")
        snippet = item.get("snippet", "")
        # Drop results that have no relation to the target company.
        combined = f"{title} {snippet} {url}"
        if name_parts and not self._text_contains_company(combined, name_parts):
            return None
        if category != "profile" and self._is_low_value_source(url):
            return None
        if not self._is_category_relevant(category, combined):
            return None
        seen_urls.add(url)
        return {"category": category, "title": title, "url": url, "snippet": snippet}

    def _run_domain_fallback_searches(
        self, company_name, name_parts, likely_domain,
        categorized_sources, all_sources, search_params,
    ) -> None:
        """For empty categories, retry searches restricted to the likely official domain."""
        safe_company_name = self._escape_search_term(company_name)
        for category in DOMAIN_FALLBACK_CATEGORIES:
            if categorized_sources.get(category):
                continue
            fallback_query = self._build_domain_fallback_query(category, likely_domain, safe_company_name)
            fallback_results = self._search(fallback_query, search_params)
            seen_urls_in_category = {src.get("url", "") for src in categorized_sources.get(category, [])}
            for item in fallback_results:
                source = self._build_domain_fallback_source(
                    category, item, name_parts, likely_domain, seen_urls_in_category
                )
                if source is None:
                    continue
                categorized_sources.setdefault(category, []).append(source)
                all_sources.append(source)
                seen_urls_in_category.add(source["url"])

    def _build_domain_fallback_source(self, category, item, name_parts, likely_domain, seen_urls):
        """Validate a fallback result (must match the official domain), or None to skip it."""
        url = item.get("url", "").strip()
        if (
            not url
            or url in seen_urls
            or self._is_low_value_source(url)
            or not self._url_matches_domain(url, likely_domain)
        ):
            return None
        title = item.get("title", "No title")
        snippet = item.get("snippet", "")
        combined = f"{title} {snippet} {url}"
        if name_parts and not self._text_contains_company(combined, name_parts):
            return None
        if not self._is_category_relevant(category, combined):
            return None
        return {"category": category, "title": title, "url": url, "snippet": snippet}

    def format_report(self, data: Dict) -> str:
        if data.get("error"):
            return f"⚠️ Company intelligence failed: {data['error']}"

        lines = [
            "## Company Intelligence",
            "",
            f"- **Company:** {data.get('company_name', 'Unknown')}",
            f"- **Source Count:** {data.get('source_count', 0)}",
        ]

        if data.get("official_domain"):
            lines.append(f"- **Likely Official Domain:** {data['official_domain']}")

        business = data.get("business_signals", [])
        lines.append("\n### Business Description")
        if business:
            for entry in business[:4]:
                lines.append(f"- {entry}")
        else:
            lines.append("- No business description found.")

        leadership = data.get("leadership_signals", [])
        lines.append("\n### Leadership")
        if leadership:
            for entry in leadership[:6]:
                lines.append(f"- {entry}")
        else:
            lines.append("- No leadership information found.")

        structures = data.get("structure_signals", [])
        lines.append("\n### Structure Signals")
        if structures:
            for entry in structures[:6]:
                lines.append(f"- {entry}")
        else:
            lines.append("- No strong structure signals found.")

        risk_signals = data.get("risk_signals", [])
        lines.append("\n### Risk Signals")
        if risk_signals:
            for entry in risk_signals[:6]:
                lines.append(f"- {entry}")
        else:
            lines.append("- No strong risk signals found.")

        # Aggregate sources from all categories, preserving insertion order.
        all_sources: list = []
        seen_urls: set = set()
        for cat in ("profile", "business", "leadership", "structure", "risk"):
            for src in data.get("sources_by_category", {}).get(cat, []):
                url = src.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_sources.append(src)

        if all_sources:
            # Prefer non-directory/non-proxy sources in visible report output.
            preferred_sources = [
                src for src in all_sources if not self._is_low_value_source(src.get("url", ""))
            ]
            low_value_sources = [
                src for src in all_sources if self._is_low_value_source(src.get("url", ""))
            ]
            display_sources = preferred_sources if preferred_sources else low_value_sources[:3]

            lines.append("\n### Sources")
            for idx, src in enumerate(display_sources[:10], 1):
                title = src.get("title", "No title")
                url = src.get("url", "")
                cat = src.get("category", "")
                snippet = src.get("snippet", "").strip()
                lines.append(f"{idx}. **[{cat}] {title}**")
                lines.append(f"   {url}")
                if snippet:
                    lines.append(f"   {snippet[:180]}")

        return "\n".join(lines)

    @staticmethod
    def _company_name_parts(company_name: str) -> List[str]:
        """Return significant words from the company name for text relevance checks."""
        lower = company_name.lower()
        for suffix in CORPORATE_SUFFIXES:
            lower = re.sub(rf"(?<!\w){re.escape(suffix)}(?!\w)\.?", "", lower)
        parts = [
            w.strip(".,&;") for w in lower.split()
            if len(w.strip(".,&;")) >= 3 and w.strip(".,&;") not in _GENERIC_NAME_WORDS
        ]
        if not parts:
            # Fall back to all words (including generic), at least 3 chars.
            parts = [w.strip(".,&;") for w in lower.split() if len(w.strip(".,&;")) >= 3]
        return parts or [company_name.lower()[:30]]

    @staticmethod
    def _text_contains_company(text: str, name_parts: List[str]) -> bool:
        lower_text = text.lower()
        return any(part in lower_text for part in name_parts)

    # Pattern to find an embedded domain in a URL path (e.g. sur.ly/i/examplecorp.de/).
    _EMBEDDED_DOMAIN_RE = re.compile(
        r'(?:/|=)([a-z0-9][a-z0-9-]{1,62}\.[a-z]{2,6})(?:/|$|#|\?|&)', re.IGNORECASE
    )
    # Pattern to detect a domain at the start of a page title (e.g. "examplecorp.de - ...").
    _TITLE_DOMAIN_RE = re.compile(
        r'^([a-z0-9][a-z0-9.-]{1,62}\.[a-z]{2,6})\s*[-–|]', re.IGNORECASE
    )

    def _extract_domains(self, sources: List[Dict]) -> List[str]:
        """Extract candidate domains from source URLs and titles."""
        domains: Set[str] = set()
        for src in sources:
            url = src.get("url", "")
            title = src.get("title", "")

            parsed = urlparse(url)
            host = self._extract_host(url)
            if host:
                domains.add(host)

            # Extract embedded domain from proxy/redirect URLs (e.g. sur.ly/i/examplecorp.de/).
            path_match = self._EMBEDDED_DOMAIN_RE.search(parsed.path + "?" + parsed.query)
            if path_match:
                domains.add(path_match.group(1).lower())

            # Extract domain from title prefix (e.g. "examplecorp.de - Official Site").
            title_match = self._TITLE_DOMAIN_RE.match(title)
            if title_match:
                domains.add(title_match.group(1).lower())

        return sorted(domains)

    def _pick_likely_company_domain(self, company_name: str, domains: List[str]) -> str:
        if not domains:
            return ""

        normalized_company = re.sub(r"[^a-z0-9]", "", company_name.lower())
        best_domain = ""
        best_score = -1

        all_generic = GENERIC_PLATFORM_DOMAINS | GENERIC_BUSINESS_DIRECTORIES
        PREFERRED_TLDS = {"com", "de", "net", "org", "eu", "io"}
        for domain in domains:
            parts = domain.split(".")
            base = parts[0]
            tld = parts[-1].lower()
            score = 0
            if any(domain.endswith(d) for d in all_generic):
                score -= 2
            normalized_base = re.sub(r"[^a-z0-9]", "", base)
            if normalized_company and normalized_base and normalized_base in normalized_company:
                score += 4
            if len(base) >= 4:
                score += 1
            # Prefer common official TLDs to break ties (.com > .de > others).
            if tld in PREFERRED_TLDS:
                score += 1
            if score > best_score:
                best_domain = domain
                best_score = score

        # Only return a domain when there's a confident match (positive score).
        return best_domain if best_score > 0 else ""

    def _extract_business_signals(self, sources: List[Dict], company_name: str = "") -> List[str]:
        """Extract what the company does from profile/business category sources."""
        BUSINESS_TERMS = {
            "produces", "provides", "manufactures", "develops", "offers", "specializes",
            "focuses", "delivers", "solutions", "products", "services", "herstellt",
            "bietet", "entwickelt", "spezialisiert", "produziert", "liefert",
        }
        name_parts = self._company_name_parts(company_name) if company_name else []
        signals: List[str] = []
        # Prefer profile/business category sources first
        ordered = sorted(sources, key=lambda s: (0 if s.get("category") in ("profile", "business") else 1))
        for source in ordered:
            if source.get("category") not in ("profile", "business"):
                continue
            text = f"{source.get('title', '')} {source.get('snippet', '')}"
            lowered = text.lower()
            if not any(term in lowered for term in BUSINESS_TERMS):
                continue
            if name_parts and not self._text_contains_company(text, name_parts):
                continue
            signals.append(text[:200].strip())
        return self._deduplicate_preserve_order(signals)

    def _extract_leadership(self, sources: List[Dict], company_name: str = "") -> List[str]:
        name_parts = self._company_name_parts(company_name) if company_name else []
        # Pattern to capture "Name, Title" or "Title Name" snippets
        role_pattern = re.compile(
            r"\b(CEO|CFO|CTO|COO|President|Chair(?:man|woman)?|Vorstand(?:svorsitzende(?:r|n)?)?|Geschäftsführer(?:in)?)\b",
            re.IGNORECASE,
        )
        # Pattern to detect a person name near the role (Firstname Lastname)
        name_near_role = re.compile(r"[A-ZÄÖÜ][a-zäöü]+\s+[A-ZÄÖÜ][a-zäöü]+")
        matches: List[str] = []
        for source in sources:
            url = source.get("url", "")
            # Skip financial/market news sites — they report about executives, not org-chart data
            host = self._extract_host(url)
            if self._host_in_set(host, FINANCIAL_NEWS_DOMAINS):
                continue
            text = f"{source.get('title', '')} {source.get('snippet', '')}"
            if not role_pattern.search(text):
                continue
            if name_parts and not self._text_contains_company(text, name_parts):
                continue
            # Prefer snippets that also contain a person name
            has_name = bool(name_near_role.search(text))
            matches.append((0 if has_name else 1, text[:180].strip()))
        # Sort: entries with actual names first
        matches.sort(key=lambda x: x[0])
        return self._deduplicate_preserve_order([m[1] for m in matches])

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

    def _build_domain_fallback_query(self, category: str, domain: str, company_name: str) -> str:
        if category == "business":
            return f'site:{domain} "{company_name}" about products services solutions'
        if category == "leadership":
            return f'site:{domain} "{company_name}" CEO CFO Vorstand executive team'
        if category == "structure":
            return f'site:{domain} "{company_name}" subsidiaries holding Tochtergesellschaften'
        return f'site:{domain} "{company_name}" lawsuit fine sanction compliance'

    def _is_category_relevant(self, category: str, text: str) -> bool:
        if category in ("profile", "business"):
            return True
        lowered = text.lower()
        if category == "leadership":
            return any(term in lowered for term in LEADERSHIP_TERMS)
        if category == "structure":
            return any(term in lowered for term in STRUCTURE_TERMS)
        if category == "risk":
            return any(term in lowered for term in RISK_TERMS)
        return True

    def _is_low_value_source(self, url: str) -> bool:
        host = self._extract_host(url)
        if not host:
            return False
        return self._host_in_set(host, GENERIC_BUSINESS_DIRECTORIES)

    @staticmethod
    def _extract_host(url: str) -> str:
        host = urlparse(url).netloc.lower().replace("www.", "").strip()
        return host

    @staticmethod
    def _host_in_set(host: str, domains) -> bool:
        """True if host equals or is a subdomain of any domain in the set."""
        return any(host == d or host.endswith(f".{d}") for d in domains)

    def _url_matches_domain(self, url: str, domain: str) -> bool:
        host = self._extract_host(url)
        target = (domain or "").lower().replace("www.", "").strip()
        if not host or not target:
            return False
        return host == target or host.endswith(f".{target}")

    def _escape_search_term(self, value: str) -> str:
        return re.sub(r'["`]+', " ", value).strip()
