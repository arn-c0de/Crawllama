"""Main agent for orchestrating tools and LLM interactions."""
import logging
import json
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime
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

        # Session file path
        self.session_file = Path("data/session.json")
        self.session_file.parent.mkdir(parents=True, exist_ok=True)

        # Session state for search results
        self.last_search_results = []
        self.last_search_query = ""

        # Conversation history for context
        self.conversation_history = []
        self.max_history = 10  # Keep last 10 Q&A pairs (increased for RTX 3080 16k context)

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
            max_tokens=llm_config.get("max_tokens", 4096)
        )

        context_config = config.get("security", {})
        self.context_manager = ContextManager(
            max_tokens=context_config.get("max_context_length", 16000)  # Increased default for RTX 3080
        )

        cache_config = config.get("cache", {})
        self.cache = CacheManager(
            cache_dir="data/cache",
            ttl_hours=cache_config.get("ttl_hours", 24)
        ) if cache_config.get("enabled", True) else None

        rag_config = config.get("rag", {})
        self.tool_registry = ToolRegistry(
            rag_enabled=rag_config.get("enabled", True),
            config=config
        )

        self.tools = self.tool_registry.get_tools() if enable_web else []

        logger.info(f"Agent initialized (web: {enable_web}, tools: {len(self.tools)})")

        # Auto-load previous session if exists
        self.load_session()

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

        # Check if query starts with '<' - force context-only mode
        force_context_mode = False
        if user_query.strip().startswith('<'):
            force_context_mode = True
            user_query = user_query.strip()[1:].strip()  # Remove '<' and clean up
            logger.info(f"Context-only mode activated (< prefix). Query: '{user_query}'")

        # Check cache first (but NOT for context-only mode to avoid stale responses)
        if self.cache and not force_context_mode:
            cached_response = self.cache.get(user_query)
            if cached_response:
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

            # Update conversation history
            self.conversation_history.append({
                "query": user_query,
                "response": response[:4000]  # Store more context for follow-up questions (increased for 16k context)
            })

            # Keep only last N entries
            if len(self.conversation_history) > self.max_history:
                self.conversation_history = self.conversation_history[-self.max_history:]

            # Cache the response (but NOT for context-only mode to avoid polluting cache)
            if self.cache and not force_context_mode:
                self.cache.set(user_query, response)

            # Auto-save session after each query
            self.save_session()

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
        # Check if this is a follow-up question
        is_followup = self._is_followup_question(user_query)

        # Build context from conversation history
        context = ""
        if is_followup and self.conversation_history:
            context = self._build_conversation_context()

        system_prompt = """Du bist ein hilfreicher Assistent.
Beantworte Fragen präzise und informativ auf Deutsch.

Wenn die Frage sich auf einen vorherigen Kontext bezieht (z.B. "dieser", "er", "sie"),
nutze die Informationen aus dem Gesprächsverlauf."""

        prompt = self.context_manager.build_prompt(
            system_prompt=system_prompt,
            user_query=user_query,
            context=context
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
        import re

        # Step 1: Check if query contains URLs
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, user_query)

        context = ""

        # Priority 1: Connection analysis (2+ URLs or connection keywords)
        if self._is_connection_analysis(user_query) or (len(urls) >= 2):
            return self._handle_connection_analysis(user_query)

        # Priority 2: Single URL processing
        elif len(urls) == 1:
            # If single URL is present, use read_page tool
            logger.info(f"URL detected: {urls[0]}")
            read_page_tool = next((t for t in self.tools if t.name == "read_page"), None)
            if read_page_tool:
                logger.info(f"Using read_page tool for: {urls[0]}")
                context = read_page_tool.func(urls[0])

        # Priority 3: Check if user references a previous search result
        elif self._is_result_reference(user_query):
            return self._handle_result_reference(user_query)

        else:
            # Step 2: Check for explicit search keywords
            query_lower = user_query.lower()
            web_search_keywords = [
                "suche im internet", "suche nach", "search for", "google",
                "web search", "find online", "search online", "look up online",
                "internet search", "web suche", "online suchen"
            ]
            wiki_keywords = ["wikipedia", "wiki", "enzyklopädie"]

            tool_to_use = None

            # Force web_search if explicit keywords found
            if any(keyword in query_lower for keyword in web_search_keywords):
                tool_to_use = "web_search"
                logger.info(f"Selected tool (keyword match): {tool_to_use}")
            elif any(keyword in query_lower for keyword in wiki_keywords):
                tool_to_use = "wiki_lookup"
                logger.info(f"Selected tool (keyword match): {tool_to_use}")
            else:
                # Step 2b: Decide if tools are needed
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

                # Step 3: Let LLM determine which tool to use
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

                logger.info(f"Selected tool (LLM decision): {tool_to_use}")

            # Step 4: Extract search query from user input with context
            # Check if query references names from history
            context_hint = ""
            if self.conversation_history:
                names = self._extract_names_from_history()
                if names:
                    context_hint = f"\nKONTEXT: In der vorherigen Konversation wurden diese Namen/Personen erwähnt: {', '.join(names[:3])}"

            extraction_prompt = f"""Extrahiere den EIGENTLICHEN SUCHBEGRIFF aus dieser Anfrage: "{user_query}"
{context_hint}

Beispiele:
- "google nach Python Tutorial" → "Python Tutorial"
- "finde Informationen über Berlin" → "Berlin"
- "was ist Photosynthese" → "Photosynthese"
- Wenn KONTEXT vorhanden: "was macht er beruflich" + KONTEXT "Max Müller" → "Max Müller Beruf"

Gib NUR den Suchbegriff zurück, nichts anderes."""

            search_query = self.llm.generate(
                prompt=extraction_prompt,
                system_prompt="Du bist ein Experte für Suchbegriff-Extraktion. Nutze den Kontext wenn vorhanden."
            ).strip().strip('"').strip("'")

            logger.info(f"Extracted search query: '{search_query}' from '{user_query}' (with context: {bool(context_hint)})")

            # Step 5: Use the selected tool
            if "web_search" in tool_to_use:
                from tools.web_search import web_search
                search_config = self.config.get("search", {})
                max_results = search_config.get("max_results", 10)
                region = search_config.get("region", "de-de")

                # Get raw search results
                results = web_search(search_query, max_results=max_results, region=region)

                # Debug: Log first result to see structure
                if results:
                    logger.info(f"Sample result: title='{results[0].get('title', 'N/A')}', url='{results[0].get('url', 'EMPTY')}'")

                # Store results in session state
                self.last_search_results = results
                self.last_search_query = search_query
                logger.info(f"Stored {len(results)} search results in session state")

                # Format results with numbered list and URLs
                context = self._format_search_results_with_links(results)

            elif "wiki" in tool_to_use:
                wiki_tool = next((t for t in self.tools if t.name == "wiki_lookup"), None)
                if wiki_tool:
                    context = wiki_tool.func(search_query)

            elif "rag" in tool_to_use:
                rag_tool = next((t for t in self.tools if t.name == "rag_search"), None)
                if rag_tool:
                    context = rag_tool.func(search_query)

        # Step 6: Generate answer with context
        system_prompt = """Du bist ein hilfreicher Assistent.
Nutze die bereitgestellten Informationen um die Frage zu beantworten.

WICHTIG: Wenn du Quellen zitierst, gib IMMER die vollständige URL an!
Format: [Nummer] URL - Beschreibung

Beispiel:
Quellen:
• [1] https://example.com - Offizielle Website
• [3] https://example2.com - Fachinformationen"""

        final_prompt = self.context_manager.build_prompt(
            system_prompt=system_prompt,
            user_query=user_query,
            context=context,
            max_context_tokens=4000  # Increased for RTX 3080 16k context
        )

        response = self.llm.generate(
            prompt=final_prompt,
            stream=self.config.get("llm", {}).get("stream", False)
        )

        # Post-process: Always add URL reference if search results exist
        if self.last_search_results:
            response += self._append_source_urls()

        return response

    def _is_result_reference(self, query: str) -> bool:
        """
        Check if query references a previous search result.

        Args:
            query: User query

        Returns:
            True if query references a result (e.g., "ergebnis 1", "result 2", "quelle 3", "quellen 2, 3, 5")
        """
        import re
        query_lower = query.lower()

        # Pattern: ergebnis/result/quelle/source (singular or plural) followed by number(s)
        patterns = [
            r'\bergebnisse?\s+(\d+)\b',  # ergebnis OR ergebnisse + number
            r'\bresults?\s+(\d+)\b',      # result OR results + number
            r'\bquellen?\s+(\d+)\b',      # quelle OR quellen + number
            r'\bsources?\s+(\d+)\b',      # source OR sources + number
            r'\b(\d+)\.\s*ergebnisse?\b',
            r'\b(\d+)\.\s*results?\b',
            r'\b(\d+)\.\s*quellen?\b',
            r'\b(\d+)\.\s*sources?\b',
            # With colon: "quellen: 1, 2, 3" or "quelle: 1"
            r'\bquellen?:\s*\d+',
            r'\bergebnisse?:\s*\d+',
            r'\bresults?:\s*\d+',
            r'\bsources?:\s*\d+',
            # Commands like "durchsuche quelle/quellen"
            r'\bdurchsuche\s+quellen?\b',
            r'\bsuche\s+in\s+quellen?\b',
            r'\bsuche\s+quellen?\b',
            # Analysis commands with sources
            r'\banalysiere\s+.*quellen?\b',
            r'\bfasse.*zusammen\s+.*quellen?\b',
            r'\bvergleiche\s+.*quellen?\b',
            # "in quelle/quellen X" patterns
            r'\bin\s+quellen?\s+(\d+)\b',
            r'\bin\s+ergebnisse?\s+(\d+)\b'
        ]

        for pattern in patterns:
            if re.search(pattern, query_lower):
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
        import re

        # Extract all result numbers from the query
        query_lower = query.lower()

        # Find all numbers that appear with result/quelle/source keywords
        all_nums = []

        # Pattern 1a: "quelle 2", "ergebnis 3", "quellen 5", etc. (with space)
        pattern1a = r'(?:quellen?|ergebnisse?|results?|sources?)\s+(\d+)'
        all_nums.extend([int(m) for m in re.findall(pattern1a, query_lower)])

        # Pattern 1b: "quellen: 1", "quelle: 2", etc. (with colon)
        pattern1b = r'(?:quellen?|ergebnisse?|results?|sources?):\s*(\d+)'
        all_nums.extend([int(m) for m in re.findall(pattern1b, query_lower)])

        # Pattern 2: Check if query contains plural forms or colon, which usually means multiple numbers follow
        plural_keywords = ['quellen', 'ergebnisse', 'results', 'sources']
        has_plural = any(kw in query_lower for kw in plural_keywords)
        has_colon = ':' in query_lower and any(kw + ':' in query_lower for kw in plural_keywords + ['quelle', 'ergebnis', 'result', 'source'])

        # If plural form, colon format, OR we already found keyword-based numbers, extract all bare numbers
        if has_plural or has_colon or all_nums:
            # Look for all bare numbers in the query
            pattern2 = r'\b(\d+)\b'
            potential_nums = [int(m) for m in re.findall(pattern2, query_lower)]
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

        # Validate all numbers
        invalid_nums = [num for num in result_nums if num < 1 or num > len(self.last_search_results)]
        if invalid_nums:
            return f"Ergebnisse {invalid_nums} existieren nicht. Es gibt nur {len(self.last_search_results)} Ergebnisse."

        # Handle multiple results
        if len(result_nums) > 1:
            logger.info(f"Processing multiple results: {result_nums}")
            return self._handle_multiple_results(query, result_nums)

        # Single result - keep original behavior
        result_num = result_nums[0]
        result = self.last_search_results[result_num - 1]
        url = result.get("url", "")
        title = result.get("title", "")

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
                "content": page_content[:8000]  # Store up to 8000 chars for context (increased for 16k)
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
                max_context_tokens=6000  # Increased for RTX 3080 16k context
            )
        else:
            # Just summarize the page
            system_prompt = """Du bist ein hilfreicher Assistent.
Fasse den Inhalt dieser Webseite zusammen."""

            final_prompt = self.context_manager.build_prompt(
                system_prompt=system_prompt,
                user_query=f"Fasse die Webseite zusammen: {title}",
                context=f"Webseite: {url}\n\nInhalt:\n{page_content}",
                max_context_tokens=6000  # Increased for RTX 3080 16k context
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

        # Load all pages
        pages = []
        for num in result_nums:
            result = self.last_search_results[num - 1]
            url = result.get("url", "")
            title = result.get("title", "")

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
                        "content": content[:8000]  # Increased for 16k context
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
            context_parts.append(f"\nInhalt:\n{page['content'][:6000]}\n")  # Limit each to 6000 chars (increased for 16k)

        context = "\n".join(context_parts)

        final_prompt = self.context_manager.build_prompt(
            system_prompt=system_prompt,
            user_query=user_query_text,
            context=context,
            max_context_tokens=12000  # More tokens for multiple sources (increased for 16k)
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

        # Explicit connection keywords
        keywords = [
            "verbindung zwischen",
            "verbindung",
            "connection between",
            "vergleiche",
            "compare",
            "gemeinsamkeiten",
            "similarities",
            "unterschiede zwischen",
            "differences between",
            "beziehung zwischen",
            "relation between",
            "zeige mir verbindung",
            "analysiere verbindung"
        ]

        # Check for explicit keywords
        if any(keyword in query_lower for keyword in keywords):
            return True

        # Check if query has 2+ URLs and connecting words (und/and)
        url_pattern = r'https?://[^\s]+'
        urls = re.findall(url_pattern, query)

        if len(urls) >= 2:
            # Check for "und" or "and" between URLs
            if " und " in query_lower or " and " in query_lower:
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
        result_pattern = r'\bergebnis\s+(\d+)\b|\bresult\s+(\d+)\b|\bquelle\s+(\d+)\b|\bsource\s+(\d+)\b'
        result_matches = re.findall(result_pattern, query.lower())

        if result_matches:
            # User referenced previous search results
            result_nums = []
            for match in result_matches:
                # Extract number from any of the 4 groups (ergebnis, result, quelle, source)
                num = int(match[0] or match[1] or match[2] or match[3])
                result_nums.append(num)

            if len(result_nums) < 2:
                return "Bitte geben Sie mindestens zwei Ergebnisnummern an (z.B. 'Verbindung zwischen Ergebnis 1 und Ergebnis 2')."

            # Get URLs from stored results
            for num in result_nums[:2]:  # Take first two
                if num < 1 or num > len(self.last_search_results):
                    return f"Ergebnis {num} existiert nicht."
                result = self.last_search_results[num - 1]
                urls_to_analyze.append({
                    "url": result["url"],
                    "title": result["title"],
                    "number": num
                })

            logger.info(f"Analyzing connection between result #{result_nums[0]} and #{result_nums[1]}")

        else:
            # Extract direct URLs
            url_pattern = r'https?://[^\s,]+'
            found_urls = re.findall(url_pattern, query)

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
{pages[0]['content'][:4000]}

=== WEBSEITE 2 ===
URL: {pages[1]['url']}
Titel: {pages[1]['title']}

Inhalt:
{pages[1]['content'][:4000]}"""

        final_prompt = self.context_manager.build_prompt(
            system_prompt=system_prompt,
            user_query=analysis_query,
            context=context,
            max_context_tokens=8000  # Increased for RTX 3080 16k context
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

        for entry in self.conversation_history[-3:]:  # Last 3 conversations
            # Look for capitalized words (potential names)
            # Pattern: 2-3 capitalized words in a row
            text = entry.get('query', '') + ' ' + entry.get('response', '')

            # Find patterns like "Jens Neumann" or "Herr Müller"
            name_pattern = r'\b([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+){0,2})\b'
            found_names = re.findall(name_pattern, text)

            for name in found_names:
                # Filter out common words that aren't names
                if name not in ['Der', 'Die', 'Das', 'Ein', 'Eine', 'Keine', 'Alle']:
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
            for i, result in enumerate(self.last_search_results[:5], 1):  # Show first 5
                title = result.get("title", "Kein Titel")
                snippet = result.get("snippet", "")[:200]  # Short snippet
                context_parts.append(f"[{i}] {title}")
                if snippet:
                    context_parts.append(f"    {snippet}")

        # CRITICAL: Include cached page contents for better follow-up answers
        # This solves the "forgetting" problem - previously loaded pages are now available
        if self.loaded_pages_cache:
            context_parts.append("\n═══ Geladene Seiteninhalte (vollständiger Kontext) ═══")
            for num, page_data in sorted(self.loaded_pages_cache.items()):
                context_parts.append(f"\nQuelle [{num}]: {page_data['title']}")
                context_parts.append(f"URL: {page_data['url']}")
                context_parts.append(f"Inhalt:\n{page_data['content'][:4000]}")  # First 4000 chars (increased for 16k)
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
