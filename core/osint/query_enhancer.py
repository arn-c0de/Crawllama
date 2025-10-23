"""AI-Powered Query Enhancement for OSINT.

Uses LLM to:
- Generate query variations and synonyms
- Suggest appropriate search operators
- Expand search context
- Identify relevant sources
"""

import logging
from typing import List, Dict, Optional
from core.llm_client import OllamaClient

logger = logging.getLogger("crawllama")


class QueryEnhancer:
    """Use AI to enhance and expand OSINT queries."""

    def __init__(self, llm_client: OllamaClient):
        """
        Initialize query enhancer.

        Args:
            llm_client: Ollama LLM client
        """
        self.llm = llm_client
        logger.info("Query Enhancer initialized")

    def generate_variations(self, query: str, max_variations: int = 5) -> List[str]:
        """
        Generate query variations for better coverage.

        Args:
            query: Original query
            max_variations: Maximum variations to generate

        Returns:
            List of query variations

        Example:
            >>> enhancer = QueryEnhancer(llm_client)
            >>> variations = enhancer.generate_variations("John Doe security researcher")
            >>> len(variations) > 0
            True
        """
        logger.info(f"Generating query variations for: {query}")

        prompt = f"""Generiere {max_variations} alternative Suchanfragen für die OSINT-Recherche zu:
"{query}"

Nutze dabei:
- Synonyme und verwandte Begriffe
- Alternative Formulierungen
- Erweiterte Kontexte (z.B. berufliche Titel, Organisationen)
- Spezifischere oder breitere Begriffe

Antworte NUR mit den Varianten, eine pro Zeile. Keine Nummerierung oder Erklärungen.

Beispiel für Input "Max Mustermann Software Engineer":
Max Mustermann Entwickler
Max Mustermann Programmierer
Max Mustermann Tech Lead
Max Mustermann Software Developer
Mustermann Software Engineering

Jetzt für: "{query}"
"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                system_prompt="Du bist ein OSINT-Experte der Suchstrategien optimiert."
            )

            # Parse variations
            variations = []
            for line in response.split('\n'):
                line = line.strip()
                # Remove numbering (1., 2., -, etc.)
                line = line.lstrip('0123456789.-) ')
                if line and line != query:
                    variations.append(line)

            variations = variations[:max_variations]
            logger.info(f"Generated {len(variations)} query variations")

            return variations

        except Exception as e:
            logger.error(f"Failed to generate variations: {e}")
            return []

    def suggest_operators(self, query: str) -> Dict[str, str]:
        """
        Suggest appropriate search operators for query.

        Args:
            query: Search query

        Returns:
            Dictionary with operator suggestions and reasoning

        Example:
            >>> enhancer = QueryEnhancer(llm_client)
            >>> ops = enhancer.suggest_operators("find John Doe LinkedIn")
            >>> 'site' in ops
            True
        """
        logger.info(f"Suggesting operators for: {query}")

        prompt = f"""Analysiere diese OSINT-Suchanfrage: "{query}"

Welche Suchoperatoren würden die Suche verbessern?

Verfügbare Operatoren:
- site: (spezifische Domain, z.B. site:linkedin.com)
- inurl: (Text in URL, z.B. inurl:profile)
- intext: (Text im Seiteninhalt, z.B. intext:"email")
- intitle: (Text im Seitentitel, z.B. intitle:"about")
- filetype: (Dateityp, z.B. filetype:pdf)

Antworte im Format (OHNE zusätzlichen Text):
operator: wert

Beispiele:
site: linkedin.com
inurl: profile
intext: "contact"

