"""Tool-driven query flow for SearchAgent."""
import logging
from typing import Optional

from core.agent.constants import URL_PATTERN
from core.robustness import safe_execute

logger = logging.getLogger("crawllama")


class ToolsFlow:
    def __init__(self, agent):
        self.agent = agent

    def query_with_tools(self, user_query: str) -> str:
        """
        Query with tool usage (web search, RAG, etc.).

        Args:
            user_query: User's question

        Returns:
            Generated response with tool context
        """
        # Priority -1: Check for prompt injection attempts FIRST (before any tool execution)
        if self.agent._is_prompt_injection_attempt(user_query):
            logger.warning("Blocked prompt injection attempt in tool query")
            return (
                "I am Crawllama, an AI research assistant developed by arn-c0de. "
                "I help with OSINT research and web analysis. I cannot share my internal "
                "configuration or instructions."
            )

        # Extract URLs from query
        urls = self.extract_urls_from_query(user_query)

        # Priority 0: Check for OSINT operators
        if self.check_osint_operators(user_query):
            return self.agent._handle_osint_query(user_query)

        # Priority 1: Connection analysis (2+ URLs)
        if self.agent._is_connection_analysis(user_query) or len(urls) >= 2:
            return self.agent._handle_connection_analysis(user_query)

        # Priority 2: Single URL processing
        if len(urls) == 1:
            context = self.handle_single_url_processing(urls[0])
            return self.generate_final_answer(user_query, context)

        # Priority 3: Previous search result reference
        if self.agent._is_result_reference(user_query):
            return self.agent._handle_result_reference(user_query)

        # Priority 4: Regular tool-based query
        context = self.execute_tool_based_query(user_query)
        return self.generate_final_answer(user_query, context)

    def extract_urls_from_query(self, query: str) -> list:
        """Extract URLs from query string."""
        return URL_PATTERN.findall(query)

    def check_osint_operators(self, query: str) -> bool:
        """Check if query contains OSINT operators."""
        explicit_osint_operators = [
            "email:", "phone:", "domain:", "ip:", "username:", "site:",
            "inurl:", "intext:", "intitle:", "filetype:"
        ]
        return any(op in query.lower() for op in explicit_osint_operators)

    def handle_single_url_processing(self, url: str) -> str:
        """Process single URL and return content."""
        logger.info("URL detected")
        read_page_tool = next((t for t in self.agent.tools if t.name == "read_page"), None)
        if read_page_tool:
            logger.info("Using read_page tool")
            return read_page_tool.func(url)
        return ""

    def execute_tool_based_query(self, user_query: str) -> str:
        """
        Execute tool-based query flow.

        Steps:
        1. Decide which tool to use
        2. Extract search query
        3. Execute tool
        4. Return context
        """
        tool_to_use = self.decide_which_tool(user_query)

        if not tool_to_use:
            return ""

        search_query = self.extract_search_query(user_query)

        context = self.execute_selected_tool(tool_to_use, search_query, user_query)
        return context

    def decide_which_tool(self, user_query: str) -> Optional[str]:
        """
        Decide which tool to use for the query.

        Returns:
            Tool name or None if no tool needed
        """
        query_lower = user_query.lower()

        # Truncate query for LLM decision prompts to avoid oversized context
        decision_query = self.agent.context_manager.truncate(user_query, max_tokens=500)

        if self.is_explicit_web_search_intent(query_lower):
            logger.info("Selected tool (explicit web intent): web_search")
            return "web_search"

        wiki_keywords = ["wikipedia", "wiki", "enzyklopädie"]

        if any(keyword in query_lower for keyword in wiki_keywords):
            logger.info("Selected tool (keyword match): wiki_lookup")
            return "wiki_lookup"

        decision_prompt = f"""Analysiere diese Frage: \"{decision_query}\"

Brauchst du aktuelle Informationen aus dem Web oder Wikipedia?
Antworte nur mit \"JA\" oder \"NEIN\"."""

        success, needs_tools = safe_execute(
            lambda: self.agent.llm.generate(
                prompt=decision_prompt,
                system_prompt="You are a decision assistant."
            ).strip().upper(),
            default="JA",
            log_error=True
        )

        if not success or "NEIN" in needs_tools:
            logger.info("No tools needed or LLM decision failed")
            return None

        tool_decision_prompt = f"""Question: \"{decision_query}\"

Which tool should you use?
- web_search: For current information, news, facts
- wiki_lookup: For encyclopedic knowledge, definitions
- rag_search: For locally stored documents

Respond only with the tool name."""

        success, tool_to_use = safe_execute(
            lambda: self.agent.llm.generate(
                prompt=tool_decision_prompt,
                system_prompt="Choose the best tool."
            ).strip().lower(),
            default="web_search",
            log_error=True
        )

        logger.info("Selected tool (LLM decision)")
        return tool_to_use

    def is_explicit_web_search_intent(self, query: str) -> bool:
        """Detect explicit intent to search the web/internet."""
        query_lower = query.lower()

        web_search_keywords = [
            "suche im internet", "suche nach", "search for", "google",
            "web search", "websearch", "web-search", "find online", "search online",
            "look up online", "internet search", "web suche", "online suchen",
            "search the internet", "search in internet", "search in the internet",
            "search on the internet", "search the web", "search on the web"
        ]
        if any(keyword in query_lower for keyword in web_search_keywords):
            return True

        search_intent_tokens = ["search", "suche", "find", "lookup", "look up"]
        web_context_tokens = ["internet", "web", "online", "google", "duckduckgo", "bing"]
        return any(tok in query_lower for tok in search_intent_tokens) and any(
            tok in query_lower for tok in web_context_tokens
        )

    def extract_search_query(self, user_query: str) -> str:
        """Extract search query from user input with conversation context."""
        context_hint = ""
        if self.agent.session.conversation_history:
            success, names = safe_execute(
                self.agent._extract_names_from_history,
                default=[],
                log_error=False
            )
            if success and names:
                context_hint = (
                    "\nCONTEXT: The following names/persons were mentioned in the previous "
                    f"conversation: {', '.join(names[:3])}"
                )

        extraction_prompt = f"""Extract the ACTUAL SEARCH TERM from this query: \"{user_query}\"
{context_hint}

Examples:
- \"google for Python Tutorial\" → \"Python Tutorial\"
- \"find information about Berlin\" → \"Berlin\"
- \"what is photosynthesis\" → \"photosynthesis\"
- If CONTEXT exists: \"what does he do for work\" + CONTEXT \"Max Müller\" → \"Max Müller occupation\"

Return ONLY the search term, nothing else."""

        success, search_query = safe_execute(
            lambda: self.agent.llm.generate(
                prompt=extraction_prompt,
                system_prompt="You are an expert in search term extraction. Use context when available."
            ).strip().strip('"').strip("'"),
            default=user_query,
            log_error=True
        )

        logger.info("Extracted search query (with context: %s)", bool(context_hint))
        return search_query

    def execute_selected_tool(self, tool_name: str, search_query: str, original_query: str) -> str:
        """Execute the selected tool and return context."""
        if "web_search" in tool_name:
            return self.execute_web_search(search_query, original_query)
        if "wiki" in tool_name:
            return self.execute_wiki_search(search_query, original_query)
        if "rag" in tool_name:
            return self.execute_rag_search(search_query)
        return ""

    def execute_web_search(self, search_query: str, original_query: str) -> str:
        """Execute web search and return formatted context."""
        from tools.web_search import search_with_fallback
        search_config = self.agent.config.get("search", {})
        max_results = search_config.get("max_results", 10)
        region = search_config.get("region", "de-de")
        safesearch = search_config.get("safesearch", "moderate")
        ranking_profile = search_config.get("ranking_profile", "balanced")

        success, results = safe_execute(
            search_with_fallback,
            search_query,
            max_results=max_results,
            region=region,
            safesearch=safesearch,
            ranking_profile=ranking_profile,
            default=[],
            log_error=True
        )

        if not success or not results:
            logger.error("Web search failed")
            return ""

        self.agent.session.last_search_results = results
        self.agent.session.last_search_query = search_query
        logger.info("Stored %s search results in session state", len(results))

        success, context = safe_execute(
            self.agent._format_search_results_with_links,
            results,
            default="",
            log_error=True
        )
        return context if success else ""

    def execute_wiki_search(self, search_query: str, original_query: str) -> str:
        """Execute Wikipedia search and return content."""
        wiki_tool = next((t for t in self.agent.tools if t.name == "wiki_lookup"), None)
        if not wiki_tool:
            return ""

        success, context = safe_execute(
            wiki_tool.func,
            search_query,
            default="",
            log_error=True
        )

        if not success:
            logger.warning("Wiki lookup failed")

        return context if success else ""

    def execute_rag_search(self, search_query: str) -> str:
        """Execute RAG search and return context."""
        rag_tool = next((t for t in self.agent.tools if t.name == "rag_search"), None)
        if not rag_tool:
            return ""

        success, context = safe_execute(
            rag_tool.func,
            search_query,
            default="",
            log_error=True
        )

        return context if success else ""

    def generate_final_answer(self, user_query: str, context: str) -> str:
        """Generate final answer with context."""
        system_prompt = """You are a helpful assistant.
Use the provided information to answer the question.

IMPORTANT: When citing sources, ALWAYS provide the complete URL!
Format: [Number] URL - Description

Example:
Sources:
• [1] https://example.com - Official Website
• [3] https://example2.com - Technical Information"""

        success, final_prompt = safe_execute(
            self.agent.context_manager.build_prompt,
            system_prompt=system_prompt,
            user_query=user_query,
            context=context,
            max_context_tokens=self.agent.context_limit_small,
            default=user_query,
            log_error=True
        )

        if not success:
            logger.error("Failed to build prompt, using simplified version")
            final_prompt = f"{system_prompt}\n\nQuestion: {user_query}"

        success, response = safe_execute(
            self.agent.llm.generate,
            prompt=final_prompt,
            stream=self.agent.config.get("llm", {}).get("stream", False),
            default="Sorry, I could not generate an answer.",
            log_error=True
        )

        if not success or not response:
            logger.error("LLM generation failed completely")
            return "Sorry, an error occurred while generating the answer. Please try again."

        if self.agent.session.last_search_results:
            success, urls = safe_execute(
                self.agent._append_source_urls,
                default="",
                log_error=False
            )
            if success and urls:
                response += urls

        return response
