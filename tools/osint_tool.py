"""OSINT Tool for CrawlLama Agent Integration.

Provides unified interface to OSINT features:
- Advanced search operators
- Email intelligence
- Phone intelligence
- AI-powered query enhancement
"""

import logging
from typing import Dict, List, Optional
from core.osint import (
    OSINTQueryParser,
    EmailIntelligence,
    PhoneIntelligence,
    DomainIntelligence,
    QueryEnhancer,
    OSINTCompliance
)
from core.llm_client import OllamaClient

logger = logging.getLogger("crawllama")


class OSINTTool:
    """Unified OSINT tool for agent."""

    def __init__(self, llm_client: OllamaClient, config: Dict = None):
        """
        Initialize OSINT tool.

        Args:
            llm_client: Ollama LLM client
            config: Configuration dictionary
        """
        self.config = config or {}

        # Initialize modules
        self.query_parser = OSINTQueryParser()
        self.email_intel = EmailIntelligence()
        self.phone_intel = PhoneIntelligence()
        self.domain_intel = DomainIntelligence()
        self.query_enhancer = QueryEnhancer(llm_client)
        self.compliance = OSINTCompliance()

        # Check if OSINT is enabled in config
        self.enabled = self.config.get('osint', {}).get('enabled', True)

        logger.info(f"OSINT Tool initialized (enabled: {self.enabled})")

    def process_query(self, query: str, user_id: str = "default") -> Dict:
        """
        Process OSINT query with full intelligence.

        Args:
            query: Search query
            user_id: User identifier

        Returns:
            Dictionary with processed results

        Example:
            >>> osint = OSINTTool(llm_client)
            >>> result = osint.process_query("site:github.com python")
            >>> result['query_type']
            'advanced_search'
        """
        if not self.enabled:
            logger.warning("OSINT features are disabled")
            return {'error': 'OSINT features disabled'}

        # Check compliance
        allowed, reason = self.compliance.check_query(query, user_id, 'general_osint')
        if not allowed:
            logger.warning(f"OSINT query blocked: {reason}")
            return {
                'error': 'Query not allowed',
                'reason': reason,
                'terms': self.compliance.display_terms()
            }

        # Parse query
        parsed = self.query_parser.parse(query)
        logger.info(f"Parsed OSINT query: {parsed}")

        result = {
            'original_query': query,
            'parsed_query': str(parsed),
            'query_type': self._determine_query_type(parsed),
            'intelligence': {},
            'suggestions': {}
        }

        # Email intelligence
        if parsed.email:
            result['intelligence']['email'] = self.analyze_email(parsed.email, user_id)

        # Phone intelligence
        if parsed.phone:
            result['intelligence']['phone'] = self.analyze_phone(parsed.phone, user_id)

        # Domain intelligence
        if parsed.domain:
            result['intelligence']['domain'] = self.analyze_domain(parsed.domain, user_id)

        # AI-powered suggestions
        result['suggestions'] = self._get_suggestions(query, parsed)

        return result

    def analyze_email(self, email: str, user_id: str = "default") -> Dict:
        """
        Analyze email address.

        Args:
            email: Email address
            user_id: User identifier

        Returns:
            Email intelligence results
        """
        # Check compliance
        allowed, reason = self.compliance.check_query(email, user_id, 'email_search')
        if not allowed:
            return {'error': 'Query not allowed', 'reason': reason}

        logger.info(f"Analyzing email: {email}")
        return self.email_intel.analyze_email(email)

    def analyze_phone(self, phone: str, region: str = None, user_id: str = "default") -> Dict:
        """
        Analyze phone number.

        Args:
            phone: Phone number
            region: Region code
            user_id: User identifier

        Returns:
            Phone intelligence results
        """
        # Check compliance
        allowed, reason = self.compliance.check_query(phone, user_id, 'phone_search')
        if not allowed:
            return {'error': 'Query not allowed', 'reason': reason}

        logger.info(f"Analyzing phone: {phone}")
        return self.phone_intel.analyze_phone(phone, region)

    def analyze_domain(self, domain: str, user_id: str = "default") -> Dict:
        """
        Analyze domain with IP geolocation.

        Args:
            domain: Domain name
            user_id: User identifier

        Returns:
            Domain intelligence results
        """
        # Check compliance
        allowed, reason = self.compliance.check_query(domain, user_id, 'general_osint')
        if not allowed:
            return {'error': 'Query not allowed', 'reason': reason}

        logger.info(f"Analyzing domain: {domain}")
        return self.domain_intel.analyze_domain(domain)

    def enhance_query(self, query: str) -> Dict:
        """
        Enhance query with AI suggestions.

        Args:
            query: Original query

        Returns:
            Dictionary with enhancements
        """
        logger.info(f"Enhancing query: {query}")

        # Identify entity type
        entity_type = self.query_enhancer.identify_entity_type(query)

        # Generate variations
        variations = self.query_enhancer.generate_variations(query)

        # Suggest operators
        operators = self.query_enhancer.suggest_operators(query)

        # Suggest sources
        sources = self.query_enhancer.suggest_sources(query, entity_type)

        return {
            'original_query': query,
            'entity_type': entity_type,
            'variations': variations,
            'suggested_operators': operators,
            'suggested_sources': sources
        }

    def build_search_query(self, parsed_query) -> str:
        """
        Build optimized search query from parsed query.

        Args:
            parsed_query: SearchQuery object

        Returns:
            Formatted search query
        """
        return self.query_parser.build_search_query(parsed_query)

    def check_terms(self, user_id: str = "default") -> bool:
        """
        Check if user has accepted terms.

        Args:
            user_id: User identifier

        Returns:
            True if terms accepted
        """
        return self.compliance.check_terms_accepted(user_id)

    def accept_terms(self, user_id: str = "default"):
        """
        Accept OSINT terms.

        Args:
            user_id: User identifier
        """
        self.compliance.accept_terms(user_id)
        logger.info(f"OSINT terms accepted for user: {user_id}")

    def get_usage_stats(self, user_id: str = "default") -> Dict:
        """
        Get usage statistics.

        Args:
            user_id: User identifier

        Returns:
            Usage statistics
        """
        return self.compliance.get_usage_stats(user_id)

    def _determine_query_type(self, parsed_query) -> str:
        """
        Determine type of OSINT query.

        Args:
            parsed_query: SearchQuery object

        Returns:
            Query type string
        """
        if parsed_query.email:
            return 'email_intelligence'
        elif parsed_query.phone:
            return 'phone_intelligence'
        elif parsed_query.domain:
            return 'domain_intelligence'
        elif parsed_query.site or parsed_query.inurl or parsed_query.intext:
            return 'advanced_search'
        else:
            return 'general_search'

    def _get_suggestions(self, query: str, parsed_query) -> Dict:
        """
        Get AI-powered suggestions.

        Args:
            query: Original query
            parsed_query: Parsed query

        Returns:
            Suggestions dict
        """
        try:
            # Identify entity type
            entity_type = self.query_enhancer.identify_entity_type(query)

            # Get query variations (limit to 3 for performance)
            variations = self.query_enhancer.generate_variations(query, max_variations=3)

            # Get operator suggestions
            operators = self.query_enhancer.suggest_operators(query)

            return {
                'entity_type': entity_type,
                'variations': variations,
                'operators': operators
            }
        except Exception as e:
            logger.error(f"Failed to get suggestions: {e}")
            return {}


