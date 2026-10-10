"""Result reranking and search-preference/region/profile resolution.

Pure helpers extracted from tools/web_search.py (no network, no DDGS)."""
import re
from urllib.parse import urlparse


def _extract_inline_operator(query: str, operator: str) -> tuple[str | None, str]:
    """Extract operator value from query and return cleaned query."""
    pattern = rf"(?i)(?:^|\s){re.escape(operator)}:(?:\"([^\"]+)\"|([^\s]+))"
    match = re.search(pattern, query)
    if not match:
        return None, query

    value = (match.group(1) or match.group(2) or "").strip()
    cleaned = (query[:match.start()] + " " + query[match.end():]).strip()
    cleaned = " ".join(cleaned.split())
    return value or None, cleaned



COUNTRY_TO_REGION = {
    "de": "de-de", "deutschland": "de-de", "germany": "de-de",
    "us": "us-en", "usa": "us-en", "united-states": "us-en", "united_states": "us-en",
    "uk": "uk-en", "gb": "uk-en", "united-kingdom": "uk-en", "great-britain": "uk-en",
    "fr": "fr-fr", "france": "fr-fr",
    "es": "es-es", "spain": "es-es",
    "it": "it-it", "italy": "it-it",
    "nl": "nl-nl", "netherlands": "nl-nl",
    "pl": "pl-pl", "poland": "pl-pl",
    "pt": "pt-pt", "portugal": "pt-pt",
    "at": "at-de", "austria": "at-de",
    "ch": "ch-de", "switzerland": "ch-de",
    "be": "be-fr", "belgium": "be-fr",
    "ca": "ca-en", "canada": "ca-en",
    "au": "au-en", "australia": "au-en",
    "br": "br-pt", "brazil": "br-pt",
    "mx": "mx-es", "mexico": "mx-es",
    "jp": "jp-jp", "japan": "jp-jp",
    "kr": "kr-kr", "korea": "kr-kr",
    "cn": "cn-zh", "china": "cn-zh",
    "in": "in-en", "india": "in-en",
    "ru": "ru-ru", "russia": "ru-ru",
}

LANG_TO_REGION = {
    "de": "de-de",
    "en": "us-en",
    "fr": "fr-fr",
    "es": "es-es",
    "it": "it-it",
    "nl": "nl-nl",
    "pl": "pl-pl",
    "pt": "pt-pt",
    "ja": "jp-jp",
    "ko": "kr-kr",
    "zh": "cn-zh",
    "ru": "ru-ru",
}

RANKING_PROFILES = {
    "balanced": {
        "base_order": 1.0,
        "exact_title": 5.0,
        "exact_snippet": 2.5,
        "title_overlap": 1.0,
        "snippet_overlap": 0.4,
        "coverage": 1.5,
        "trust": 1.0,
    },
    "strict_factual": {
        "base_order": 0.8,
        "exact_title": 5.5,
        "exact_snippet": 2.0,
        "title_overlap": 1.2,
        "snippet_overlap": 0.25,
        "coverage": 1.8,
        "trust": 1.4,
    },
    "osint": {
        "base_order": 1.0,
        "exact_title": 6.0,
        "exact_snippet": 3.0,
        "title_overlap": 1.15,
        "snippet_overlap": 0.55,
        "coverage": 2.0,
        "trust": 0.75,
    },
}

OSINT_PROFILE_HINTS = (
    "email:",
    "phone:",
    "phonenumber:",
    "domain:",
    "ip:",
    "username:",
    "site:",
    "inurl:",
    "intext:",
    "intitle:",
    "filetype:",
)

STRICT_FACTUAL_HINTS = (
    "official",
    "government",
    "regulation",
    "law",
    "statistic",
    "statistics",
    "report",
    "whitepaper",
    "documentation",
    "specification",
    "source",
    "citation",
    "studie",
    "gesetz",
    "verordnung",
    "offiziell",
    "quelle",
)


def _tokenize_query_text(text: str) -> list[str]:
    """Tokenize text for simple lexical relevance scoring."""
    return re.findall(r"[a-z0-9]{2,}", text.lower())


def _domain_trust_score(url: str) -> float:
    """Assign a lightweight trust prior based on TLD/domain patterns."""
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except Exception:
        return 0.0

    if not host:
        return 0.0

    score = 0.0
    if host.endswith(".gov") or host.endswith(".gov.uk"):
        score += 1.2
    if host.endswith(".edu"):
        score += 1.0
    if host.endswith(".org"):
        score += 0.5
    if host.startswith("www."):
        score += 0.05
    if host == "wikipedia.org" or host.endswith(".wikipedia.org"):
        score += 0.8
    return score


