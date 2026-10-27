"""OSINT Tool for CrawlLama Agent Integration.

Provides unified interface to OSINT features:
- Advanced search operators
- Email intelligence
- Phone intelligence
- Persistent memory store
- AI-powered query enhancement
"""

import logging
from collections.abc import Callable

from core.llm_client import OllamaClient
from core.memory_store import get_memory_store
from core.osint import (
    DomainIntelligence,
    EmailIntelligence,
    IPIntelligence,
    OSINTCompliance,
    OSINTQueryParser,
    PhoneIntelligence,
    QueryEnhancer,
    SocialIntelligence,
)
from core.osint._common import run_async
from tools.osint_formatting import (
    _format_intelligence_sections,
)
from tools.osint_memory_ops import _handle_forget, _handle_recall, _handle_remember
from utils.privacy import redact_email, redact_ip_address, redact_phone_number

logger = logging.getLogger("crawllama")


def _reusable(value: str | None, analysis: dict | None) -> dict[str, dict]:
    """Map a single-item analysis for batch reuse; errors are not reused."""
    if value and analysis and 'error' not in analysis:
        return {value: analysis}
    return {}


class OSINTTool:
    """Unified OSINT tool for agent."""

    def __init__(self, llm_client: OllamaClient, config: dict | None = None):
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
        self.social_intel = SocialIntelligence()
        self.ip_intel = IPIntelligence()
        self.query_enhancer = QueryEnhancer(llm_client)
        self.compliance = OSINTCompliance()
        self.memory = get_memory_store()

        # Check if OSINT is enabled in config
        self.enabled = self.config.get('osint', {}).get('enabled', True)

        logger.info(f"OSINT Tool initialized (enabled: {self.enabled})")

    def process_query(self, query: str, user_id: str = "default") -> dict:
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
            'suggestions': {},
            'memory_operation': None
        }

        # Handle memory operations
        memory_operation = self._run_memory_operation(parsed)
        if memory_operation is not None:
            result['memory_operation'] = memory_operation
            return result

        result['intelligence'] = self._collect_intelligence(parsed, result['query_type'], user_id)

        # AI-powered suggestions
        result['suggestions'] = self._get_suggestions(query, parsed)

        return result

    def _run_memory_operation(self, parsed) -> dict | None:
        """Run remember/recall/forget operation if requested, else return None."""
        if parsed.remember_type:
            return self._handle_remember(parsed)
        if parsed.recall_category:
            return self._handle_recall(parsed)
        if parsed.forget_type:
            return self._handle_forget(parsed)
        return None

    def _collect_intelligence(self, parsed, query_type: str, user_id: str) -> dict:
        """Run all applicable intelligence analyses for the parsed query."""
        intelligence: dict = {}

        # Email intelligence (the batch reuses the first result instead of
        # analyzing - and compliance-counting - that address twice)
        if parsed.email:
            intelligence['email'] = self.analyze_email(parsed.email, user_id)

        if parsed.emails and len(parsed.emails) > 1:
            intelligence['email_batch'] = self.analyze_emails_batch(
                parsed.emails, user_id, precomputed=_reusable(parsed.email, intelligence.get('email'))
            )

        # Phone intelligence
        if parsed.phone:
            intelligence['phone'] = self.analyze_phone(parsed.phone, user_id=user_id)

        if parsed.phones and len(parsed.phones) > 1:
            intelligence['phone_batch'] = self.analyze_phones_batch(
                parsed.phones, user_id=user_id, precomputed=_reusable(parsed.phone, intelligence.get('phone'))
            )

        # Domain intelligence
        if parsed.domain:
            intelligence['domain'] = self.analyze_domain(parsed.domain, user_id)

        # IP intelligence
        if parsed.ip:
            intelligence['ip'] = self.analyze_ip(parsed.ip, user_id)

        # IP intelligence (auto-detected)
        if query_type == 'ip_intelligence' and not parsed.ip:
            intelligence['ip'] = run_async(self._execute_ip_search(parsed))

        # Social intelligence
        if query_type == 'social_intelligence':
            intelligence['social'] = run_async(self._execute_social_search(parsed))

        return intelligence

    def analyze_email(self, email: str, user_id: str = "default") -> dict:
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

        logger.info(f"Analyzing email: {redact_email(email)}")
        return self.email_intel.analyze_email(email)

    def analyze_emails_batch(
        self, emails: list[str], user_id: str = "default", precomputed: dict[str, dict] | None = None
    ) -> dict:
        """
        Analyze multiple email addresses in batch.

        Args:
            emails: List of email addresses
            user_id: User identifier
            precomputed: Already analyzed emails (value -> result) to reuse
                instead of running and compliance-counting them again

        Returns:
            Dictionary with batch results
        """
        logger.info(f"Batch analyzing {len(emails)} emails")
        summary = {'valid': 0, 'invalid': 0, 'disposable': 0, 'total_variations': 0}

        def summarize(analysis: dict) -> None:
            summary['valid' if analysis.get('valid') else 'invalid'] += 1
            if analysis.get('disposable'):
                summary['disposable'] += 1
            summary['total_variations'] += len(analysis.get('variations', []))

        return self._run_batch(
            emails, 'email', 'email_search', self.email_intel.analyze_email,
            summarize, summary, user_id, precomputed, redact_email,
        )

    def analyze_phone(self, phone: str, region: str | None = None, user_id: str = "default") -> dict:
        """
        Analyze phone number.

        Args:
            phone: Phone number
            region: Region code (e.g., 'DE', 'US')
            user_id: User identifier

        Returns:
            Phone intelligence results
        """
        # Check compliance
        allowed, reason = self.compliance.check_query(phone, user_id, 'phone_search')
        if not allowed:
            return {'error': 'Query not allowed', 'reason': reason}

        logger.info(f"Analyzing phone: {redact_phone_number(phone)}")
        return self.phone_intel.analyze_phone(phone, region)

    def analyze_phones_batch(
        self,
        phones: list[str],
        region: str | None = None,
        user_id: str = "default",
        precomputed: dict[str, dict] | None = None,
    ) -> dict:
        """
        Analyze multiple phone numbers in batch.

        Args:
            phones: List of phone numbers
            region: Default region code
            user_id: User identifier
            precomputed: Already analyzed numbers (value -> result) to reuse

        Returns:
            Dictionary with batch results
        """
        logger.info(f"Batch analyzing {len(phones)} phone numbers")
        summary: dict = {'valid': 0, 'invalid': 0, 'mobile': 0, 'landline': 0, 'countries': set()}

        def summarize(analysis: dict) -> None:
            if not analysis.get('valid'):
                summary['invalid'] += 1
                return
            summary['valid'] += 1
            phone_type = (analysis.get('type') or '').lower()
            if 'mobile' in phone_type:
                summary['mobile'] += 1
            elif 'landline' in phone_type or 'fixed' in phone_type:
                summary['landline'] += 1
            if analysis.get('country'):
                summary['countries'].add(analysis['country'])

        results = self._run_batch(
            phones, 'phone', 'phone_search',
            lambda phone: self.phone_intel.analyze_phone(phone, region),
            summarize, summary, user_id, precomputed, redact_phone_number,
        )
        # Convert set to list for JSON serialization
        results['summary']['countries'] = sorted(results['summary']['countries'])
        return results

    def _run_batch(
        self,
        values: list[str],
        kind: str,
        compliance_type: str,
        analyze: Callable[[str], dict],
        summarize: Callable[[dict], None],
        summary: dict,
        user_id: str,
        precomputed: dict[str, dict] | None,
        redact: Callable[[str], str],
    ) -> dict:
        """Shared batch loop: compliance check, analysis, summary, error entries."""
        precomputed = precomputed or {}
        results: dict = {'total': len(values), 'analyzed': 0, 'results': [], 'summary': summary}

        for value in values:
            analysis = precomputed.get(value)
            if analysis is None:
                allowed, reason = self.compliance.check_query(value, user_id, compliance_type)
                if not allowed:
                    results['results'].append({kind: value, 'error': 'Query not allowed', 'reason': reason})
                    continue
                try:
                    analysis = analyze(value)
                except Exception as e:
                    logger.error(f"Error analyzing {redact(value)}: {e}")
                    results['results'].append({kind: value, 'error': str(e)})
                    continue

            # Summarize before appending so a summary error cannot duplicate entries
            try:
                summarize(analysis)
            except Exception as e:
                logger.warning(f"Could not summarize {kind} result: {e}")
            results['results'].append(analysis)
            results['analyzed'] += 1

        logger.info(f"Batch analysis complete: {results['analyzed']}/{results['total']} successful")
        return results

    def analyze_domain(self, domain: str, user_id: str = "default") -> dict:
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

    def analyze_ip(self, ip: str, user_id: str = "default") -> dict:
        """
        Analyze IP address with comprehensive intelligence.

        Args:
            ip: IP address
            user_id: User identifier

        Returns:
            IP intelligence results
        """
        # Check compliance
        allowed, reason = self.compliance.check_query(ip, user_id, 'ip_search')
        if not allowed:
            return {'error': 'Query not allowed', 'reason': reason}

        logger.info(f"Analyzing IP address: {redact_ip_address(ip)}")

        return run_async(self.ip_intel.lookup_ip(ip))

    def analyze_social_username(self, username: str, platforms: list[str] | None = None, user_id: str = "default") -> dict:
        """
        Analyze username across social media platforms.

        Args:
            username: Username to analyze
            platforms: List of platforms to check (default: all)
            user_id: User identifier

        Returns:
            Social intelligence results
        """
        # Check compliance
        allowed, reason = self.compliance.check_query(username, user_id, 'social_search')
        if not allowed:
            return {'error': 'Query not allowed', 'reason': reason}

        logger.info(f"Analyzing social username: {username}")
        return self.social_intel.search_username_across_platforms(username, platforms)

    def discover_social_profiles_by_email(self, email: str, user_id: str = "default") -> dict:
        """
        Discover social media profiles associated with an email address.

        Args:
            email: Email address to search
            user_id: User identifier

        Returns:
            Social profile discovery results
        """
        # Check compliance
        allowed, reason = self.compliance.check_query(email, user_id, 'email_search')
        if not allowed:
            return {'error': 'Query not allowed', 'reason': reason}

        logger.info(f"Discovering social profiles for email: {redact_email(email)}")
        return run_async(self.social_intel.discover_profiles_by_email(email))

    def enhance_query(self, query: str) -> dict:
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

    def get_usage_stats(self, user_id: str = "default") -> dict:
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
        direct_matches = (
            (parsed_query.email, 'email_intelligence'),
            (parsed_query.phone, 'phone_intelligence'),
            (parsed_query.domain, 'domain_intelligence'),
            (parsed_query.ip or self._is_ip_query(parsed_query.text), 'ip_intelligence'),
            # The parser strips "username:" from the text, so check the field
            (getattr(parsed_query, 'username', None), 'social_intelligence'),
        )
        for matched, query_type in direct_matches:
            if matched:
                return query_type

        if self._is_username_query(getattr(parsed_query, 'terms', None) or parsed_query.text):
            return 'social_intelligence'
        if parsed_query.site or parsed_query.inurl or parsed_query.intext:
            return 'advanced_search'
        return 'general_search'

    def _is_username_query(self, query_terms: str) -> bool:
        """
        Check if query appears to be a username search.

        Args:
            query_terms: Search terms

        Returns:
            True if likely a username query
        """
        if not query_terms:
            return False
            
        # Check for social media indicators
        social_indicators = ['username:', 'user:', 'profile:', 'social:', '@']
        for indicator in social_indicators:
            if indicator in query_terms.lower():
                return True
                
        # A single handle-like token ("john_doe", "jdoe92"). Plain words such as
        # "python" or "weather" are ordinary searches, not a 12-platform scan.
        terms = query_terms.strip()
        if (' ' not in terms and 3 <= len(terms) <= 30
                and terms.replace('_', '').replace('-', '').replace('.', '').isalnum()
                and any(c.isdigit() or c in '_.-' for c in terms)):
            return True

        return False

    def _is_ip_query(self, query_text: str) -> bool:
        """
        Check if query appears to be an IP address.

        Args:
            query_text: Query text to check

        Returns:
            True if likely an IP address
        """
        if not query_text:
            return False
            
        # Check if it looks like an IP address
        import ipaddress
        try:
            # Try to parse as IP address
            ipaddress.ip_address(query_text.strip())
            return True
        except ValueError:
            pass  # Not a valid IP address, return False below
            
        return False

    async def _execute_ip_search(self, parsed_query) -> dict:
        """
        Execute IP intelligence search.

        Args:
            parsed_query: SearchQuery object

        Returns:
            IP intelligence results
        """
        # Get IP from either ip field or text field (auto-detection)
        ip = parsed_query.ip or parsed_query.text.strip()
        
        logger.info(f"Executing IP intelligence search for: {redact_ip_address(ip)}")
        
        try:
            # Use the IP intelligence module
            result = await self.ip_intel.lookup_ip(ip)
            return result
        except Exception as e:
            logger.error(f"IP intelligence search failed: {e}")
            return {
                'error': f'IP intelligence search failed: {e}',
                'ip': ip
            }

    async def _execute_social_search(self, parsed_query) -> dict:
        """
        Execute social intelligence search.

        Args:
            parsed_query: SearchQuery object

        Returns:
            Social intelligence results
        """
        query_terms = (
            getattr(parsed_query, 'username', None)
            or getattr(parsed_query, 'terms', None)
            or parsed_query.text
            or ""
        )

        # Clean up query terms (remove social indicators)
        username = query_terms.replace('username:', '').replace('user:', '').replace('profile:', '').replace('social:', '').replace('@', '').strip()
        
        logger.info(f"Executing social intelligence search for: {username}")
        
        try:
            # Search for username across social platforms
            results = await self.social_intel.analyze_username(username)
            summary = results.get('summary', {})

            return {
                'username': username,
                'platforms_found': summary.get('platforms_with_presence', 0),
                'total_platforms': summary.get('total_platforms_checked', 0),
                'social_intelligence': results
            }
        except Exception as e:
            logger.error(f"Social intelligence search failed: {e}")
            return {
                'error': f'Social intelligence search failed: {e}',
                'username': username
            }

    def _get_suggestions(self, query: str, parsed_query) -> dict:
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
def osint_search(query: str, config: dict | None = None) -> str:
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

    llm_config = config.get('llm', {}) if config else {}
    llm = OllamaClient(
        base_url=llm_config.get('base_url', 'http://127.0.0.1:11434'),
        model=llm_config.get('model', 'qwen3:8b')
    )
    osint = OSINTTool(llm, config)

    if not osint.check_terms():
        return osint.compliance.display_terms()

    result = osint.process_query(query)
    if 'error' in result:
        return f"Error: {result['error']}\nReason: {result.get('reason', 'Unknown')}"

    output = [
        f"OSINT Analysis for: {query}\n",
        f"Query Type: {result['query_type']}",
        f"Parsed: {result['parsed_query']}\n",
    ]
    output.extend(_format_intelligence_sections(result))
    return "\n".join(output)


# Bind methods to OSINTTool class
OSINTTool._handle_remember = _handle_remember
OSINTTool._handle_recall = _handle_recall
OSINTTool._handle_forget = _handle_forget
