"""Search-result reference handling for SearchAgent.

Extracted from ``agent.py`` as a delegation collaborator (same pattern as
:class:`ToolsFlow` / :class:`OSINTFlow`): :class:`SearchAgent` holds a
``ResultFlow(self)`` and forwards the three entry points
(``_handle_result_reference``, ``_is_connection_analysis``,
``_handle_connection_analysis``). These methods reach back into the agent
through ``self.agent``.
"""
import logging
from datetime import UTC, datetime
from typing import Any

from core.agent.constants import (
    PATTERN_1A,
    PATTERN_1B,
    PATTERN_2,
    RESULT_PATTERN,
    RESULT_REFERENCE_PATTERNS,
    URL_PATTERN,
)
from utils.validators import sanitize_exception_message, sanitize_url_for_logging

logger = logging.getLogger("crawllama")

# Result reference keywords ("quellen 2, 3 und 5")
PLURAL_RESULT_KEYWORDS = ['quellen', 'ergebnisse', 'results', 'sources']
SINGULAR_RESULT_KEYWORDS = ['quelle', 'ergebnis', 'result', 'source']

# Keywords indicating the user wants to search WITHIN loaded page(s)
SINGLE_PAGE_SEARCH_KEYWORDS = ["suche nach", "finde", "kontakt", "informationen über"]
MULTI_PAGE_SEARCH_KEYWORDS = ["suche nach", "finde", "kontakt", "informationen über", "nach"]

# Connection analysis keywords: strict ones always trigger, weak ones only
# when at least two URLs or result numbers are present.
STRICT_CONNECTION_KEYWORDS = [
    "verbindung zwischen",
    "connection between",
    "beziehung zwischen",
    "relation between",
    "zeige mir verbindung",
    "analysiere verbindung"
]
WEAK_CONNECTION_KEYWORDS = [
    "verbindung",
    "vergleiche",
    "compare",
    "gemeinsamkeiten",
    "similarities",
    "unterschiede zwischen",
    "differences between"
]

MULTI_PAGE_SUMMARY_SYSTEM_PROMPT = """You are a helpful assistant.
Summarize the contents of all websites and show commonalities and differences.
Rules:
- Do NOT output raw website text blocks, HTML, nav items, or repeated boilerplate.
- Summarize only relevant facts.
- Use source numbers [n] for each key statement.
- If multiple entities with similar names exist, separate them clearly.
- If sources conflict, state the conflict instead of guessing."""

CONNECTION_ANALYSIS_SYSTEM_PROMPT = """You are an expert in web analysis and data comparison.
Analyze the two websites and find connections, commonalities and relationships.

Pay special attention to:
1. **Contact Details**: Same emails, phone numbers, addresses
2. **People/Names**: Same or similar names (executives, employees, authors)
3. **Company Data**: Company name, commercial register number, VAT ID
4. **Links**: Does one page link to the other? Common external links?
5. **Content**: Similar topics, products, services
6. **Technical Details**: Same hosting provider, same IP, same server
7. **Design/Structure**: Similar design, same template/theme

Provide a structured analysis with clear categories."""

SEARCH_TERM_EXTRACTOR_ROLE = "You extract search terms."