def rerank_results(
    query: str,
    results: list[dict[str, str]],
    ranking_profile: str = "balanced",
) -> list[dict[str, str]]:
    """Re-rank search results by lexical relevance and lightweight domain trust."""
    if not results:
        return results

    profile = RANKING_PROFILES.get((ranking_profile or "balanced").lower(), RANKING_PROFILES["balanced"])
    normalized_query = (query or "").strip().lower()
    query_tokens = _tokenize_query_text(normalized_query)
    query_token_set = set(query_tokens)

    ranked: list[tuple[float, dict[str, str]]] = []
    for idx, result in enumerate(results):
        title = (result.get("title") or "").lower()
        snippet = (result.get("snippet") or "").lower()
        url = result.get("url") or ""
        combined_text = f"{title} {snippet}"

        score = 0.0

        # Preserve original provider order as mild tie-breaker
        score += max(0.0, profile["base_order"] - idx * 0.03)

        # Exact phrase matches are strong signals
        if normalized_query and normalized_query in title:
            score += profile["exact_title"]
        if normalized_query and normalized_query in snippet:
            score += profile["exact_snippet"]

        # Token overlap (title weighted stronger than snippet)
        if query_token_set:
            title_tokens = set(_tokenize_query_text(title))
            snippet_tokens = set(_tokenize_query_text(snippet))
            score += len(query_token_set & title_tokens) * profile["title_overlap"]
            score += len(query_token_set & snippet_tokens) * profile["snippet_overlap"]

            # Coverage bonus if most query tokens appear anywhere
            combined_tokens = set(_tokenize_query_text(combined_text))
            coverage = len(query_token_set & combined_tokens) / max(1, len(query_token_set))
            score += coverage * profile["coverage"]

        score += _domain_trust_score(url) * profile["trust"]

        ranked.append((score, result))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in ranked]


def resolve_region_from_preferences(
    default_region: str = "de-de",
    region: str | None = None,
    country: str | None = None,
    lang: str | None = None,
) -> str:
    """Resolve DDGS region code from explicit region/country/lang preferences."""
    if region:
        normalized_region = region.strip().lower()
        if re.match(r"^[a-z]{2}-[a-z]{2}$", normalized_region):
            return normalized_region
        mapped_from_country = COUNTRY_TO_REGION.get(normalized_region)
        if mapped_from_country:
            return mapped_from_country

    if country:
        normalized_country = country.strip().lower().replace(" ", "-")
        mapped_from_country = COUNTRY_TO_REGION.get(normalized_country)
        if mapped_from_country:
            return mapped_from_country

    if lang:
        normalized_lang = lang.strip().lower()
        mapped_from_lang = LANG_TO_REGION.get(normalized_lang)
        if mapped_from_lang:
            return mapped_from_lang

    return default_region


def resolve_search_preferences(query: str, default_region: str = "de-de") -> tuple[str, str]:
    """
    Resolve query-level search preferences.

    Supports inline operators in plain search queries:
    - country:us / country:germany
    - lang:en
    - region:us-en
    """
    cleaned_query = query.strip()

    region_hint, cleaned_query = _extract_inline_operator(cleaned_query, "region")
    country_hint, cleaned_query = _extract_inline_operator(cleaned_query, "country")
    lang_hint, cleaned_query = _extract_inline_operator(cleaned_query, "lang")

    effective_region = resolve_region_from_preferences(
        default_region=default_region,
        region=region_hint,
        country=country_hint,
        lang=lang_hint,
    )

    return cleaned_query, effective_region


def resolve_ranking_profile(query: str, requested_profile: str = "balanced") -> str:
    """
    Resolve ranking profile from config/inline operators/query intent.

    Supported explicit inline operators:
    - ranking:<profile>
    - profile:<profile>

    Automatic mode:
    - requested_profile in {"auto", "adaptive"}
    """
    effective_profile = (requested_profile or "balanced").strip().lower()
    cleaned_query = (query or "").strip()

    ranking_hint, _ = _extract_inline_operator(cleaned_query, "ranking")
    profile_hint, _ = _extract_inline_operator(cleaned_query, "profile")
    explicit_profile = (ranking_hint or profile_hint or "").strip().lower()
    if explicit_profile in RANKING_PROFILES:
        return explicit_profile

    if effective_profile not in ("auto", "adaptive"):
        return effective_profile if effective_profile in RANKING_PROFILES else "balanced"

    lowered = cleaned_query.lower()
    if any(hint in lowered for hint in OSINT_PROFILE_HINTS):
        return "osint"

    if any(hint in lowered for hint in STRICT_FACTUAL_HINTS):
        return "strict_factual"

    return "balanced"
