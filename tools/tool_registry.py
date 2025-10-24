"""Tool registry for LangChain agent integration."""
import logging
from typing import List, Optional
from langchain_core.tools import StructuredTool
from tools.web_search import web_search, format_search_results
from tools.page_reader import read_page
from tools.wiki_lookup import wiki_lookup
from tools.rag import RAGManager, format_rag_results

logger = logging.getLogger("crawllama")


class ToolRegistry:
    """Registry for managing agent tools."""

    def __init__(self, rag_enabled: bool = True, config: dict = None):
        """
        Initialize tool registry.

        Args:
            rag_enabled: Whether to enable RAG tool
            config: Configuration dictionary
        """
        self.rag_enabled = rag_enabled
        self.rag_manager = None
        self.config = config or {}

        # Get search config
        search_config = self.config.get("search", {})
        self.max_results = search_config.get("max_results", 10)
        self.search_region = search_config.get("region", "de-de")

        if rag_enabled:
            try:
                paths_config = self.config.get("paths", {})
                embeddings_dir = paths_config.get("embeddings_dir", "data/embeddings")
                self.rag_manager = RAGManager(persist_dir=embeddings_dir)
            except Exception as e:
                logger.warning(f"RAG initialization failed: {e}")
                self.rag_enabled = False

        logger.info(f"Tool registry initialized (RAG: {self.rag_enabled}, max_results: {self.max_results}, region: {self.search_region})")

    def _web_search_wrapper(self, query: str) -> str:
        """Web search tool wrapper."""
        try:
            results = web_search(
                query,
                max_results=self.max_results,
                region=self.search_region
            )
            return format_search_results(results)
        except Exception as e:
            logger.error(f"Web search tool error: {e}")
            return f"Search failed: {str(e)}"

    def _page_reader_wrapper(self, url: str) -> str:
        """Page reader tool wrapper."""
        try:
            content = read_page(url)
            if content:
                return content
            return "Failed to read page or page is empty."
        except Exception as e:
            logger.error(f"Page reader tool error: {e}")
            return f"Page read failed: {str(e)}"

    def _wiki_lookup_wrapper(self, query: str) -> str:
        """Wikipedia lookup tool wrapper."""
        try:
            result = wiki_lookup(query, lang="de", sentences=5)
            if result:
                return result
            return "No Wikipedia article found."
        except Exception as e:
            logger.error(f"Wikipedia tool error: {e}")
            return f"Wikipedia lookup failed: {str(e)}"

    def _rag_search_wrapper(self, query: str) -> str:
        """RAG search tool wrapper."""
        if not self.rag_enabled or not self.rag_manager:
            return "RAG is not enabled."

        try:
            results = self.rag_manager.search(query, top_k=5)
            return format_rag_results(results)
        except Exception as e:
            logger.error(f"RAG tool error: {e}")
            return f"RAG search failed: {str(e)}"

    def get_tools(self) -> List[StructuredTool]:
        """
        Get list of available tools for the agent.

        Returns:
            List of LangChain StructuredTool objects
        """
        tools = [
            StructuredTool.from_function(
                name="web_search",
                func=self._web_search_wrapper,
                description=(
                    "Search the web for current information. "
                    "Input should be a search query string. "
                    "Use this when you need up-to-date information or facts not in your knowledge base."
                )
            ),
            StructuredTool.from_function(
                name="read_page",
                func=self._page_reader_wrapper,
                description=(
                    "Read and extract content from a web page. "
                    "Input should be a valid URL starting with http:// or https://. "
                    "Use this after getting search results to read full page content."
                )
            ),
            StructuredTool.from_function(
                name="wiki_lookup",
                func=self._wiki_lookup_wrapper,
                description=(
                    "Look up information on Wikipedia (German). "
                    "Input should be a topic or term to search for. "
                    "Use this for encyclopedic knowledge and factual information."
                )
            )
        ]

        if self.rag_enabled:
            tools.append(
                StructuredTool.from_function(
                    name="rag_search",
                    func=self._rag_search_wrapper,
                    description=(
                        "Search in locally stored documents using semantic similarity. "
                        "Input should be a search query. "
                        "Use this to find information from previously stored documents."
                    )
                )
            )

        logger.info(f"Registered {len(tools)} tools")
        return tools

    def add_documents_to_rag(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None
    ) -> bool:
        """
        Add documents to RAG system.

        Args:
            texts: List of text documents
            metadatas: Optional metadata

        Returns:
            True if successful, False otherwise
        """
        if not self.rag_enabled or not self.rag_manager:
            logger.warning("RAG is not enabled")
            return False

        try:
            self.rag_manager.add_documents(texts, metadatas)
            return True
        except Exception as e:
            logger.error(f"Failed to add documents to RAG: {e}")
            return False

    def get_rag_stats(self) -> dict:
        """Get RAG statistics."""
        if not self.rag_enabled or not self.rag_manager:
            return {"enabled": False}

        return {
            "enabled": True,
            **self.rag_manager.get_stats()
        }