class ResultFlow:
    """Handle 'result N' references, multi-result and connection-analysis queries."""

    def __init__(self, agent):
        self.agent = agent

    def _handle_result_reference(self, query: str) -> str:
        """
        Handle query that references one or more previous search results.

        Args:
            query: User query with result reference (e.g., "quelle 2" or "quelle 2, 3 und 6" or "quellen 5, 8, 10")

        Returns:
            Response after processing the referenced result(s)
        """
        result_nums = self._extract_result_numbers(query)
        if not result_nums:
            return "Could not find result number."

        if not self.agent.session.last_search_results:
            return "No previous search results available. Please perform a search first."

        result_nums, error = self._validate_result_numbers(result_nums)
        if error:
            return error

        if len(result_nums) > 1:
            logger.info(f"Processing multiple results: {result_nums}")
            return self._handle_multiple_results(query, result_nums)

        return self._handle_single_result(query, result_nums[0])

    @staticmethod
    def _extract_result_numbers(query: str) -> list[int]:
        """Extract all referenced result numbers (e.g. "quelle 2, 3 und 6")."""
        query_lower = query.lower()
        all_nums = []

        # Pattern 1a: "quelle 2", "ergebnis 3", "quellen 5", etc. (with space)
        all_nums.extend(int(m) for m in PATTERN_1A.findall(query_lower))

        # Pattern 1b: "quellen: 1", "quelle: 2", etc. (with colon)
        all_nums.extend(int(m) for m in PATTERN_1B.findall(query_lower))

        # Plural forms or colon notation usually mean multiple bare numbers follow
        has_plural = any(kw in query_lower for kw in PLURAL_RESULT_KEYWORDS)
        has_colon = ':' in query_lower and any(
            f"{kw}:" in query_lower
            for kw in PLURAL_RESULT_KEYWORDS + SINGULAR_RESULT_KEYWORDS
        )

        # If plural form, colon format, OR we already found keyword-based numbers,
        # extract all bare numbers as well
        if has_plural or has_colon or all_nums:
            for num in (int(m) for m in PATTERN_2.findall(query_lower)):
                if 1 <= num <= 20 and num not in all_nums:  # Reasonable range
                    all_nums.append(num)

        # Remove duplicates and sort
        return sorted(set(all_nums))

    def _validate_result_numbers(self, result_nums: list[int]) -> tuple[list[int], str | None]:
        """
        Validate result numbers against the stored search results.

        Returns:
            (valid_numbers, error_message) - error_message is None on success.
        """
        max_results = len(self.agent.session.last_search_results)
        invalid_nums = []
        valid_nums = []

        for num in result_nums:
            if not isinstance(num, int):
                invalid_nums.append(f"{num} (not integer)")
            elif num < 1:
                invalid_nums.append(f"{num} (< 1)")
            elif num > max_results:
                invalid_nums.append(f"{num} (> {max_results})")
            else:
                valid_nums.append(num)

        if invalid_nums:
            return [], f"Invalid results: {invalid_nums}. Available results: 1-{max_results}."

        if not valid_nums:
            return [], f"No valid results found. Available results: 1-{max_results}."

        return valid_nums, None

    def _get_result(self, num: int) -> dict[str, Any] | None:
        """Return search result ``num`` (1-based) or None if it doesn't exist."""
        results = self.agent.session.last_search_results
        if not isinstance(num, int) or not 1 <= num <= len(results):
            return None
        result = results[num - 1]
        return result if isinstance(result, dict) else None

    def _handle_single_result(self, query: str, result_num: int) -> str:
        """Load a single referenced result page and summarize or search it."""
        result = self._get_result(result_num)
        if result is None:
            return f"Result #{result_num} outside valid range (1-{len(self.agent.session.last_search_results)})."
        url = result.get("url", "")
        title = result.get("title", "")

        logger.info(f"Processing result #{result_num}")  # lgtm[py/clear-text-logging-sensitive-data] - Result details omitted to avoid leaking data

        page_content, error = self._load_and_cache_result_page(result_num, url, title)
        if error:
            return error

        final_prompt = self._build_single_result_prompt(query, title, url, page_content)
        return self.agent.llm.generate(
            prompt=final_prompt,
            stream=self.agent._stream_enabled()
        )

    def _load_and_cache_result_page(
        self,
        result_num: int,
        url: str,
        title: str
    ) -> tuple[str | None, str | None]:
        """
        Read a result page, normalize it, and cache it for follow-up questions.

        Returns:
            (page_content, error_message) - exactly one of the two is None.
        """
        from tools.page_reader import read_page
        try:
            page_content = read_page(
                url,
                max_length=6000,
                include_links=False,
                smart_contact_search=False,
                include_contact_info=False,
            )
            if page_content is None:
                logger.error("Failed to read page: returned None (robots.txt, blacklist, or network error)")
                return None, (
                    "Error: Page could not be loaded. Possible reasons: blocked by robots.txt, "
                    "URL on blacklist, or network error."
                )
            page_content = self.agent._prepare_page_content_for_analysis(page_content, max_tokens=700)

            # IMPORTANT: Cache the loaded page content for follow-up questions
            self.agent.session.loaded_pages_cache[result_num] = {
                "url": "REDACTED",
                "title": title,
                "content": page_content[:self.agent.max_storage_chars],  # Store normalized content for context
                "cached_at": datetime.now(UTC).isoformat()
            }
            logger.info(f"Cached page #{result_num} content ({len(page_content)} chars)")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted from cache to avoid storing sensitive data
            return page_content, None

        except Exception as e:
            sanitized_error = sanitize_exception_message(str(e))
            logger.error(f"Failed to read page: {sanitized_error}")  # lgtm[py/stack-trace-exposure] - Error is sanitized and generic message returned
            logger.debug("Full page read exception details (suppressed)")
            return None, "Error reading page: An internal error occurred while loading the page."

    def _build_single_result_prompt(self, query: str, title: str, url: str, page_content: str) -> str:
        """Build the LLM prompt for a single result: targeted search or summary."""
        context = f"Website: {url}\n\nContent:\n{page_content}"
        wants_search = any(keyword in query.lower() for keyword in SINGLE_PAGE_SEARCH_KEYWORDS)

        if not wants_search:
            # Just summarize the page
            return self.agent.context_manager.build_prompt(
                system_prompt="You are a helpful assistant.\nSummarize the content of this website.",
                user_query=f"Summarize the website: {title}",
                context=context,
                max_context_tokens=self.agent.context_limit_medium
            )

        search_for = self._extract_single_page_search_term(query)
        logger.info(f"Searching for '{search_for}' in page content")

        system_prompt = f"""You are a helpful assistant.
The user wants to find specific information on a website: {search_for}

Analyze the page content and extract the relevant information."""

        return self.agent.context_manager.build_prompt(
            system_prompt=system_prompt,
            user_query=f"Find {search_for} on this website: {title}",
            context=context,
            max_context_tokens=self.agent.context_limit_medium
        )

    def _extract_single_page_search_term(self, query: str) -> str:
        """Ask the LLM what the user wants to find on a single page."""
        extraction_prompt = f"""Extract what the user wants to search for on the website from this query: "{query}"

Examples:
- "search in result 1 for contact information" → "Contact Information"
- "find in result 2 the opening hours" → "Opening Hours"
- "search result 3 for prices" → "Prices"

Return ONLY the search term."""

        return self.agent.llm.generate(
            prompt=extraction_prompt,
            system_prompt=SEARCH_TERM_EXTRACTOR_ROLE
        ).strip()

    def _handle_multiple_results(self, query: str, result_nums: list) -> str:
        """
        Handle query that references multiple search results.

        Args:
            query: User query
            result_nums: List of result numbers to process

        Returns:
            Combined analysis of all results
        """
        logger.info(f"Loading {len(result_nums)} pages for multi-source analysis...")
        pages = self._load_result_pages(result_nums)

        # Check if any pages loaded successfully. Use the explicit per-page "ok"
        # flag — successful content is wrapped in [EXTERNAL_WEB_CONTENT_START],
        # so a content.startswith("[") heuristic would wrongly reject every page.
        successful_pages = [p for p in pages if p.get("ok")]
        if not successful_pages:
            logger.warning("All pages failed to load")
            return f"Error: All {len(pages)} pages could not be loaded.\n\n" + \
                   "\n".join([f"[{p['num']}] {p['title']}: {p['content']}" for p in pages])

        logger.info(f"Successfully loaded {len(successful_pages)}/{len(pages)} pages")

        system_prompt, user_query_text = self._build_multi_result_task(query, len(pages))
        final_prompt = self.agent.context_manager.build_prompt(
            system_prompt=system_prompt,
            user_query=user_query_text,
            context=self._build_multi_page_context(pages),
            max_context_tokens=self.agent.context_limit_xlarge  # More tokens for multiple sources
        )

        response = self.agent.llm.generate(
            prompt=final_prompt,
            stream=self.agent._stream_enabled()
        )

        return response + self._format_processed_sources(pages)

    def _load_result_pages(self, result_nums: list[int]) -> list[dict[str, Any]]:
        """Load all referenced result pages, keeping per-page error placeholders."""
        pages = []
        for num in result_nums:
            page = self._load_one_result_page(num)
            if page is not None:
                pages.append(page)
        return pages

    def _load_one_result_page(self, num: int) -> dict[str, Any] | None:
        """
        Load a single result page for multi-source analysis.

        Returns:
            Page dict (content holds a "[...]" placeholder on load errors),
            or None if the result number itself is invalid.
        """
        from tools.page_reader import read_page

        result = self._get_result(num)
        if result is None:
            logger.warning(f"Skipping invalid result number: {num} (range: 1-{len(self.agent.session.last_search_results)})")
            return None
        url = result.get("url", "")
        title = result.get("title", "")

        try:
            logger.info(f"[{num}] Loading")  # lgtm[py/clear-text-logging-sensitive-data] - Title omitted to avoid logging content
            content = read_page(
                url,
                max_length=6000,
                include_links=False,
                smart_contact_search=False,
                include_contact_info=False,
            )

            if content is None:
                error_msg = "Page could not be loaded (robots.txt, blacklist or network error)"
                logger.error(f"[{num}] ✗ Failed to load page: {error_msg}")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted to avoid logging content
                return {
                    "num": num,
                    "url": "REDACTED",
                    "title": title,
                    "content": f"[{error_msg}]",
                    "ok": False,
                }

            normalized_content = self.agent._prepare_page_content_for_analysis(content, max_tokens=650)
            # Cache the loaded page for follow-up questions
            self.agent.session.loaded_pages_cache[num] = {
                "url": sanitize_url_for_logging(url),
                "title": title,
                "content": normalized_content[:self.agent.max_storage_chars],
                "cached_at": datetime.now(UTC).isoformat()
            }
            logger.info(f"[{num}] ✓ Loaded {len(normalized_content)} characters (cached for follow-ups)")  # lgtm[py/clear-text-logging-sensitive-data] - Content length is not sensitive
            return {
                "num": num,
                "url": "REDACTED",
                "title": title,
                "content": normalized_content,
                "ok": True,
            }

        except Exception as e:
            sanitized_error = sanitize_exception_message(str(e))
            logger.error(f"[{num}] ✗ Failed to load page: {sanitized_error}")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted to avoid logging content
            return {
                "num": num,
                "url": sanitize_url_for_logging(url),
                "title": title,
                "content": "[Error loading page]",
                "ok": False,
            }

    def _build_multi_result_task(self, query: str, page_count: int) -> tuple[str, str]:
        """
        Build (system_prompt, user_query) for the multi-result analysis.

        Searches for a specific term if the query asks for it, otherwise
        falls back to a comparative summary of all pages.
        """
        wants_search = any(keyword in query.lower() for keyword in MULTI_PAGE_SEARCH_KEYWORDS)
        if not wants_search:
            return (
                MULTI_PAGE_SUMMARY_SYSTEM_PROMPT,
                f"Summarize these {page_count} websites and compare them."
            )

        search_for = self._extract_multi_page_search_term(query)
        logger.info(f"Searching for '{search_for}' across {page_count} pages")

        system_prompt = f"""You are a helpful assistant.
The user wants to extract specific information from multiple websites: {search_for}

Analyze ALL websites and provide a concise synthesis.
Rules:
- Do NOT output raw website text blocks, HTML, nav items, or repeated boilerplate.
- Summarize only relevant facts.
- Explicitly map each fact to source numbers like [1], [2], [3].
- If multiple entities with similar names exist, separate them clearly.
- If sources conflict, state the conflict instead of guessing."""

        return system_prompt, f"Find {search_for} in these {page_count} websites and summarize."

    def _extract_multi_page_search_term(self, query: str) -> str:
        """Ask the LLM what the user wants to find across multiple pages."""
        extraction_prompt = f"""Extract what the user wants to search for in the websites from this query: "{query}"

Examples:
- "search source 2 and 3 for contact information" → "Contact Information"
- "find in source 1, 4 and 5 the prices" → "Prices"
- "search for opening hours in source 2" → "Opening Hours"

Return ONLY the search term."""

        return self.agent.llm.generate(
            prompt=extraction_prompt,
            system_prompt=SEARCH_TERM_EXTRACTOR_ROLE
        ).strip()

    def _build_multi_page_context(self, pages: list[dict[str, Any]]) -> str:
        """Concatenate all loaded pages into one labelled context block."""
        context_parts = []
        for page in pages:
            context_parts.append(f"═══ SOURCE [{page['num']}] ═══")
            context_parts.append(f"Title: {page['title']}")
            context_parts.append(f"URL: {page['url']}")
            page_excerpt = self.agent.context_manager.truncate(page["content"], max_tokens=550)
            context_parts.append(f"\nContent:\n{page_excerpt}\n")

        return "\n".join(context_parts)

    @staticmethod
    def _format_processed_sources(pages: list[dict[str, Any]]) -> str:
        """Format the trailing source reference block for multi-result answers."""
        reference = ["\n\n═══ Processed Sources ═══"]
        for page in pages:
            reference.append(f"[{page['num']}] {page['url']}")
            reference.append(f"    → {page['title']}")

        return "\n".join(reference)

    def _is_connection_analysis(self, query: str) -> bool:
        """
        Check if query requests connection analysis between websites.

        Args:
            query: User query

        Returns:
            True if query requests connection analysis
        """
        query_lower = query.lower()

        # Check for URLs or result references
        urls = URL_PATTERN.findall(query)
        result_nums = self._extract_loose_result_numbers(query_lower)
        has_targets = len(urls) >= 2 or len(result_nums) >= 2

        if any(keyword in query_lower for keyword in STRICT_CONNECTION_KEYWORDS):
            return True

        if has_targets and any(keyword in query_lower for keyword in WEAK_CONNECTION_KEYWORDS):
            return True

        # Two URLs joined by connecting words (und/and) also count
        return len(urls) >= 2 and (" und " in query_lower or " and " in query_lower)

    @staticmethod
    def _extract_loose_result_numbers(query_lower: str) -> list[int]:
        """Collect result numbers using only the direct-number reference patterns."""
        result_nums = []
        for pattern in RESULT_REFERENCE_PATTERNS[:4]:  # Use only direct number patterns
            for match in pattern.findall(query_lower):
                if isinstance(match, tuple):
                    result_nums.extend(int(m) for m in match if m.isdigit())
                elif match.isdigit():
                    result_nums.append(int(match))
        return result_nums

    def _handle_connection_analysis(self, query: str) -> str:
        """
        Analyze connections between two websites.

        Args:
            query: User query requesting connection analysis

        Returns:
            Analysis of connections between the websites
        """
        targets, error = self._resolve_connection_targets(query)
        if error:
            return error

        pages, error = self._load_connection_pages(targets)
        if error:
            return error

        # Do not include URLs in logs
        logger.info("Starting connection analysis")  # lgtm[py/clear-text-logging-sensitive-data] - URLs omitted from logs

        final_prompt = self._build_connection_analysis_prompt(pages)
        return self.agent.llm.generate(
            prompt=final_prompt,
            stream=self.agent._stream_enabled()
        )

    def _resolve_connection_targets(self, query: str) -> tuple[list[dict[str, Any]], str | None]:
        """
        Resolve the two pages to compare from result references or direct URLs.

        Returns:
            (targets, error_message) - error_message is None on success.
        """
        # Result references first (e.g. "verbindung zwischen ergebnis 1 und quelle 2")
        result_matches = RESULT_PATTERN.findall(query.lower())
        if result_matches:
            return self._resolve_targets_from_results([int(num) for num in result_matches])

        # Otherwise extract direct URLs
        found_urls = URL_PATTERN.findall(query)
        if len(found_urls) < 2:
            return [], (
                "Please provide two URLs or result numbers "
                "(e.g. 'Connection between https://example1.com and https://example2.com')."
            )

        # Do not log specific URLs to avoid exposing user-submitted addresses
        logger.info("Analyzing connection between two URLs")  # lgtm[py/clear-text-logging-sensitive-data] - URLs omitted from logs
        return [
            {"url": found_urls[0], "title": found_urls[0], "number": 1},
            {"url": found_urls[1], "title": found_urls[1], "number": 2}
        ], None

    def _resolve_targets_from_results(self, result_nums: list[int]) -> tuple[list[dict[str, Any]], str | None]:
        """Resolve connection targets from previously stored search results."""
        if len(result_nums) < 2:
            return [], (
                "Please provide at least two result numbers "
                "(e.g. 'Connection between result 1 and result 2')."
            )

        targets = []
        for num in result_nums[:2]:  # Take first two
            result = self._get_result(num)
            if result is None:
                return [], f"Result {num} does not exist (available: 1-{len(self.agent.session.last_search_results)})."
            if not result.get("url"):
                return [], f"Error accessing result #{num}."
            targets.append({
                "url": result["url"],
                "title": result.get("title", ""),
                "number": num
            })

        logger.info(f"Analyzing connection between result #{result_nums[0]} and #{result_nums[1]}")
        return targets, None

    @staticmethod
    def _load_connection_pages(targets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None]:
        """
        Load both pages for connection analysis.

        Returns:
            (pages, error_message) - error_message is None on success.
        """
        from tools.page_reader import read_page

        pages = []
        logger.info(f"Loading {len(targets[:2])} pages for connection analysis...")

        for i, item in enumerate(targets[:2], 1):
            try:
                # Avoid logging or storing specific URLs
                logger.info(f"[{i}/2] Loading page")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
                content = read_page(item["url"])
                pages.append({
                    "url": "REDACTED",
                    "title": item["title"],
                    "content": content,
                    "number": item.get("number")
                })
                logger.info(f"[{i}/2] Successfully loaded {len(content)} characters from page")  # lgtm[py/clear-text-logging-sensitive-data] - URL omitted
            except Exception as e:
                sanitized_error = sanitize_exception_message(str(e))
                logger.error(f"Failed to load page: {sanitized_error}")  # lgtm[py/stack-trace-exposure] - Error sanitized and generic message returned
                logger.debug("Full page load exception details (suppressed)")
                return [], "Error loading page: An internal error occurred while loading the page."

        return pages, None

    def _build_connection_analysis_prompt(self, pages: list[dict[str, Any]]) -> str:
        """Build the LLM prompt comparing the two loaded pages."""
        analysis_query = f"""Analyze the connection between these two websites:

**Website 1:** {pages[0]['title']}
URL: {pages[0]['url']}

**Website 2:** {pages[1]['title']}
URL: {pages[1]['url']}

Find all commonalities, connections and relationships."""

        context = f"""=== WEBSITE 1 ===
URL: {pages[0]['url']}
Title: {pages[0]['title']}

Content:
{pages[0]['content'][:self.agent.context_limit_small]}

=== WEBSITE 2 ===
URL: {pages[1]['url']}
Title: {pages[1]['title']}

Content:
{pages[1]['content'][:self.agent.context_limit_small]}"""

        return self.agent.context_manager.build_prompt(
            system_prompt=CONNECTION_ANALYSIS_SYSTEM_PROMPT,
            user_query=analysis_query,
            context=context,
            max_context_tokens=self.agent.context_limit_large
        )

