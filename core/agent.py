"""Main agent for orchestrating tools and LLM interactions."""
import logging
import json
import re
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime
from core.llm_client import OllamaClient
from core.context_manager import ContextManager
from core.cache import CacheManager
from tools.tool_registry import ToolRegistry
from core.robustness import (
    retry_on_failure,
    safe_execute,
    validate_input,
    sanitize_query,
    log_performance,
    health_checker
)

logger = logging.getLogger("crawllama")

# Pre-compiled regex patterns for performance
URL_PATTERN = re.compile(r'https?://[^\s]+')
NAME_PATTERN = re.compile(r'\b[A-ZÄÖÜß][a-zäöüß]+(?: [A-ZÄÖÜß][a-zäöüß]+)+\b')

# Result reference patterns
RESULT_REFERENCE_PATTERNS = [
    re.compile(r'\bergebnisse?\s+(\d+)\b'),  # ergebnis OR ergebnisse + number
    re.compile(r'\bresults?\s+(\d+)\b'),      # result OR results + number
    re.compile(r'\bquellen?\s+(\d+)\b'),      # quelle OR quellen + number
    re.compile(r'\bsources?\s+(\d+)\b'),      # source OR sources + number
    re.compile(r'\b(\d+)\.\s*ergebnisse?\b'),
    re.compile(r'\b(\d+)\.\s*results?\b'),
    re.compile(r'\b(\d+)\.\s*quellen?\b'),
    re.compile(r'\b(\d+)\.\s*sources?\b'),
    re.compile(r'\bquellen?:\s*\d+'),
    re.compile(r'\bergebnisse?:\s*\d+'),
    re.compile(r'\bresults?:\s*\d+'),
    re.compile(r'\bsources?:\s*\d+'),
    re.compile(r'\bdurchsuche\s+quellen?\b'),
    re.compile(r'\bsuche\s+in\s+quellen?\b'),
    re.compile(r'\bsuche\s+quellen?\b'),
    re.compile(r'\banalysiere\s+.*quellen?\b'),
    re.compile(r'\bfasse.*zusammen\s+.*quellen?\b'),
    re.compile(r'\bvergleiche\s+.*quellen?\b'),
    re.compile(r'\bin\s+quellen?\s+(\d+)\b'),
    re.compile(r'\bin\s+ergebnisse?\s+(\d+)\b')
]

# Additional patterns
PATTERN_1A = re.compile(r'(?:quellen?|ergebnisse?|results?|sources?)\s+(\d+)')
PATTERN_1B = re.compile(r'(?:quellen?|ergebnisse?|results?|sources?):\s*(\d+)')
PATTERN_2 = re.compile(r'\b(\d+)\b')
RESULT_PATTERN = re.compile(r'(?:ergebnis|quelle|result|source)\s*(\d+)')