Jetzt für: "{query}"
"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                system_prompt="Du bist ein OSINT-Experte. Antworte nur mit operator: wert, nichts anderes."
            )

            # Parse suggestions
            suggestions = {}
            for line in response.split('\n'):
                line = line.strip()
                if ':' in line and not line.startswith('#'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        operator = parts[0].strip()
                        value = parts[1].strip().strip('"')
                        if operator in ['site', 'inurl', 'intext', 'intitle', 'filetype']:
                            suggestions[operator] = value

            logger.info(f"Suggested {len(suggestions)} operators")
            return suggestions

        except Exception as e:
            logger.error(f"Failed to suggest operators: {e}")
            return {}

    def expand_context(self, query: str, entity_type: Optional[str] = None) -> str:
        """
        Expand query with additional context.

        Args:
            query: Original query
            entity_type: Type hint (person, company, email, phone)

        Returns:
            Expanded query with context

        Example:
            >>> enhancer = QueryEnhancer(llm_client)
            >>> expanded = enhancer.expand_context("John Doe", entity_type="person")
            >>> len(expanded) > len("John Doe")
            True
        """
        logger.info(f"Expanding context for: {query} (type: {entity_type})")

        if entity_type == "person":
            context_prompt = """Diese Person soll recherchiert werden. Welche zusätzlichen Informationen wären hilfreich?
- Berufliche Informationen (Titel, Firma, Branche)
- Soziale Medien (LinkedIn, Twitter, GitHub)
- Publikationen oder Beiträge
- Geografische Informationen (Stadt, Land)
"""
        elif entity_type == "company":
            context_prompt = """Dieses Unternehmen soll recherchiert werden. Welche Informationen sind relevant?
- Offizielle Website
- Soziale Medien
- Pressemitteilungen
- Mitarbeiter-Profile
- Registerdaten
"""
        elif entity_type == "email":
            context_prompt = """Diese Email-Adresse soll recherchiert werden. Was ist interessant?
- Zugehörige Social-Media-Profile
- Zugehörige Domains/Websites
- Veröffentlichungen mit dieser Email
- Professionelle Profile
"""
        elif entity_type == "phone":
            context_prompt = """Diese Telefonnummer soll recherchiert werden. Welche Quellen sind nützlich?
- Telefonverzeichnisse
- Business-Einträge
- Social-Media-Profile
- Online-Bewertungen/Rezensionen
"""
        else:
            context_prompt = "Was sollte zu diesem Thema recherchiert werden?"

        prompt = f"""Query: "{query}"

{context_prompt}

Erweitere die Suchanfrage mit relevantem Kontext.
Antworte mit EINER erweiterten Suchanfrage (max 15 Wörter):"""

        try:
            expanded = self.llm.generate(
                prompt=prompt,
                system_prompt="Du erweiterst Suchanfragen mit relevanten Kontext-Keywords."
            ).strip().strip('"')

            logger.info(f"Expanded query: '{query}' -> '{expanded}'")
            return expanded

        except Exception as e:
            logger.error(f"Failed to expand context: {e}")
            return query

    def identify_entity_type(self, query: str) -> str:
        """
        Identify what type of entity is being searched.

        Args:
            query: Search query

        Returns:
            Entity type (person, company, email, phone, domain, topic)

        Example:
            >>> enhancer = QueryEnhancer(llm_client)
            >>> entity_type = enhancer.identify_entity_type("test@example.com")
            >>> entity_type
            'email'
        """
        # Simple pattern matching first
        import re

        # Email pattern
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', query.strip()):
            return 'email'

        # Phone pattern
        if re.match(r'^\+?\d[\d\s\-\(\)]{7,}$', query.strip()):
            return 'phone'

        # Domain pattern
        if re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', query.strip()) and ' ' not in query:
            return 'domain'

        # Use LLM for more complex detection
        prompt = f"""Analysiere diese OSINT-Suchanfrage: "{query}"

Um was für eine Entity handelt es sich?

Mögliche Typen:
- person (Name einer Person)
- company (Firmenname)
- email (Email-Adresse)
- phone (Telefonnummer)
- domain (Webseite/Domain)
- topic (Thema oder allgemeine Frage)

Antworte NUR mit dem Typ (ein Wort):"""

        try:
            entity_type = self.llm.generate(
                prompt=prompt,
                system_prompt="Du klassifizierst OSINT-Suchanfragen. Antworte nur mit dem Typ."
            ).strip().lower()

            # Validate
            valid_types = ['person', 'company', 'email', 'phone', 'domain', 'topic']
            if entity_type in valid_types:
                logger.info(f"Identified entity type: {entity_type}")
                return entity_type
            else:
                logger.warning(f"Invalid entity type: {entity_type}, defaulting to 'topic'")
                return 'topic'

        except Exception as e:
            logger.error(f"Failed to identify entity type: {e}")
            return 'topic'

    def suggest_sources(self, query: str, entity_type: Optional[str] = None) -> List[str]:
        """
        Suggest relevant sources for research.

        Args:
            query: Search query
            entity_type: Entity type hint

        Returns:
            List of suggested sources

        Example:
            >>> enhancer = QueryEnhancer(llm_client)
            >>> sources = enhancer.suggest_sources("John Doe developer", "person")
            >>> 'linkedin.com' in sources or 'github.com' in sources
            True
        """
        if not entity_type:
            entity_type = self.identify_entity_type(query)

        logger.info(f"Suggesting sources for {entity_type}: {query}")

        prompt = f"""Für diese OSINT-Recherche:
Query: "{query}"
Type: {entity_type}

Welche Online-Quellen sind am relevantesten?

Gib 5 relevante Domains/Quellen zurück (eine pro Zeile, nur Domain):

Beispiel:
linkedin.com
github.com
twitter.com

Jetzt für die Recherche:
"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                system_prompt="Du empfiehlst Recherchequellen. Antworte nur mit Domains, eine pro Zeile."
            )

            # Parse sources
            sources = []
            for line in response.split('\n'):
                line = line.strip().lower()
                # Remove http://, https://, www.
                line = line.replace('http://', '').replace('https://', '').replace('www.', '')
                # Remove trailing slash
                line = line.rstrip('/')

                if line and '.' in line and ' ' not in line:
                    sources.append(line)

            sources = sources[:5]  # Limit to 5
            logger.info(f"Suggested {len(sources)} sources")

            return sources

        except Exception as e:
            logger.error(f"Failed to suggest sources: {e}")
            return []
