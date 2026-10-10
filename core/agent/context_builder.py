"""Conversation-context assembly for SearchAgent.

Extracted from ``agent.py`` as a delegation collaborator (same pattern as
:class:`ToolsFlow` / :class:`OSINTFlow` / :class:`ResultFlow`):
:class:`SearchAgent` holds a ``ContextBuilder(self)`` and forwards the entry
points. These methods reach back into the agent through ``self.agent``.
"""
import re
from typing import Any


class ContextBuilder:
    """Build conversation context, compact search results and prep page content."""

    def __init__(self, agent):
        self.agent = agent

    def _build_conversation_context(self) -> str:
        """
        Build context string from conversation history.

        Returns:
            Formatted conversation context
        """
        if (
            not self.agent.session.conversation_history
            and not self.agent.session.last_search_results
            and not self.agent.session.loaded_pages_cache
        ):
            return ""

        # German section labels are prompt-internal markers and kept unchanged.
        sections = []
        sections.extend(self._history_context_sections())
        sections.extend(self._search_results_context_sections())
        sections.extend(self._loaded_pages_context_sections())

        total_budget = min(self.agent.context_limit_small, self.agent.context_manager.prompt_budget)
        return self.agent.context_manager.build_prioritized_context(sections, total_budget)

    def _history_context_sections(self) -> list[dict[str, Any]]:
        """Build context sections from the conversation history (priorities 1, 3)."""
        if not self.agent.session.conversation_history:
            return []

        # P1: Last Q&A pair (most relevant for follow-ups)
        last_entry = self.agent.session.conversation_history[-1]
        sections = [{
            "label": "Last question/answer",
            "content": f"Question: {last_entry['query']}\nAnswer: {last_entry['response']}",
            "priority": 1,
        }]

        # P3: Older Q&A pairs (up to 2 previous)
        if len(self.agent.session.conversation_history) > 1:
            older_entries = self.agent.session.conversation_history[-3:-1]
            older_parts = [
                f"Question: {entry['query']}\nAnswer: {entry['response']}"
                for entry in older_entries
            ]
            sections.append({
                "label": "Earlier questions/answers",
                "content": "\n\n".join(older_parts),
                "priority": 3,
            })

        return sections

    def _search_results_context_sections(self) -> list[dict[str, Any]]:
        """Build the search results metadata section (priority 2)."""
        if not self.agent.session.last_search_results:
            return []

        lines = ["Available search results (references):"]
        for i, result in enumerate(self.agent.session.last_search_results[:15], 1):
            title = result.get("title", "No Title")
            url = result.get("url", "")
            snippet = result.get("snippet", "")[:150]
            lines.append(f"[{i}] {title}")
            lines.append(f"URL: {url}")
            if snippet:
                lines.append(f"{snippet}")

        return [{
            "label": "Search results",
            "content": "\n".join(lines),
            "priority": 2,
        }]

    def _loaded_pages_context_sections(self) -> list[dict[str, Any]]:
        """Build one context section per loaded page (priority 4)."""
        sections = []
        for num, page_data in sorted(self.agent.session.loaded_pages_cache.items()):
            content = (
                f"Title: {page_data.get('title', '')}\n"
                f"URL: {page_data.get('url', '')}\n"
                f"Content:\n{page_data.get('content', '')}"
            )
            sections.append({
                "label": f"Loaded page [{num}]",
                "content": content,
                "priority": 4,
            })
        return sections

    def _append_source_urls(self) -> str:
        """
        Append URL reference list for cited sources.

        Returns:
            Formatted URL reference guide
        """
        if not self.agent.session.last_search_results:
            return ""

        reference = ["\n\n═══ Source Reference ═══\n"]
        for i, result in enumerate(self.agent.session.last_search_results, 1):
            title = result.get("title", "No Title")
            url = result.get("url", "")
            reference.append(f"[{i}] {url}")
            reference.append(f"    → {title}\n")

        return "\n".join(reference)

    def _format_search_results_with_links(self, results: list) -> str:
        """
        Format search results with numbered list and URLs.

        Args:
            results: List of search result dictionaries

        Returns:
            Formatted string with numbered results and links
        """
        if not results:
            return "No search results found."

        formatted = ["Search Results:\n"]
        for i, result in enumerate(results, 1):
            title = result.get("title", "No Title")
            url = result.get("url", "")
            snippet = (result.get("snippet", "") or "").strip()
            if len(snippet) > 220:
                snippet = snippet[:220].rsplit(" ", 1)[0] + "..."

            formatted.append(f"[{i}] {title}")
            formatted.append(f"    URL: {url}")
            formatted.append(f"    {snippet}\n")

        return "\n".join(formatted)

    def _compact_search_results(
        self,
        results: list,
        max_results: int = 8,
        max_snippet_chars: int = 220,
    ) -> list:
        """
        Deduplicate and compact search results for session/context usage.

        Args:
            results: Raw search results list
            max_results: Maximum number of results to keep
            max_snippet_chars: Maximum snippet length per result

        Returns:
            Compact list of search result dicts
        """
        if not results:
            return []

        compact = []
        seen_urls = set()

        for result in results:
            if not isinstance(result, dict):
                continue

            url = (result.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = (result.get("title") or "No Title").strip()
            snippet = (result.get("snippet") or "").strip()
            if len(snippet) > max_snippet_chars:
                snippet = snippet[:max_snippet_chars].rsplit(" ", 1)[0].strip() + "..."

            compact.append({
                "title": title[:220] if len(title) > 220 else title,
                "url": url,
                "snippet": snippet,
            })

            if len(compact) >= max_results:
                break

        return compact

    def _prepare_page_content_for_analysis(self, content: str, max_tokens: int = 600) -> str:
        """
        Normalize crawled page content for LLM analysis.

        Drops noisy subpage dumps to reduce hallucinations and prompt bloat, but
        PRESERVES the [EXTERNAL_WEB_CONTENT_*] trust-boundary markers so the model
        can still tell untrusted page data from its instructions. Stripping them
        (as before) defeated the prompt-injection sanitizer. Any pre-existing
        markers are removed first so the result is wrapped exactly once.
        """
        if not content:
            return ""

        cleaned = str(content)
        cleaned = cleaned.replace("[EXTERNAL_WEB_CONTENT_START]", "")
        cleaned = cleaned.replace("[EXTERNAL_WEB_CONTENT_END]", "")

        # Drop verbose link dump sections that are usually irrelevant for semantic summarization
        cleaned = re.sub(
            r"--- Additional Subpages.*?(?=(?:\n---|\Z))",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        cleaned = re.sub(
            r"--- Contact Subpages.*?(?=(?:\n---|\Z))",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )

        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        cleaned = self.agent.context_manager.truncate(cleaned, max_tokens=max_tokens)
        if not cleaned:
            return ""
        # Re-wrap exactly once so the untrusted-data boundary reaches the LLM.
        return f"[EXTERNAL_WEB_CONTENT_START]\n{cleaned}\n[EXTERNAL_WEB_CONTENT_END]"

