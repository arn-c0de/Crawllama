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
        logger.info("Generating query variations for: %s", query)  # lgtm[py/log-injection] - parameterized logging; false positive

        prompt = f"""Generate {max_variations} alternative search queries for the OSINT investigation of:
"{query}"

Use:
- Synonyms and related terms
- Alternative formulations
- Extended contexts (e.g. professional titles, organizations)
- More specific or broader terms

Respond ONLY with the variants, one per line. No numbering or explanations.

Example for input "Max Mustermann Software Engineer":
Max Mustermann Entwickler
Max Mustermann Programmierer
Max Mustermann Tech Lead
Max Mustermann Software Developer
Mustermann Software Engineering

Now for: "{query}"
"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                system_prompt="You are an OSINT expert who optimizes search strategies."
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

        prompt = f"""Analyze this OSINT search query: "{query}"

Which search operators would improve the search?

Available operators:
- site: (specific domain, e.g. site:linkedin.com)
- inurl: (text in URL, e.g. inurl:profile)
- intext: (text in page content, e.g. intext:"email")
- intitle: (text in page title, e.g. intitle:"about")
- filetype: (file type, e.g. filetype:pdf)

Respond in format (WITHOUT additional text):
operator: value

Examples:
site: linkedin.com
inurl: profile
intext: "contact"

Now for: "{query}"
"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                system_prompt="You are an OSINT expert. Respond only with operator: value, nothing else."
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
            context_prompt = """This person should be investigated. What additional information would be helpful?
- Professional information (title, company, industry)
- Social media (LinkedIn, Twitter, GitHub)
- Publications or contributions
- Geographic information (city, country)
"""
        elif entity_type == "company":
            context_prompt = """This company should be investigated. What information is relevant?
- Official website
- Social media
- Press releases
- Employee profiles
- Registry data
"""
        elif entity_type == "email":
            context_prompt = """This email address should be investigated. What is interesting?
- Associated social media profiles
- Associated domains/websites
- Publications with this email
- Professional profiles
"""
        elif entity_type == "phone":
            context_prompt = """This phone number should be investigated. Which sources are useful?
- Phone directories
- Business listings
- Social media profiles
- Online reviews/ratings
"""
        else:
            context_prompt = "What should be investigated about this topic?"

        prompt = f"""Query: "{query}"

{context_prompt}

Expand the search query with relevant context.
Respond with ONE expanded search query (max 15 words):"""

        try:
            expanded = self.llm.generate(
                prompt=prompt,
                system_prompt="You expand search queries with relevant context keywords."
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
        prompt = f"""Analyze this OSINT search query: "{query}"

What type of entity is this?

Possible types:
- person (name of a person)
- company (company name)
- email (email address)
- phone (phone number)
- domain (website/domain)
- topic (topic or general question)

Respond ONLY with the type (one word):"""

        try:
            entity_type = self.llm.generate(
                prompt=prompt,
                system_prompt="You classify OSINT search queries. Respond only with the type."
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

        prompt = f"""For this OSINT investigation:
Query: "{query}"
Type: {entity_type}

Which online sources are most relevant?

Return 5 relevant domains/sources (one per line, domain only):

Example:
linkedin.com
github.com
twitter.com

Now for the investigation:
"""

        try:
            response = self.llm.generate(
                prompt=prompt,
                system_prompt="You recommend investigation sources. Respond only with domains, one per line."
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
