"""Main agent for orchestrating tools and LLM interactions."""
import logging
import json
from typing import Optional, Dict, Any
from core.llm_client import OllamaClient
from core.context_manager import ContextManager
from core.cache import CacheManager
from tools.tool_registry import ToolRegistry

logger = logging.getLogger("crawllama")


class SearchAgent:
    """Main agent that orchestrates web search, RAG, and LLM."""

    def __init__(
        self,
        config: Dict[str, Any],
        enable_web: bool = True,
        debug: bool = False
    ):
        """
        Initialize the search agent.

        Args:
            config: Configuration dictionary
            enable_web: Whether to enable web search tools
            debug: Enable debug mode
        """
        self.config = config
        self.enable_web = enable_web
        self.debug = debug

        # Initialize components
        llm_config = config.get("llm", {})
        self.llm = OllamaClient(
            base_url=llm_config.get("base_url", "http://127.0.0.1:11434"),
            model=llm_config.get("model", "qwen2.5:3b"),
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens", 4096)
        )

        context_config = config.get("security", {})
        self.context_manager = ContextManager(
            max_tokens=context_config.get("max_context_length", 8000)
        )

        cache_config = config.get("cache", {})
        self.cache = CacheManager(
            cache_dir="data/cache",
            ttl_hours=cache_config.get("ttl_hours", 24)
        ) if cache_config.get("enabled", True) else None

        rag_config = config.get("rag", {})
        self.tool_registry = ToolRegistry(
            rag_enabled=rag_config.get("enabled", True)
        )

        self.tools = self.tool_registry.get_tools() if enable_web else []

        logger.info(f"Agent initialized (web: {enable_web}, tools: {len(self.tools)})")

    def query(self, user_query: str, use_tools: bool = True) -> str:
        """
        Process user query and generate response.

        Args:
            user_query: User's question
            use_tools: Whether to use tools (web search, etc.)

        Returns:
            Generated response
        """
        logger.info(f"Processing query: '{user_query}'")

        # Check cache first
        if self.cache:
            cached_response = self.cache.get(user_query)
            if cached_response:
                logger.info("Returning cached response")
                return cached_response

        try:
            if use_tools and self.enable_web:
                response = self._query_with_tools(user_query)
            else:
                response = self._query_direct(user_query)

            # Cache the response
            if self.cache:
                self.cache.set(user_query, response)

            return response

        except Exception as e:
            logger.error(f"Query failed: {e}")
            return f"Error: {str(e)}"

    def _query_direct(self, user_query: str) -> str:
        """
        Query LLM directly without tools.

        Args:
            user_query: User's question

        Returns:
            LLM response
        """
        system_prompt = """Du bist ein hilfreicher Assistent.
Beantworte Fragen präzise und informativ auf Deutsch."""

        prompt = self.context_manager.build_prompt(
            system_prompt=system_prompt,
            user_query=user_query
        )

        return self.llm.generate(
            prompt=prompt,
            stream=self.config.get("llm", {}).get("stream", False)
        )

    def _query_with_tools(self, user_query: str) -> str:
        """
        Query with tool usage (web search, RAG, etc.).

        Args:
            user_query: User's question

        Returns:
            Generated response with tool context
        """
        # Step 1: Decide if tools are needed
        decision_prompt = f"""Analysiere diese Frage: "{user_query}"

Brauchst du aktuelle Informationen aus dem Web oder Wikipedia?
Antworte nur mit "JA" oder "NEIN"."""

        needs_tools = self.llm.generate(
            prompt=decision_prompt,
            system_prompt="Du bist ein Entscheidungsassistent."
        ).strip().upper()

        if "NEIN" in needs_tools:
            logger.info("No tools needed, answering directly")
            return self._query_direct(user_query)

        # Step 2: Determine which tool to use
        tool_decision_prompt = f"""Frage: "{user_query}"

Welches Tool solltest du nutzen?
- web_search: Für aktuelle Informationen, News, Fakten
- wiki_lookup: Für enzyklopädisches Wissen, Definitionen
- rag_search: Für lokal gespeicherte Dokumente

Antworte nur mit dem Tool-Namen."""

        tool_to_use = self.llm.generate(
            prompt=tool_decision_prompt,
            system_prompt="Wähle das beste Tool."
        ).strip().lower()

        logger.info(f"Selected tool: {tool_to_use}")

        # Step 3: Use the selected tool
        context = ""
        if "web_search" in tool_to_use:
            search_tool = next((t for t in self.tools if t.name == "web_search"), None)
            if search_tool:
                context = search_tool.func(user_query)

        elif "wiki" in tool_to_use:
            wiki_tool = next((t for t in self.tools if t.name == "wiki_lookup"), None)
            if wiki_tool:
                context = wiki_tool.func(user_query)

        elif "rag" in tool_to_use:
            rag_tool = next((t for t in self.tools if t.name == "rag_search"), None)
            if rag_tool:
                context = rag_tool.func(user_query)

        # Step 4: Generate answer with context
        system_prompt = """Du bist ein hilfreicher Assistent.
Nutze die bereitgestellten Informationen um die Frage zu beantworten.
Zitiere Quellen wenn möglich."""

        final_prompt = self.context_manager.build_prompt(
            system_prompt=system_prompt,
            user_query=user_query,
            context=context,
            max_context_tokens=2000
        )

        return self.llm.generate(
            prompt=final_prompt,
            stream=self.config.get("llm", {}).get("stream", False)
        )

    def add_to_knowledge_base(self, texts: list, metadatas: Optional[list] = None) -> bool:
        """
        Add documents to RAG knowledge base.

        Args:
            texts: List of text documents
            metadatas: Optional metadata

        Returns:
            True if successful
        """
        return self.tool_registry.add_documents_to_rag(texts, metadatas)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get agent statistics.

        Returns:
            Dictionary with stats
        """
        stats = {
            "tools_available": len(self.tools),
            "web_enabled": self.enable_web,
            "model": self.llm.model,
        }

        if self.cache:
            stats["cache"] = self.cache.get_stats()

        stats["rag"] = self.tool_registry.get_rag_stats()

        return stats