# Follow-up detection patterns
FOLLOWUP_PATTERNS = [
    re.compile(r'\b(wo|was|wer|wie|warum|wann|welche?)\b'),
    re.compile(r'\b(where|what|who|how|why|when|which)\b'),
    re.compile(r'\b(mehr|details?|genauer|weiter)\b'),
    re.compile(r'\b(more|details?|further)\b')
]


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

        # Session file path (from config)
        paths_config = config.get("paths", {})
        self.session_file = Path(paths_config.get("session_file", "data/session.json"))
        self.session_file.parent.mkdir(parents=True, exist_ok=True)

        # Session state for search results
        self.last_search_results = []
        self.last_search_query = ""

        # Conversation history for context
        self.conversation_history = []
        self.max_history = 20  # Keep last 10 Q&A pairs (increased for RTX 3080 16k context)

        # Cache for loaded page contents (for better follow-up questions)
        self.loaded_pages_cache = {}  # {result_num: {"url": ..., "title": ..., "content": ...}}

        # Last processed content (for follow-up questions)
        self.last_content = {
            "type": None,  # "search", "page", "analysis"
            "subject": None,  # e.g., "Person/Topic", URL, etc.
            "summary": None  # Short summary of what was discussed
        }

        # Initialize components
        llm_config = config.get("llm", {})
        self.llm = OllamaClient(
            base_url=llm_config.get("base_url", "http://127.0.0.1:11434"),
            model=llm_config.get("model", "qwen2.5:3b"),
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens", 4096),
            timeout=llm_config.get("timeout", 120),
            max_requests_per_minute=llm_config.get("max_requests_per_minute", 60)
        )

        context_config = config.get("security", {})
        self.context_manager = ContextManager(
            max_tokens=context_config.get("max_context_length", 16000)  # Increased default for RTX 3080
        )

        cache_config = config.get("cache", {})
        paths_config = config.get("paths", {})
        self.cache = CacheManager(
            cache_dir=paths_config.get("cache_dir", "data/cache"),
            ttl_hours=cache_config.get("ttl_hours", 24)
        ) if cache_config.get("enabled", True) else None

        rag_config = config.get("rag", {})
        self.tool_registry = ToolRegistry(
            rag_enabled=rag_config.get("enabled", True),
            config=config
        )

        self.tools = self.tool_registry.get_tools() if enable_web else []

        # Load context limits from config
        context_limits = config.get("context_limits", {})
        self.context_limit_small = context_limits.get("small", 4000)
        self.context_limit_medium = context_limits.get("medium", 6000)
        self.context_limit_large = context_limits.get("large", 8000)
        self.context_limit_xlarge = context_limits.get("xlarge", 12000)
        self.max_storage_chars = context_limits.get("max_storage", 8000)

        logger.info(f"Agent initialized (web: {enable_web}, tools: {len(self.tools)})")

        # Register health checks
        health_checker.register_check(
            "llm",
            lambda: self._check_llm_health(),
            cache_seconds=30
        )

        # Auto-load previous session if exists
        self.load_session()

    @log_performance
    def query(self, user_query: str, use_tools: bool = True) -> str:
        """
        Process user query and generate response.

        Args:
            user_query: User's question
            use_tools: Whether to use tools (web search, etc.)

        Returns:
            Generated response
        """
        # Validate and sanitize input
        is_valid, error_msg = validate_input(
            user_query,
            min_length=1,
            max_length=5000,
            allowed_types=(str,),
            not_empty=True
        )
        if not is_valid:
            logger.error(f"Invalid query: {error_msg}")
            return f"Ungültige Eingabe: {error_msg}"

        user_query = sanitize_query(user_query)
        logger.info(f"Processing query: '{user_query[:100]}...'")

        # Check LLM health
        if not health_checker.is_healthy("llm"):
            logger.warning("LLM health check failed - attempting query anyway")
            # Don't fail immediately, try to proceed

        # Check if query starts with '<' - force context-only mode
        force_context_mode = False
        if user_query.strip().startswith('<'):
            force_context_mode = True
            user_query = user_query.strip()[1:].strip()  # Remove '<' and clean up
            logger.info(f"Context-only mode activated (< prefix). Query: '{user_query}'")

        # Check if query is a result reference (quelle/source) - skip cache for these
        is_result_ref = self._is_result_reference(user_query)
        if is_result_ref:
            logger.info(f"Result reference detected - cache disabled for: '{user_query}'")
        
        # Check cache first (but NOT for context-only mode or result references to avoid stale responses)
        if self.cache and not force_context_mode and not is_result_ref:
            success, cached_response = safe_execute(
                self.cache.get,
                user_query,
                default=None,
                log_error=False
            )
            if success and cached_response:
                logger.info("Returning cached response")
                return cached_response

        try:
            # If '<' prefix was used, force direct answer with context
            if force_context_mode:
                response = self._query_direct(user_query)
            elif use_tools and self.enable_web:
                response = self._query_with_tools(user_query)
            else:
                response = self._query_direct(user_query)

            # Validate response
            if not response or not isinstance(response, str):
                logger.error(f"Invalid response from query processing: {type(response)}")
                return "Entschuldigung, bei der Verarbeitung ist ein Fehler aufgetreten."

            # Update conversation history
            self.conversation_history.append({
                "query": user_query,
                "response": response[:self.context_limit_small]  # Store more context for follow-up questions
            })

            # Keep only last N entries
            if len(self.conversation_history) > self.max_history:
                self.conversation_history = self.conversation_history[-self.max_history:]

            # Cache the response (but NOT for context-only mode or result references to avoid polluting cache)
            if self.cache and not force_context_mode and not is_result_ref:
                success, _ = safe_execute(
                    self.cache.set,
                    user_query,
                    response,
                    log_error=False
                )
                if not success:
                    logger.warning("Failed to cache response")

            # Auto-save session after each query
            success, _ = safe_execute(self.save_session, log_error=True)
            if not success:
                logger.warning("Failed to save session")

            return response

        except KeyboardInterrupt:
            logger.info("Query interrupted by user")
            raise
        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            return f"Entschuldigung, ein Fehler ist aufgetreten: {str(e)}"

    @retry_on_failure(max_retries=2, delay=1.0, exceptions=(Exception,))
    def _query_direct(self, user_query: str) -> str:
        """
        Query LLM directly without tools.

        Args:
            user_query: User's question

        Returns:
            LLM response
        """
        # Check if this is a follow-up question
        is_followup = self._is_followup_question(user_query)

        # Build context from conversation history
        context = ""
        if is_followup and self.conversation_history:
            success, ctx = safe_execute(
                self._build_conversation_context,
                default="",
                log_error=True
            )
            if success:
                context = ctx

        system_prompt = """Du bist ein hilfreicher Assistent.
Beantworte Fragen präzise und informativ auf Deutsch.

Wenn die Frage sich auf einen vorherigen Kontext bezieht (z.B. "dieser", "er", "sie"),
nutze die Informationen aus dem Gesprächsverlauf.

WICHTIG: Wenn im Kontext Suchergebnisse mit Nummern (z.B. [1], [2], [3]) verfügbar sind:
- Verwende IMMER die Quellennummern in eckigen Klammern [Nummer] wenn du dich auf Suchergebnisse beziehst
- Beispiel: "Die wichtigsten Quellen sind [2] Impressum und [1] Datenschutz"
- Bei Follow-up-Fragen zu Quellen: Ordne die URLs den Nummern aus den verfügbaren Suchergebnissen zu
- Format: "[Nummer] Titel - URL" """

        prompt = self.context_manager.build_prompt(
            system_prompt=system_prompt,
            user_query=user_query,
            context=context
        )

        try:
            response = self.llm.generate(
                prompt=prompt,
                stream=self.config.get("llm", {}).get("stream", False)
            )

            # Validate response
            if not response or not isinstance(response, str):
                raise ValueError(f"Invalid LLM response: {type(response)}")

            return response

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    def _query_with_tools(self, user_query: str) -> str:
        """
        Query with tool usage (web search, RAG, etc.).

        Refactored into smaller methods for better maintainability.

        Args:
            user_query: User's question

        Returns:
            Generated response with tool context
        """
        import re

        # Extract URLs from query
        urls = self._extract_urls_from_query(user_query)

        # Priority 0: Check for OSINT operators
        if self._check_osint_operators(user_query):
            return self._handle_osint_query(user_query)

        # Priority 1: Connection analysis (2+ URLs)
        if self._is_connection_analysis(user_query) or len(urls) >= 2:
            return self._handle_connection_analysis(user_query)

        # Priority 2: Single URL processing
        if len(urls) == 1:
            context = self._handle_single_url_processing(urls[0])
            return self._generate_final_answer(user_query, context)

        # Priority 3: Previous search result reference
        if self._is_result_reference(user_query):
            return self._handle_result_reference(user_query)

        # Priority 4: Regular tool-based query
        context = self._execute_tool_based_query(user_query)
        return self._generate_final_answer(user_query, context)

    def _extract_urls_from_query(self, query: str) -> list:
        """Extract URLs from query string."""
        return URL_PATTERN.findall(query)

    def _check_osint_operators(self, query: str) -> bool:
        """Check if query contains OSINT operators."""
        explicit_osint_operators = ["email:", "phone:", "site:", "inurl:", "intext:", "intitle:", "filetype:"]
        return any(op in query.lower() for op in explicit_osint_operators)

    def _handle_single_url_processing(self, url: str) -> str:
        """Process single URL and return content."""
        logger.info(f"URL detected: {url}")
        read_page_tool = next((t for t in self.tools if t.name == "read_page"), None)
        if read_page_tool:
            logger.info(f"Using read_page tool for: {url}")
            return read_page_tool.func(url)
        return ""

    def _execute_tool_based_query(self, user_query: str) -> str:
        """
        Execute tool-based query flow.

        Steps:
        1. Decide which tool to use
        2. Extract search query
        3. Execute tool
        4. Return context
        """
        # Decide tool
        tool_to_use = self._decide_which_tool(user_query)

        if not tool_to_use:
            # No tools needed
            return ""

        # Extract search query
        search_query = self._extract_search_query(user_query)

        # Execute selected tool
        context = self._execute_selected_tool(tool_to_use, search_query, user_query)

        return context

    def _decide_which_tool(self, user_query: str) -> Optional[str]:
        """
        Decide which tool to use for the query.

        Returns:
            Tool name or None if no tool needed
        """
        query_lower = user_query.lower()

        # Check for explicit keywords
        web_search_keywords = [
            "suche im internet", "suche nach", "search for", "google",
            "web search", "find online", "search online", "look up online",
            "internet search", "web suche", "online suchen"
        ]
        wiki_keywords = ["wikipedia", "wiki", "enzyklopädie"]

        if any(keyword in query_lower for keyword in web_search_keywords):
            logger.info("Selected tool (keyword match): web_search")
            return "web_search"

        if any(keyword in query_lower for keyword in wiki_keywords):
            logger.info("Selected tool (keyword match): wiki_lookup")
            return "wiki_lookup"

        # Ask LLM if tools are needed
        decision_prompt = f"""Analysiere diese Frage: "{user_query}"

Brauchst du aktuelle Informationen aus dem Web oder Wikipedia?
Antworte nur mit "JA" oder "NEIN"."""

        success, needs_tools = safe_execute(
            lambda: self.llm.generate(
                prompt=decision_prompt,
                system_prompt="Du bist ein Entscheidungsassistent."
            ).strip().upper(),
            default="JA",
            log_error=True
        )

        if not success or "NEIN" in needs_tools:
            logger.info("No tools needed or LLM decision failed")
            return None

        # Ask LLM which tool to use
        tool_decision_prompt = f"""Frage: "{user_query}"

Welches Tool solltest du nutzen?
- web_search: Für aktuelle Informationen, News, Fakten
- wiki_lookup: Für enzyklopädisches Wissen, Definitionen
- rag_search: Für lokal gespeicherte Dokumente

Antworte nur mit dem Tool-Namen."""

        success, tool_to_use = safe_execute(
            lambda: self.llm.generate(
                prompt=tool_decision_prompt,
                system_prompt="Wähle das beste Tool."
            ).strip().lower(),
            default="web_search",
            log_error=True
        )

        logger.info(f"Selected tool (LLM decision): {tool_to_use}")
        return tool_to_use

    def _extract_search_query(self, user_query: str) -> str:
        """Extract search query from user input with conversation context."""
        context_hint = ""
        if self.conversation_history:
            success, names = safe_execute(
                self._extract_names_from_history,
                default=[],
                log_error=False
            )
            if success and names:
                context_hint = f"\nKONTEXT: In der vorherigen Konversation wurden diese Namen/Personen erwähnt: {', '.join(names[:3])}"

        extraction_prompt = f"""Extrahiere den EIGENTLICHEN SUCHBEGRIFF aus dieser Anfrage: "{user_query}"
{context_hint}

Beispiele:
- "google nach Python Tutorial" → "Python Tutorial"
- "finde Informationen über Berlin" → "Berlin"
- "was ist Photosynthese" → "Photosynthese"
- Wenn KONTEXT vorhanden: "was macht er beruflich" + KONTEXT "Max Müller" → "Max Müller Beruf"

Gib NUR den Suchbegriff zurück, nichts anderes."""

        success, search_query = safe_execute(
            lambda: self.llm.generate(
                prompt=extraction_prompt,
                system_prompt="Du bist ein Experte für Suchbegriff-Extraktion. Nutze den Kontext wenn vorhanden."
            ).strip().strip('"').strip("'"),
            default=user_query,
            log_error=True
        )

        logger.info(f"Extracted search query: '{search_query}' from '{user_query}' (with context: {bool(context_hint)})")
        return search_query

    def _execute_selected_tool(self, tool_name: str, search_query: str, original_query: str) -> str:
        """Execute the selected tool and return context."""
        if "web_search" in tool_name:
            return self._execute_web_search(search_query, original_query)
        elif "wiki" in tool_name:
            return self._execute_wiki_search(search_query, original_query)
        elif "rag" in tool_name:
            return self._execute_rag_search(search_query)
        return ""

    def _execute_web_search(self, search_query: str, original_query: str) -> str:
        """Execute web search and return formatted context."""
        from tools.web_search import web_search
        search_config = self.config.get("search", {})
        max_results = search_config.get("max_results", 10)
        region = search_config.get("region", "de-de")

        success, results = safe_execute(
            web_search,
            search_query,
            max_results=max_results,
            region=region,
            default=[],
            log_error=True
        )

        if not success or not results:
            logger.error("Web search failed")
            return ""

        if results:
            logger.info(f"Sample result: title='{results[0].get('title', 'N/A')}', url='{results[0].get('url', 'EMPTY')}'")

        # Store results in session
        self.last_search_results = results
        self.last_search_query = search_query
        logger.info(f"Stored {len(results)} search results in session state")

        # Format results
        success, context = safe_execute(
            self._format_search_results_with_links,
            results,
            default="",
            log_error=True
        )
        return context if success else ""

    def _execute_wiki_search(self, search_query: str, original_query: str) -> str:
        """Execute Wikipedia search and return content."""
        wiki_tool = next((t for t in self.tools if t.name == "wiki_lookup"), None)
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

    def _execute_rag_search(self, search_query: str) -> str:
        """Execute RAG search and return context."""
        rag_tool = next((t for t in self.tools if t.name == "rag_search"), None)
        if not rag_tool:
            return ""

        success, context = safe_execute(
            rag_tool.func,
            search_query,
            default="",
            log_error=True
        )

        return context if success else ""

    def _generate_final_answer(self, user_query: str, context: str) -> str:
        """Generate final answer with context."""
        system_prompt = """Du bist ein hilfreicher Assistent.
Nutze die bereitgestellten Informationen um die Frage zu beantworten.

WICHTIG: Wenn du Quellen zitierst, gib IMMER die vollständige URL an!
Format: [Nummer] URL - Beschreibung

Beispiel:
Quellen:
• [1] https://example.com - Offizielle Website
• [3] https://example2.com - Fachinformationen"""

        success, final_prompt = safe_execute(
            self.context_manager.build_prompt,
            system_prompt=system_prompt,
            user_query=user_query,
            context=context,
            max_context_tokens=self.context_limit_small,
            default=user_query,
            log_error=True
        )

        if not success:
            logger.error("Failed to build prompt, using simplified version")
            final_prompt = f"{system_prompt}\n\nFrage: {user_query}"

        success, response = safe_execute(
            self.llm.generate,
            prompt=final_prompt,
            stream=self.config.get("llm", {}).get("stream", False),
            default="Entschuldigung, ich konnte keine Antwort generieren.",
            log_error=True
        )

        if not success or not response:
            logger.error("LLM generation failed completely")
            return "Entschuldigung, bei der Antwort-Generierung ist ein Fehler aufgetreten. Bitte versuchen Sie es erneut."

        # Add source URLs if available
        if self.last_search_results:
            success, urls = safe_execute(
                self._append_source_urls,
                default="",
                log_error=False
            )
            if success and urls:
                response += urls

        return response

    def _is_result_reference(self, query: str) -> bool:
        """
        Check if query references a previous search result.

        Args:
            query: User query

        Returns:
            True if query references a result (e.g., "ergebnis 1", "result 2", "quelle 3", "quellen 2, 3, 5")
        """
        query_lower = query.lower()

        for pattern in RESULT_REFERENCE_PATTERNS:
            if pattern.search(query_lower):
                return True

        return False

    def _handle_result_reference(self, query: str) -> str:
        """
        Handle query that references one or more previous search results.

        Args:
            query: User query with result reference (e.g., "quelle 2" or "quelle 2, 3 und 6" or "quellen 5, 8, 10")

        Returns:
            Response after processing the referenced result(s)
        """
        # Extract all result numbers from the query
        query_lower = query.lower()

        # Find all numbers that appear with result/quelle/source keywords
        all_nums = []

        # Pattern 1a: "quelle 2", "ergebnis 3", "quellen 5", etc. (with space)
        all_nums.extend([int(m) for m in PATTERN_1A.findall(query_lower)])

        # Pattern 1b: "quellen: 1", "quelle: 2", etc. (with colon)
        all_nums.extend([int(m) for m in PATTERN_1B.findall(query_lower)])

        # Pattern 2: Check if query contains plural forms or colon, which usually means multiple numbers follow
        plural_keywords = ['quellen', 'ergebnisse', 'results', 'sources']
        has_plural = any(kw in query_lower for kw in plural_keywords)
        has_colon = ':' in query_lower and any(kw + ':' in query_lower for kw in plural_keywords + ['quelle', 'ergebnis', 'result', 'source'])

        # If plural form, colon format, OR we already found keyword-based numbers, extract all bare numbers
        if has_plural or has_colon or all_nums:
            # Look for all bare numbers in the query
            potential_nums = [int(m) for m in PATTERN_2.findall(query_lower)]
            # Add numbers that are in valid range and not already in list
            for num in potential_nums:
                if 1 <= num <= 20 and num not in all_nums:  # Reasonable range
                    all_nums.append(num)

        # Remove duplicates and sort
        result_nums = sorted(set(all_nums))

        if not result_nums:
            return "Konnte keine Ergebnisnummer finden."

        # Check if we have stored results
        if not self.last_search_results:
            return "Keine vorherigen Suchergebnisse vorhanden. Bitte führen Sie zuerst eine Suche durch."

        # Validate all numbers with robust bounds checking
        max_results = len(self.last_search_results)
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
            return f"Ungültige Ergebnisse: {invalid_nums}. Verfügbare Ergebnisse: 1-{max_results}."
            
        # Use only valid numbers
        result_nums = valid_nums
        
        if not result_nums:
            return f"Keine gültigen Ergebnisse gefunden. Verfügbare Ergebnisse: 1-{max_results}."

        # Handle multiple results
        if len(result_nums) > 1:
            logger.info(f"Processing multiple results: {result_nums}")
            return self._handle_multiple_results(query, result_nums)

        # Single result - keep original behavior
        result_num = result_nums[0]
        
        # Safe access to result with additional bounds check
        try:
            if result_num < 1 or result_num > len(self.last_search_results):
                return f"Ergebnis #{result_num} außerhalb gültiger Range (1-{len(self.last_search_results)})."
                
            result = self.last_search_results[result_num - 1]
            url = result.get("url", "")
            title = result.get("title", "")
            
        except (IndexError, TypeError) as e:
            logger.error(f"IndexError accessing result #{result_num}: {e}")
            return f"Fehler beim Zugriff auf Ergebnis #{result_num}. Verfügbare Ergebnisse: 1-{len(self.last_search_results)}."

        logger.info(f"Processing result #{result_num}: {title} ({url})")

        # Read the page
        from tools.page_reader import read_page
        try:
            page_content = read_page(url)
            if page_content is None:
                logger.error(f"Failed to read page: returned None (robots.txt, blacklist, or network error)")
                return f"Fehler: Seite konnte nicht geladen werden.\nMögliche Gründe:\n- Blockiert durch robots.txt\n- URL auf Blacklist\n- Netzwerkfehler\n\nURL: {url}"

            # IMPORTANT: Cache the loaded page content for follow-up questions
            self.loaded_pages_cache[result_num] = {
                "url": url,
                "title": title,
                "content": page_content[:self.max_storage_chars]  # Store up to max_storage_chars for context
            }
            logger.info(f"Cached page #{result_num} content ({len(page_content)} chars)")

        except Exception as e:
            logger.error(f"Failed to read page: {e}")
            return f"Fehler beim Lesen der Seite: {str(e)}"

        # Check if user wants to search within the page
        search_within_keywords = ["suche nach", "finde", "kontakt", "informationen über"]
        wants_search = any(keyword in query_lower for keyword in search_within_keywords)

        if wants_search:
            # Extract what to search for
            extraction_prompt = f"""Extrahiere was der Nutzer auf der Webseite suchen möchte aus dieser Anfrage: "{query}"

Beispiele:
- "suche im ergebnis 1 nach kontaktinformationen" → "Kontaktinformationen"
- "finde im ergebnis 2 die Öffnungszeiten" → "Öffnungszeiten"
- "durchsuche ergebnis 3 nach Preisen" → "Preise"

Gib NUR den Suchbegriff zurück."""

            search_for = self.llm.generate(
                prompt=extraction_prompt,
                system_prompt="Du extrahierst Suchbegriffe."
            ).strip()

            logger.info(f"Searching for '{search_for}' in page content")

            # Generate answer based on search term
            system_prompt = f"""Du bist ein hilfreicher Assistent.
Der Nutzer möchte spezifische Informationen auf einer Webseite finden: {search_for}

Analysiere den Seiteninhalt und extrahiere die relevanten Informationen."""

            final_prompt = self.context_manager.build_prompt(
                system_prompt=system_prompt,
                user_query=f"Finde {search_for} auf dieser Webseite: {title}",
                context=f"Webseite: {url}\n\nInhalt:\n{page_content}",
                max_context_tokens=self.context_limit_medium
            )
        else:
            # Just summarize the page
            system_prompt = """Du bist ein hilfreicher Assistent.
Fasse den Inhalt dieser Webseite zusammen."""

            final_prompt = self.context_manager.build_prompt(
                system_prompt=system_prompt,
                user_query=f"Fasse die Webseite zusammen: {title}",
                context=f"Webseite: {url}\n\nInhalt:\n{page_content}",
                max_context_tokens=self.context_limit_medium
            )

        return self.llm.generate(
            prompt=final_prompt,
            stream=self.config.get("llm", {}).get("stream", False)
        )

    def _handle_multiple_results(self, query: str, result_nums: list) -> str:
        """
        Handle query that references multiple search results.

        Args:
            query: User query
            result_nums: List of result numbers to process

        Returns:
            Combined analysis of all results
        """
        from tools.page_reader import read_page

        logger.info(f"Loading {len(result_nums)} pages for multi-source analysis...")

        # Load all pages with safe access
        pages = []
        for num in result_nums:
            try:
                # Safe bounds checking
                if num < 1 or num > len(self.last_search_results):
                    logger.warning(f"Skipping invalid result number: {num} (range: 1-{len(self.last_search_results)})")
                    continue
                    
                result = self.last_search_results[num - 1]
                url = result.get("url", "")
                title = result.get("title", "")
                
            except (IndexError, TypeError) as e:
                logger.error(f"Error accessing result #{num}: {e}")
                continue

            try:
                logger.info(f"[{num}] Loading: {title}")
                content = read_page(url)

                # Check if content was successfully loaded
                if content is None:
                    error_msg = "Seite konnte nicht geladen werden (robots.txt, Blacklist oder Netzwerkfehler)"
                    logger.error(f"[{num}] ✗ Failed to load {url}: {error_msg}")
                    pages.append({
                        "num": num,
                        "url": url,
                        "title": title,
                        "content": f"[{error_msg}]"
                    })
                else:
                    pages.append({
                        "num": num,
                        "url": url,
                        "title": title,
                        "content": content
                    })
                    # Cache the loaded page for follow-up questions
                    self.loaded_pages_cache[num] = {
                        "url": url,
                        "title": title,
                        "content": content[:self.max_storage_chars]
                    }
                    logger.info(f"[{num}] ✓ Loaded {len(content)} characters (cached for follow-ups)")
            except Exception as e:
                logger.error(f"[{num}] ✗ Failed to load {url}: {e}")
                pages.append({
                    "num": num,
                    "url": url,
                    "title": title,
                    "content": f"[Fehler beim Laden: {str(e)}]"
                })

        # Check if any pages loaded successfully
        successful_pages = [p for p in pages if not p['content'].startswith('[')]
        if not successful_pages:
            logger.warning("All pages failed to load")
            return f"Fehler: Alle {len(pages)} Seiten konnten nicht geladen werden.\n\n" + \
                   "\n".join([f"[{p['num']}] {p['title']}: {p['content']}" for p in pages])

        logger.info(f"Successfully loaded {len(successful_pages)}/{len(pages)} pages")

        # Check if user wants to search for something specific
        search_within_keywords = ["suche nach", "finde", "kontakt", "informationen über", "nach"]
        wants_search = any(keyword in query.lower() for keyword in search_within_keywords)

        if wants_search:
            # Extract what to search for
            extraction_prompt = f"""Extrahiere was der Nutzer in den Webseiten suchen möchte aus dieser Anfrage: "{query}"

Beispiele:
- "durchsuche quelle 2 und 3 nach kontaktinformationen" → "Kontaktinformationen"
- "finde in quelle 1, 4 und 5 die Preise" → "Preise"
- "suche nach Öffnungszeiten in quelle 2" → "Öffnungszeiten"

Gib NUR den Suchbegriff zurück."""

            search_for = self.llm.generate(
                prompt=extraction_prompt,
                system_prompt="Du extrahierst Suchbegriffe."
            ).strip()

            logger.info(f"Searching for '{search_for}' across {len(pages)} pages")

            system_prompt = f"""Du bist ein hilfreicher Assistent.
Der Nutzer möchte spezifische Informationen aus mehreren Webseiten extrahieren: {search_for}

Analysiere ALLE Webseiten und fasse die gefundenen Informationen zusammen.
Gib bei jeder Information an, von welcher Quelle sie stammt."""

            user_query_text = f"Finde {search_for} in diesen {len(pages)} Webseiten und fasse zusammen."

        else:
            # Just summarize all pages
            system_prompt = """Du bist ein hilfreicher Assistent.
Fasse die Inhalte aller Webseiten zusammen und zeige Gemeinsamkeiten und Unterschiede auf.
Gib bei jeder Information an, von welcher Quelle sie stammt."""

            user_query_text = f"Fasse diese {len(pages)} Webseiten zusammen und vergleiche sie."

        # Build context from all pages
        context_parts = []
        for page in pages:
            context_parts.append(f"═══ QUELLE [{page['num']}] ═══")
            context_parts.append(f"Titel: {page['title']}")
            context_parts.append(f"URL: {page['url']}")
            context_parts.append(f"\nInhalt:\n{page['content'][:self.context_limit_medium]}\n")  # Limit each page

        context = "\n".join(context_parts)

        final_prompt = self.context_manager.build_prompt(
            system_prompt=system_prompt,
            user_query=user_query_text,
            context=context,
            max_context_tokens=self.context_limit_xlarge  # More tokens for multiple sources
        )

        response = self.llm.generate(
            prompt=final_prompt,
            stream=self.config.get("llm", {}).get("stream", False)
        )

        # Append source reference
        reference = ["\n\n═══ Verarbeitete Quellen ═══"]
        for page in pages:
            reference.append(f"[{page['num']}] {page['url']}")
            reference.append(f"    → {page['title']}")

        return response + "\n".join(reference)

    def _is_connection_analysis(self, query: str) -> bool:
        """
        Check if query requests connection analysis between websites.

        Args:
            query: User query

        Returns:
            True if query requests connection analysis
        """
        import re
        query_lower = query.lower()

        # Check for URLs or result references
        urls = URL_PATTERN.findall(query)
        result_nums = []
        for pattern in RESULT_REFERENCE_PATTERNS[:4]:  # Use only direct number patterns
            matches = pattern.findall(query_lower)
            if matches:
                for match in matches:
                    if isinstance(match, tuple):
                        result_nums.extend([int(m) for m in match if m.isdigit()])
                    elif match.isdigit():
                        result_nums.append(int(match))

        has_targets = len(urls) >= 2 or len(result_nums) >= 2

        # Strict connection keywords (always trigger)
        strict_keywords = [
            "verbindung zwischen",
            "connection between",
            "beziehung zwischen",
            "relation between",
            "zeige mir verbindung",
            "analysiere verbindung"
        ]

        if any(keyword in query_lower for keyword in strict_keywords):
            return True

        # Weak keywords (only trigger if 2+ URLs or result numbers present)
        weak_keywords = [
            "verbindung",
            "vergleiche",
            "compare",
            "gemeinsamkeiten",
            "similarities",
            "unterschiede zwischen",
            "differences between"
        ]

        if has_targets and any(keyword in query_lower for keyword in weak_keywords):
            return True

        # Check if query has 2+ URLs and connecting words (und/and)
        if len(urls) >= 2 and (" und " in query_lower or " and " in query_lower):
            return True

        return False

    def _handle_connection_analysis(self, query: str) -> str:
        """
        Analyze connections between two websites.

        Args:
            query: User query requesting connection analysis

        Returns:
            Analysis of connections between the websites
        """
        import re
        from tools.page_reader import read_page

        # Extract URLs or result numbers
        urls_to_analyze = []

        # Check for result references (e.g., "ergebnis 1 und ergebnis 2", "quelle 1 und quelle 2")
        result_matches = RESULT_PATTERN.findall(query.lower())

        if result_matches:
            # User referenced previous search results
            result_nums = [int(num) for num in result_matches]

            if len(result_nums) < 2:
                return "Bitte geben Sie mindestens zwei Ergebnisnummern an (z.B. 'Verbindung zwischen Ergebnis 1 und Ergebnis 2')."

            # Get URLs from stored results with safe access
            for num in result_nums[:2]:  # Take first two
                try:
                    if num < 1 or num > len(self.last_search_results):
                        return f"Ergebnis {num} existiert nicht (verfügbar: 1-{len(self.last_search_results)})."
                        
                    result = self.last_search_results[num - 1]
                    urls_to_analyze.append({
                        "url": result["url"],
                        "title": result["title"],
                        "number": num
                    })
                    
                except (IndexError, TypeError, KeyError) as e:
                    logger.error(f"Error accessing result #{num}: {e}")
                    return f"Fehler beim Zugriff auf Ergebnis #{num}."

            logger.info(f"Analyzing connection between result #{result_nums[0]} and #{result_nums[1]}")

        else:
            # Extract direct URLs
            found_urls = URL_PATTERN.findall(query)

            if len(found_urls) < 2:
                return "Bitte geben Sie zwei URLs oder Ergebnisnummern an (z.B. 'Verbindung zwischen https://example1.com und https://example2.com')."

            urls_to_analyze = [
                {"url": found_urls[0], "title": found_urls[0], "number": 1},
                {"url": found_urls[1], "title": found_urls[1], "number": 2}
            ]

            logger.info(f"Analyzing connection between {found_urls[0]} and {found_urls[1]}")

        # Load both pages
        pages = []
        logger.info(f"Loading {len(urls_to_analyze[:2])} pages for connection analysis...")

        for i, item in enumerate(urls_to_analyze[:2], 1):
            try:
                logger.info(f"[{i}/2] Loading page: {item['url']}")
                content = read_page(item["url"])
                pages.append({
                    "url": item["url"],
                    "title": item["title"],
                    "content": content,
                    "number": item.get("number")
                })
                logger.info(f"[{i}/2] Successfully loaded {len(content)} characters from {item['url']}")
            except Exception as e:
                logger.error(f"Failed to load {item['url']}: {e}")
                return f"Fehler beim Laden der Seite {item['url']}: {str(e)}"

        logger.info(f"Starting connection analysis between {pages[0]['url']} and {pages[1]['url']}")

        # Analyze connections using LLM
        system_prompt = """Du bist ein Experte für Web-Analyse und Datenvergleich.
Analysiere die beiden Webseiten und finde Verbindungen, Gemeinsamkeiten und Beziehungen.

Achte besonders auf:
1. **Kontaktdaten**: Gleiche E-Mails, Telefonnummern, Adressen
2. **Personen/Namen**: Gleiche oder ähnliche Namen (Geschäftsführer, Mitarbeiter, Autoren)
3. **Firmendaten**: Firmenname, Handelsregisternummer, USt-ID
4. **Links**: Verlinkt eine Seite auf die andere? Gemeinsame externe Links?
5. **Inhalte**: Ähnliche Themen, Produkte, Dienstleistungen
6. **Technische Details**: Gleicher Hosting-Provider, gleiche IP, gleicher Server
7. **Design/Struktur**: Ähnliches Design, gleiche Vorlage/Theme

Gib eine strukturierte Analyse mit klaren Kategorien zurück."""

        analysis_query = f"""Analysiere die Verbindung zwischen diesen beiden Webseiten:

**Webseite 1:** {pages[0]['title']}
URL: {pages[0]['url']}

**Webseite 2:** {pages[1]['title']}
URL: {pages[1]['url']}

Finde alle Gemeinsamkeiten, Verbindungen und Beziehungen."""

        context = f"""=== WEBSEITE 1 ===
URL: {pages[0]['url']}
Titel: {pages[0]['title']}

Inhalt:
{pages[0]['content'][:self.context_limit_small]}

=== WEBSEITE 2 ===
URL: {pages[1]['url']}
Titel: {pages[1]['title']}

Inhalt:
{pages[1]['content'][:self.context_limit_small]}"""

        final_prompt = self.context_manager.build_prompt(
            system_prompt=system_prompt,
            user_query=analysis_query,
            context=context,
            max_context_tokens=self.context_limit_large
        )

        return self.llm.generate(
            prompt=final_prompt,
            stream=self.config.get("llm", {}).get("stream", False)
        )

    def _is_followup_question(self, query: str) -> bool:
        """
        Check if query is a follow-up question referencing previous context.

        Args:
            query: User query

        Returns:
            True if query seems to be a follow-up
        """
        query_lower = query.lower()

        # Pronouns and references that indicate follow-up
        followup_indicators = [
            r'\bdiese[rs]?\b',  # dieser, diese, dieses
            r'\b(?:er|sie|es)\b',  # er, sie, es
            r'\bihm\b', r'\bihr\b', r'\bsein\b',  # ihm, ihr, sein
            r'\bdas\b',  # das (when at start)
            r'\bwelche[rs]?\b',  # welcher, welche, welches
        ]

        import re
        for pattern in followup_indicators:
            if re.search(pattern, query_lower):
                logger.info(f"Detected follow-up question (pronoun matched: {pattern})")
                return True

        # Check if query contains names from conversation history
        if self.conversation_history:
            names = self._extract_names_from_history()
            for name in names:
                # Check if only the first name is used (e.g., "Jens" from "Jens Neumann")
                name_parts = name.split()
                for part in name_parts:
                    if len(part) > 2 and part.lower() in query_lower:
                        logger.info(f"Detected follow-up question (name matched: {part})")
                        return True

        # Short questions are often follow-ups
        words = query.split()
        if len(words) <= 5 and not any(kw in query_lower for kw in ["suche", "finde", "zeige", "search"]):
            logger.info("Detected follow-up question (short query)")
            return True

        return False

    def _extract_names_from_history(self) -> list:
        """
        Extract person names from conversation history.

        Returns:
            List of potential names
        """
        import re
        names = set()

        # Configurable blacklist
        blacklist = self.config.get("context", {}).get("name_blacklist", [
            "User", "Assistant", "System", "Der", "Die", "Das", "Ein", "Eine", "Keine", "Alle"
        ])

        for entry in self.conversation_history[-3:]:  # Last 3 conversations
            text = entry.get('query', '') + ' ' + entry.get('response', '')
            found_names = NAME_PATTERN.findall(text)
            for name in found_names:
                if name not in blacklist:
                    names.add(name)

        logger.debug(f"Extracted names from history: {names}")
        return list(names)

    def _build_conversation_context(self) -> str:
        """
        Build context string from conversation history.

        Returns:
            Formatted conversation context
        """
        if not self.conversation_history:
            return ""

        context_parts = ["Bisheriger Gesprächsverlauf:\n"]

        # Add last few Q&A pairs
        for i, entry in enumerate(self.conversation_history[-3:], 1):  # Last 3 entries
            context_parts.append(f"Frage {i}: {entry['query']}")
            context_parts.append(f"Antwort {i}: {entry['response']}\n")

        # IMPORTANT: Also include recent search results metadata if available
        # This helps answer follow-up questions about previously shown content
        if self.last_search_results:
            context_parts.append("\n═══ Verfügbare Suchergebnisse (für Referenzen) ═══")
            # Show all results (up to 15) so LLM can reference them by number
            for i, result in enumerate(self.last_search_results[:15], 1):
                title = result.get("title", "Kein Titel")
                url = result.get("url", "")
                snippet = result.get("snippet", "")[:150]  # Short snippet
                context_parts.append(f"[{i}] {title}")
                context_parts.append(f"    URL: {url}")
                if snippet:
                    context_parts.append(f"    {snippet}")

        # CRITICAL: Include cached page contents for better follow-up answers
        # This solves the "forgetting" problem - previously loaded pages are now available
        if self.loaded_pages_cache:
            context_parts.append("\n═══ Geladene Seiteninhalte (vollständiger Kontext) ═══")
            for num, page_data in sorted(self.loaded_pages_cache.items()):
                context_parts.append(f"\nQuelle [{num}]: {page_data['title']}")
                context_parts.append(f"URL: {page_data['url']}")
                context_parts.append(f"Inhalt:\n{page_data['content'][:self.context_limit_small]}")
                context_parts.append("")

        return "\n".join(context_parts)

    def _append_source_urls(self) -> str:
        """
        Append URL reference list for cited sources.

        Returns:
            Formatted URL reference guide
        """
        if not self.last_search_results:
            return ""

        reference = ["\n\n═══ Quellen-Referenz ═══"]
        for i, result in enumerate(self.last_search_results, 1):
            title = result.get("title", "Kein Titel")
            url = result.get("url", "")
            reference.append(f"[{i}] {url}")
            reference.append(f"    → {title}")

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
            return "Keine Suchergebnisse gefunden."

        formatted = ["Suchergebnisse:\n"]
        for i, result in enumerate(results, 1):
            title = result.get("title", "Kein Titel")
            url = result.get("url", "")
            snippet = result.get("snippet", "")

            formatted.append(f"[{i}] {title}")
            formatted.append(f"    URL: {url}")
            formatted.append(f"    {snippet}\n")

        return "\n".join(formatted)

    def clear_session(self) -> Dict[str, int]:
        """
        Clear all session data (conversation history, search results, cache).

        Returns:
            Dictionary with cleared counts
        """
        stats = {
            "conversation_entries": len(self.conversation_history),
            "search_results": len(self.last_search_results),
            "cache_files": 0
        }

        # Clear conversation history
        self.conversation_history = []

        # Clear search results
        self.last_search_results = []
        self.last_search_query = ""

        # Clear loaded pages cache
        self.loaded_pages_cache = {}

        # Clear last content
        self.last_content = {
            "type": None,
            "subject": None,
            "summary": None
        }

        # Clear cache
        if self.cache:
            stats["cache_files"] = self.cache.clear()

        logger.info(f"Session cleared: {stats}")

        # Delete session file
        if self.session_file.exists():
            self.session_file.unlink()
            logger.info("Session file deleted")

        return stats

    def save_session(self) -> bool:
        """
        Save current session to file.

        Returns:
            True if successful
        """
        try:
            session_data = {
                "timestamp": datetime.now().isoformat(),
                "conversation_history": self.conversation_history,
                "last_search_results": self.last_search_results,
                "last_search_query": self.last_search_query,
                "loaded_pages_cache": self.loaded_pages_cache,  # Save cached pages
                "last_content": self.last_content
            }

            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Session saved to {self.session_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return False

    def load_session(self) -> bool:
        """
        Load session from file.

        Returns:
            True if session was loaded
        """
        if not self.session_file.exists():
            logger.info("No previous session found")
            return False

        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                session_data = json.load(f)

            # Restore session state
            self.conversation_history = session_data.get("conversation_history", [])
            self.last_search_results = session_data.get("last_search_results", [])
            self.last_search_query = session_data.get("last_search_query", "")
            self.loaded_pages_cache = session_data.get("loaded_pages_cache", {})  # Restore cached pages
            self.last_content = session_data.get("last_content", {
                "type": None,
                "subject": None,
                "summary": None
            })

            timestamp = session_data.get("timestamp", "unknown")
            logger.info(f"Session loaded from {timestamp}")
            logger.info(f"Restored: {len(self.conversation_history)} conversation entries, "
                       f"{len(self.last_search_results)} search results")

            return True

        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False

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

    def _is_osint_query(self, query: str) -> bool:
        """
        Check if query contains OSINT operators.

        Args:
            query: User query

        Returns:
            True if OSINT operators detected
        """
        from core.osint import OSINTQueryParser

        parser = OSINTQueryParser()
        return parser.is_osint_query(query)

    def _handle_osint_query(self, query: str) -> str:
        """
        Handle OSINT query with operators.
        Refactored: Main orchestrator method (reduced from 295 to ~40 lines).
        """
        # Initialize components
        components = self._initialize_osint_components()
        if isinstance(components, str):  # Error message
            return components

        parser, email_intel, phone_intel, enhancer, compliance = components
        logger.info(f"OSINT query detected: {query}")

        # Check compliance
        compliance_result = self._check_osint_compliance(compliance, query)
        if compliance_result:  # Error message
            return compliance_result

        # Parse query
        parsed = self._parse_osint_query(parser, query)
        if isinstance(parsed, str):  # Error message
            return parsed

        logger.info(f"Parsed OSINT query: {parsed}")
        response_parts = []

        # Process email intelligence
        if parsed.email and email_intel:
            email_parts = self._process_email_intelligence(parsed.email, email_intel)
            response_parts.extend(email_parts)

        # Process phone intelligence
        if parsed.phone and phone_intel:
            phone_parts = self._process_phone_intelligence(parsed.phone, phone_intel)
            response_parts.extend(phone_parts)

        # Process advanced search operators
        if parsed.site or parsed.inurl or parsed.intext or parsed.intitle or parsed.filetype:
            search_parts = self._process_advanced_search(parser, parsed, query)
            response_parts.extend(search_parts)

        # AI suggestions
        if not (parsed.email or parsed.phone) and enhancer:
            ai_parts = self._generate_ai_suggestions(enhancer, query)
            response_parts.extend(ai_parts)

        if not response_parts:
            response_parts.append("Keine OSINT-Operatoren erkannt oder verarbeitet.")

        # Add usage stats
        stats_parts = self._append_usage_stats(compliance)
        response_parts.extend(stats_parts)

        return "\n".join(response_parts)

    def _initialize_osint_components(self):
        """Initialize all OSINT components with error handling."""
        try:
            from core.osint import (
                OSINTQueryParser,
                EmailIntelligence,
                PhoneIntelligence,
                QueryEnhancer,
                OSINTCompliance
            )
        except ImportError as e:
            logger.error(f"Failed to import OSINT modules: {e}")
            return "⚠️ OSINT features sind nicht verfügbar. Module fehlen."

        success, parser = safe_execute(OSINTQueryParser, default=None, log_error=True)
        if not success or not parser:
            return "⚠️ OSINT Parser konnte nicht initialisiert werden."

        success, email_intel = safe_execute(EmailIntelligence, default=None, log_error=True)
        success, phone_intel = safe_execute(PhoneIntelligence, default=None, log_error=True)
        success, enhancer = safe_execute(QueryEnhancer, self.llm, default=None, log_error=False)
        success, compliance = safe_execute(OSINTCompliance, config=self.config, default=None, log_error=True)

        if not compliance:
            return "⚠️ OSINT Compliance konnte nicht initialisiert werden."

        return (parser, email_intel, phone_intel, enhancer, compliance)

    def _check_osint_compliance(self, compliance, query: str):
        """Check OSINT compliance and return error message if blocked."""
        success, (allowed, reason) = safe_execute(
            compliance.check_query,
            query,
            "default",
            "general_osint",
            default=(False, "Compliance check failed"),
            log_error=True
        )

        if not success or not allowed:
            logger.warning(f"OSINT query blocked: {reason}")
            if "terms of use" in reason.lower():
                return ("⚠️ OSINT Features müssen erst aktiviert werden.\n\n"
                       "Starten Sie CrawlLama neu, um die Terms zu akzeptieren, oder akzeptieren Sie "
                       "die Terms manuell in der Konfiguration.")
            return f"⚠️ OSINT Query blockiert: {reason}"
        return None

    def _parse_osint_query(self, parser, query: str):
        """Parse OSINT query and return parsed object or error message."""
        success, parsed = safe_execute(
            parser.parse,
            query,
            default=None,
            log_error=True
        )
        if not success or not parsed:
            return f"⚠️ Fehler beim Parsen der OSINT Query: {query}"
        return parsed

    def _process_email_intelligence(self, email: str, email_intel) -> list:
        """Process email intelligence and return response parts."""
        logger.info(f"Processing email intelligence: {email}")
        response_parts = []

        success, email_result = safe_execute(
            email_intel.analyze_email,
            email,
            default={'valid': False, 'email': email},
            log_error=True
        )

        if not success or not email_result:
            response_parts.append("⚠️ Email-Analyse fehlgeschlagen.")
            return response_parts

        # Format email results
        response_parts.extend(self._format_email_results(email_result, email))

        # Search email online if valid
        if email_result.get('valid'):
            online_parts = self._search_email_online(email)
            response_parts.extend(online_parts)

        return response_parts

    def _format_email_results(self, email_result: dict, email: str) -> list:
        """Format email analysis results."""
        parts = ["═══ Email Intelligence ═══\n"]
        parts.append(f"**Email:** {email_result.get('email', email)}")
        parts.append(f"**Valid:** {'✓' if email_result.get('valid') else '✗'} {email_result.get('valid', False)}")

        if email_result.get('valid'):
            parts.append(f"**Domain:** {email_result['domain']}")
            parts.append(f"**Username:** {email_result['username']}")
            parts.append(f"**Disposable:** {email_result['disposable']}")
            parts.append(f"**Domain exists:** {email_result['domain_exists']}")
            parts.append(f"**Confidence:** {email_result['confidence']:.2f}")

            if email_result.get('variations'):
                parts.append(f"\n**Email Variations:**")
                for var in email_result['variations'][:5]:
                    parts.append(f"  • {var}")

        return parts

    def _search_email_online(self, email: str) -> list:
        """Search for email mentions online."""
        from tools.web_search import web_search

        response_parts = [f"\n═══ Online Search Results ═══\n"]
        logger.info(f"Searching web for email: {email}")

        # Extract domain for more targeted searches
        domain = email.split('@')[1] if '@' in email else ""

        search_config = self.config.get("search", {})
        region = search_config.get("region", "de-de")

        # Build search queries - prioritize domain-specific searches
        search_queries = []

        # Priority 1: Search on the email's own domain (most relevant for business emails)
        if domain:
            search_queries.append(f'site:{domain} "{email}"')
            search_queries.append(f'site:{domain} kontakt OR impressum')  # German context

        # Priority 2: Exact email search with quotes
        search_queries.append(f'"{email}"')

        # Priority 3: Social/professional networks (region-specific)
        if domain.endswith('.de'):
            # German-specific networks first
            search_queries.extend([
                f'site:xing.de "{email}"',
                f'site:linkedin.com/in "{email}"',
                f'site:github.com "{email}"',
            ])
        else:
            # International networks
            search_queries.extend([
                f'site:linkedin.com/in "{email}"',
                f'site:github.com "{email}"',
                f'site:twitter.com "{email}"',
            ])

        # Get safesearch setting
        osint_config = self.config.get("osint", {})
        safesearch = osint_config.get("safesearch", "strict")

        # Execute searches and collect results
        all_results = []
        for search_query in search_queries:
            success, results = safe_execute(
                web_search,
                search_query,
                max_results=3,
                region=region,
                safesearch=safesearch,
                default=[],
                log_error=False
            )
            if success and results:
                all_results.extend(results)

        # Deduplicate by URL
        unique_results = self._deduplicate_results(all_results)

        # Store results in session for quelle/source commands
        if unique_results:
            self.last_search_results = unique_results
            self.last_search_query = f'email:{email}'
            logger.info(f"Stored {len(unique_results)} email search results in session state")

        # Format results
        if unique_results:
            response_parts.append(f"**Found {len(unique_results)} mentions online:**\n")
            for i, result in enumerate(unique_results[:10], 1):
                response_parts.append(f"[{i}] **{result.get('title', 'No Title')}**")
                response_parts.append(f"    URL: {result.get('url', '')}")
                if result.get('snippet'):
                    snippet = result.get('snippet', '')[:250]
                    response_parts.append(f"    {snippet}...")
                response_parts.append("")
        else:
            response_parts.append("**No public mentions found.**")
            response_parts.append("This email may be private or not publicly indexed.")

        return response_parts

    def _process_phone_intelligence(self, phone: str, phone_intel) -> list:
        """Process phone intelligence and return response parts."""
        logger.info(f"Processing phone intelligence: {phone}")
        phone_result = phone_intel.analyze_phone(phone)

        response_parts = ["\n═══ Phone Intelligence ═══\n"]
        response_parts.append(f"**Phone:** {phone_result['input']}")
        response_parts.append(f"**Valid:** {'✓' if phone_result['valid'] else '✗'} {phone_result['valid']}")

        if phone_result['valid']:
            response_parts.extend(self._format_phone_results(phone_result))
            online_parts = self._search_phone_online(phone_result)
            response_parts.extend(online_parts)

        return response_parts

    def _format_phone_results(self, phone_result: dict) -> list:
        """Format phone analysis results."""
        parts = []
        parts.append(f"**Formatted:** {phone_result['formatted']}")
        parts.append(f"**Country:** {phone_result['country']}")
        parts.append(f"**Type:** {phone_result['type']}")
        if phone_result.get('carrier'):
            parts.append(f"**Carrier:** {phone_result['carrier']}")
        parts.append(f"**Confidence:** {phone_result['confidence']:.2f}")

        if phone_result.get('variations'):
            parts.append(f"\n**Phone Variations:**")
            for var in phone_result['variations'][:5]:
                parts.append(f"  • {var}")

        return parts

    def _search_phone_online(self, phone_result: dict) -> list:
        """Search for phone number mentions online."""
        from tools.web_search import web_search

        response_parts = [f"\n═══ Online Search Results ═══\n"]
        logger.info(f"Searching web for phone: {phone_result['input']}")

        search_config = self.config.get("search", {})
        osint_config = self.config.get("osint", {})
        safesearch = osint_config.get("safesearch", "strict")
        search_queries = [f'"{var}"' for var in phone_result['variations'][:3]]

        # Execute searches
        all_results = []
        for search_query in search_queries:
            success, results = safe_execute(
                web_search,
                search_query,
                max_results=3,
                region=search_config.get("region", "de-de"),
                safesearch=safesearch,
                default=[],
                log_error=False
            )
            if success and results:
                all_results.extend(results)

        # Deduplicate
        unique_results = self._deduplicate_results(all_results)

        # Store results in session for quelle/source commands
        if unique_results:
            self.last_search_results = unique_results
            self.last_search_query = f'phone:{phone_result["input"]}'
            logger.info(f"Stored {len(unique_results)} phone search results in session state")

        # Format results
        if unique_results:
            response_parts.append(f"**Found {len(unique_results)} mentions online:**\n")
            for i, result in enumerate(unique_results[:10], 1):
                response_parts.append(f"[{i}] **{result.get('title', 'No Title')}**")
                response_parts.append(f"    URL: {result.get('url', '')}")
                if result.get('snippet'):
                    snippet = result.get('snippet', '')[:250]
                    response_parts.append(f"    {snippet}...")
                response_parts.append("")
        else:
            response_parts.append("**No public mentions found.**")
            response_parts.append("This phone number may be private or not publicly listed.")

        return response_parts

    def _deduplicate_results(self, results: list) -> list:
        """Remove duplicate results by URL."""
        seen_urls = set()
        unique_results = []
        for result in results:
            url = result.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        return unique_results

    def _process_advanced_search(self, parser, parsed, query: str) -> list:
        """Process advanced search operators."""
        response_parts = ["\n═══ Advanced Search Query ═══\n"]
        response_parts.append(f"**Original:** {query}")
        response_parts.append(f"**Parsed:**")

        if parsed.site:
            response_parts.append(f"  • Site: {parsed.site}")
        if parsed.inurl:
            response_parts.append(f"  • In URL: {parsed.inurl}")
        if parsed.intext:
            response_parts.append(f"  • In Text: {parsed.intext}")
        if parsed.intitle:
            response_parts.append(f"  • In Title: {parsed.intitle}")
        if parsed.filetype:
            response_parts.append(f"  • File Type: {parsed.filetype}")
        if parsed.exclude:
            response_parts.append(f"  • Exclude: {', '.join(parsed.exclude)}")

        # Build and execute search
        search_query = parser.build_search_query(parsed)
        response_parts.append(f"\n**Optimized Search Query:**\n`{search_query}`")

        search_results_parts = self._execute_osint_search(search_query, parsed)
        response_parts.extend(search_results_parts)

        return response_parts

    def _execute_osint_search(self, search_query: str, parsed) -> list:
        """Execute OSINT search and format results."""
        from tools.web_search import web_search

        response_parts = []
        osint_config = self.config.get("osint", {})
        search_config = self.config.get("search", {})
        max_results = osint_config.get("max_results", 25)
        # Default region is "de-de" (Germany) to avoid irrelevant international results
        region = search_config.get("region", "de-de")
        safesearch = osint_config.get("safesearch", "strict")  # Default: strict for better quality

        logger.info(f"Executing OSINT search: {search_query} (max_results={max_results}, region={region}, safesearch={safesearch})")
        results = web_search(search_query, max_results=max_results, region=region, safesearch=safesearch)

        if results:
            # Store in session
            self.last_search_results = results
            self.last_search_query = search_query
            logger.info(f"Stored {len(results)} OSINT search results in session state")

            response_parts.append(f"\n**Search Results:**")
            for i, result in enumerate(results[:max_results], 1):
                response_parts.append(f"\n[{i}] **{result.get('title', 'No Title')}**")
                response_parts.append(f"    {result.get('url', '')}")
                if result.get('snippet'):
                    response_parts.append(f"    {result.get('snippet', '')[:200]}...")

        return response_parts

    def _generate_ai_suggestions(self, enhancer, query: str) -> list:
        """Generate AI suggestions for the query."""
        response_parts = []
        try:
            entity_type = enhancer.identify_entity_type(query)
            response_parts.append(f"\n═══ AI Analysis ═══\n")
            response_parts.append(f"**Entity Type:** {entity_type}")

            variations = enhancer.generate_variations(query, max_variations=3)
            if variations:
                response_parts.append(f"\n**Alternative Queries:**")
                for var in variations:
                    response_parts.append(f"  • {var}")
        except Exception as e:
            logger.debug(f"AI suggestions skipped: {e}")

        return response_parts

    def _append_usage_stats(self, compliance) -> list:
        """Append usage statistics to response."""
        stats = compliance.get_usage_stats("default")
        parts = [
            f"\n\n═══ Usage Stats ═══",
            f"Queries this hour: {stats['total_requests_last_hour']}",
            f"Remaining limits:",
            f"  • Email: {stats['remaining_limits']['email_search']}/50",
            f"  • Phone: {stats['remaining_limits']['phone_search']}/50",
            f"  • General: {stats['remaining_limits']['general_osint']}/100"
        ]
        return parts

    def _check_llm_health(self) -> bool:
        """
        Check if LLM is healthy and responsive.

        Returns:
            True if LLM is healthy, False otherwise
        """
        try:
            # Simple health check - try to generate a short response
            test_response = self.llm.generate(
                prompt="Test",
                system_prompt="Respond with 'OK'."
            )
            return bool(test_response and len(test_response) > 0)
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False