# Tool function for agent integration
def osint_search(query: str, config: Dict = None) -> str:
    """
    OSINT search tool function for agent.

    Args:
        query: OSINT query with operators
        config: Configuration dict

    Returns:
        Formatted results string

    Example:
        >>> result = osint_search("email:test@example.com")
        >>> "Email Intelligence" in result
        True
    """
    from core.llm_client import OllamaClient

    # Initialize LLM client
    llm_config = config.get('llm', {}) if config else {}
    llm = OllamaClient(
        base_url=llm_config.get('base_url', 'http://127.0.0.1:11434'),
        model=llm_config.get('model', 'qwen3:8b')
    )

    # Initialize OSINT tool
    osint = OSINTTool(llm, config)

    # Check terms
    if not osint.check_terms():
        return osint.compliance.display_terms()

    # Process query
    result = osint.process_query(query)

    # Format output
    if 'error' in result:
        return f"Error: {result['error']}\nReason: {result.get('reason', 'Unknown')}"

    output = [f"OSINT Analysis for: {query}\n"]
    output.append(f"Query Type: {result['query_type']}")
    output.append(f"Parsed: {result['parsed_query']}\n")

    # Email intelligence
    if 'email' in result.get('intelligence', {}):
        email_data = result['intelligence']['email']
        output.append("═══ Email Intelligence ═══")
        output.append(f"Email: {email_data['email']}")
        output.append(f"Valid: {email_data['valid']}")
        output.append(f"Domain: {email_data['domain']}")
        output.append(f"Disposable: {email_data['disposable']}")
        output.append(f"Confidence: {email_data['confidence']:.2f}\n")

    # Phone intelligence
    if 'phone' in result.get('intelligence', {}):
        phone_data = result['intelligence']['phone']
        output.append("═══ Phone Intelligence ═══")
        output.append(f"Phone: {phone_data['input']}")
        output.append(f"Valid: {phone_data['valid']}")
        output.append(f"Formatted: {phone_data['formatted']}")
        output.append(f"Country: {phone_data['country']}")
        output.append(f"Type: {phone_data['type']}")
        output.append(f"Confidence: {phone_data['confidence']:.2f}\n")

    # Domain intelligence
    if 'domain' in result.get('intelligence', {}):
        from core.osint import DomainIntelligence
        domain_intel = DomainIntelligence()
        domain_data = result['intelligence']['domain']
        # Use the formatted output from DomainIntelligence
        output.append(domain_intel.format_results(domain_data))

    # Suggestions
    if result.get('suggestions'):
        suggestions = result['suggestions']
        output.append("═══ AI Suggestions ═══")
        if 'variations' in suggestions and suggestions['variations']:
            output.append("Query Variations:")
            for var in suggestions['variations'][:3]:
                output.append(f"  • {var}")
        if 'operators' in suggestions and suggestions['operators']:
            output.append("Suggested Operators:")
            for op, val in suggestions['operators'].items():
                output.append(f"  • {op}: {val}")

    return "\n".join(output)
