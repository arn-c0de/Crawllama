"""OSINT Tool for CrawlLama Agent Integration.

Provides unified interface to OSINT features:
- Advanced search operators
- Email intelligence
- Phone intelligence
- Persistent memory store
- AI-powered query enhancement
"""

import logging
from typing import Dict, List, Optional
from core.osint import (
    OSINTQueryParser,
    EmailIntelligence,
    PhoneIntelligence,
    QueryEnhancer,
    OSINTCompliance,
    SocialIntelligence,
    DomainIntelligence,
    IPIntelligence
)
from core.osint._common import run_async
from core.llm_client import OllamaClient
from core.memory_store import get_memory_store
from utils.privacy import redact_email, redact_ip_address, redact_phone_number

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
        self.social_intel = SocialIntelligence()
        self.ip_intel = IPIntelligence()
        self.query_enhancer = QueryEnhancer(llm_client)
        self.compliance = OSINTCompliance()
        self.memory = get_memory_store()

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

    def _run_memory_operation(self, parsed) -> Optional[Dict]:
        """Run remember/recall/forget operation if requested, else return None."""
        if parsed.remember_type:
            return self._handle_remember(parsed)
        if parsed.recall_category:
            return self._handle_recall(parsed)
        if parsed.forget_type:
            return self._handle_forget(parsed)
        return None

    def _collect_intelligence(self, parsed, query_type: str, user_id: str) -> Dict:
        """Run all applicable intelligence analyses for the parsed query."""
        intelligence: Dict = {}

        # Email intelligence
        if parsed.email:
            intelligence['email'] = self.analyze_email(parsed.email, user_id)

        # Batch email intelligence
        if parsed.emails and len(parsed.emails) > 1:
            intelligence['email_batch'] = self.analyze_emails_batch(parsed.emails, user_id)

        # Phone intelligence
        if parsed.phone:
            intelligence['phone'] = self.analyze_phone(parsed.phone, user_id=user_id)

        # Batch phone intelligence
        if parsed.phones and len(parsed.phones) > 1:
            intelligence['phone_batch'] = self.analyze_phones_batch(parsed.phones, user_id=user_id)

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

        logger.info(f"Analyzing email: {redact_email(email)}")
        return self.email_intel.analyze_email(email)

    def analyze_emails_batch(self, emails: List[str], user_id: str = "default") -> Dict:
        """
        Analyze multiple email addresses in batch.

        Args:
            emails: List of email addresses
            user_id: User identifier

        Returns:
            Dictionary with batch results
        """
        logger.info(f"Batch analyzing {len(emails)} emails")
        
        results = {
            'total': len(emails),
            'analyzed': 0,
            'results': [],
            'summary': {
                'valid': 0,
                'invalid': 0,
                'disposable': 0,
                'total_variations': 0
            }
        }
        
        for email in emails:
            # Check compliance for each
            allowed, reason = self.compliance.check_query(email, user_id, 'email_search')
            if not allowed:
                results['results'].append({
                    'email': email,
                    'error': 'Query not allowed',
                    'reason': reason
                })
                continue
            
            # Analyze email
            try:
                analysis = self.email_intel.analyze_email(email)
                results['results'].append(analysis)
                results['analyzed'] += 1
                
                # Update summary
                if analysis.get('valid'):
                    results['summary']['valid'] += 1
                else:
                    results['summary']['invalid'] += 1
                    
                if analysis.get('disposable'):
                    results['summary']['disposable'] += 1
                    
                results['summary']['total_variations'] += len(analysis.get('variations', []))
                
            except Exception as e:
                logger.error(f"Error analyzing {redact_email(email)}: {e}")
                results['results'].append({
                    'email': email,
                    'error': str(e)
                })
        
        logger.info(f"Batch analysis complete: {results['analyzed']}/{results['total']} successful")
        return results

    def analyze_phone(self, phone: str, region: str = None, user_id: str = "default") -> Dict:
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

    def analyze_phones_batch(self, phones: List[str], region: str = None, user_id: str = "default") -> Dict:
        """
        Analyze multiple phone numbers in batch.

        Args:
            phones: List of phone numbers
            region: Default region code
            user_id: User identifier

        Returns:
            Dictionary with batch results
        """
        logger.info(f"Batch analyzing {len(phones)} phone numbers")
        
        results = {
            'total': len(phones),
            'analyzed': 0,
            'results': [],
            'summary': {
                'valid': 0,
                'invalid': 0,
                'mobile': 0,
                'landline': 0,
                'countries': set()
            }
        }
        
        for phone in phones:
            # Check compliance for each
            allowed, reason = self.compliance.check_query(phone, user_id, 'phone_search')
            if not allowed:
                results['results'].append({
                    'phone': phone,
                    'error': 'Query not allowed',
                    'reason': reason
                })
                continue
            
            # Analyze phone
            try:
                analysis = self.phone_intel.analyze_phone(phone, region)
                results['results'].append(analysis)
                results['analyzed'] += 1
                
                # Update summary
                if analysis.get('valid'):
                    results['summary']['valid'] += 1
                    
                    # Track type
                    phone_type = analysis.get('type', '').lower()
                    if 'mobile' in phone_type:
                        results['summary']['mobile'] += 1
                    elif 'landline' in phone_type or 'fixed' in phone_type:
                        results['summary']['landline'] += 1
                    
                    # Track country
                    if analysis.get('country'):
                        results['summary']['countries'].add(analysis['country'])
                else:
                    results['summary']['invalid'] += 1
                
            except Exception as e:
                logger.error(f"Error analyzing {phone}: {e}")
                results['results'].append({
                    'phone': phone,
                    'error': str(e)
                })
        
        # Convert set to list for JSON serialization
        results['summary']['countries'] = list(results['summary']['countries'])
        
        logger.info(f"Batch analysis complete: {results['analyzed']}/{results['total']} successful")
        return results

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

    def analyze_ip(self, ip: str, user_id: str = "default") -> Dict:
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

    def analyze_social_username(self, username: str, platforms: Optional[List[str]] = None, user_id: str = "default") -> Dict:
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
        return self.social_intel.search_username_across_platforms(username)

    def discover_social_profiles_by_email(self, email: str, user_id: str = "default") -> Dict:
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
        direct_matches = (
            (parsed_query.email, 'email_intelligence'),
            (parsed_query.phone, 'phone_intelligence'),
            (parsed_query.domain, 'domain_intelligence'),
            (parsed_query.ip or self._is_ip_query(parsed_query.text), 'ip_intelligence'),
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
                
        # Check if it looks like a single username (no spaces, reasonable length)
        terms = query_terms.strip()
        if ' ' not in terms and 3 <= len(terms) <= 30 and terms.replace('_', '').replace('-', '').replace('.', '').isalnum():
            # Could be a username - let social intelligence decide
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

    async def _execute_ip_search(self, parsed_query) -> Dict:
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
                'error': f'IP intelligence search failed: {str(e)}',
                'ip': ip
            }

    async def _execute_social_search(self, parsed_query) -> Dict:
        """
        Execute social intelligence search.

        Args:
            parsed_query: SearchQuery object

        Returns:
            Social intelligence results
        """
        query_terms = getattr(parsed_query, 'terms', None) or parsed_query.text or ""
        
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
                'error': f'Social intelligence search failed: {str(e)}',
                'username': username
            }

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


# --- Section formatters for osint_search output -----------------------------

def _format_email_section(email_data: Dict) -> List[str]:
    """Format single-email intelligence results."""
    return [
        "═══ Email Intelligence ═══",
        f"Email: {email_data['email']}",
        f"Valid: {email_data['valid']}",
        f"Domain: {email_data['domain']}",
        f"Disposable: {email_data['disposable']}",
        f"Confidence: {email_data['confidence']:.2f}\n",
    ]


def _format_email_batch_section(batch_data: Dict) -> List[str]:
    """Format batch email intelligence results."""
    summary = batch_data['summary']
    lines = [
        "═══ Batch Email Intelligence ═══",
        f"Total Emails Analyzed: {batch_data['analyzed']}/{batch_data['total']}",
        "Summary:",
        f"  ✅ Valid: {summary['valid']}",
        f"  ❌ Invalid: {summary['invalid']}",
        f"  🗑️  Disposable: {summary['disposable']}",
        f"  📊 Total Variations: {summary['total_variations']}",
        "",
        "Individual Results:",
    ]
    for i, email_result in enumerate(batch_data['results'], 1):
        if 'error' in email_result:
            lines.append(f"  {i}. ❌ {email_result['email']}: {email_result['error']}")
        else:
            status = "✅" if email_result.get('valid') else "❌"
            disp = "🗑️" if email_result.get('disposable') else ""
            lines.append(f"  {i}. {status} {disp} {email_result['email']} - {email_result.get('domain', 'N/A')}")
    lines.append("")
    return lines


def _format_phone_section(phone_data: Dict) -> List[str]:
    """Format single-phone intelligence results."""
    return [
        "═══ Phone Intelligence ═══",
        f"Phone: {phone_data['input']}",
        f"Valid: {phone_data['valid']}",
        f"Formatted: {phone_data['formatted']}",
        f"Country: {phone_data['country']}",
        f"Type: {phone_data['type']}",
        f"Confidence: {phone_data['confidence']:.2f}\n",
    ]


def _format_phone_batch_section(batch_data: Dict) -> List[str]:
    """Format batch phone intelligence results."""
    summary = batch_data['summary']
    lines = [
        "═══ Batch Phone Intelligence ═══",
        f"Total Phones Analyzed: {batch_data['analyzed']}/{batch_data['total']}",
        "Summary:",
        f"  ✅ Valid: {summary['valid']}",
        f"  ❌ Invalid: {summary['invalid']}",
        f"  📱 Mobile: {summary['mobile']}",
        f"  📞 Landline: {summary['landline']}",
        f"  🌍 Countries: {', '.join(summary['countries'])}",
        "",
        "Individual Results:",
    ]
    for i, phone_result in enumerate(batch_data['results'], 1):
        if 'error' in phone_result:
            phone = phone_result.get('phone', phone_result.get('input', 'Unknown'))
            lines.append(f"  {i}. ❌ {phone}: {phone_result['error']}")
        else:
            status = "✅" if phone_result.get('valid') else "❌"
            ptype = phone_result.get('type', 'Unknown')
            country = phone_result.get('country', 'Unknown')
            formatted = phone_result.get('formatted', phone_result.get('input', 'N/A'))
            lines.append(f"  {i}. {status} {formatted} - {country} ({ptype})")
    lines.append("")
    return lines


def _format_ip_section(ip_data: Dict) -> List[str]:
    """Format IP intelligence results, delegating to IPIntelligence."""
    if 'error' in ip_data:
        return [f"❌ IP Analysis Error: {ip_data.get('error', 'Unknown error')}"]
    from core.osint.ip_intel import IPIntelligence
    return [IPIntelligence().format_results(ip_data)]


def _format_social_section(social_data: Dict) -> List[str]:
    """Format social media intelligence results."""
    lines = ["═══ Social Intelligence ═══"]
    if 'error' in social_data:
        lines.append(f"Error: {social_data.get('error', 'Unknown error')}")
        lines.append("")
        return lines

    lines.append(f"Username: {social_data.get('username', 'Unknown')}")
    lines.append(
        f"Platforms Found: {social_data.get('platforms_found', 0)} / {social_data.get('total_platforms', 0)}"
    )

    social_intel = social_data.get('social_intelligence', {})
    found_profiles = [
        _describe_profile(data) for data in social_intel.get('platforms_found', [])
    ]
    if found_profiles:
        lines.append("\nProfiles Found:")
        lines.extend(f"  {profile}" for profile in found_profiles)
    else:
        lines.append("No profiles found on searched platforms")

    summary = social_intel.get('summary', {})
    if summary:
        lines.append(f"\nSummary: Searched {summary.get('total_platforms_checked', 0)} platforms")
    lines.append("")
    return lines


def _describe_profile(data: Dict) -> str:
    """Build a one-line description of a found social profile."""
    info = f"✓ {data.get('platform', 'unknown').title()}"
    profile = data.get('profile_data') or {}
    if profile.get('display_name'):
        info += f" - {profile['display_name']}"
    if profile.get('followers'):
        info += f" ({profile['followers']} followers)"
    return info


def _format_suggestions_section(suggestions: Dict) -> List[str]:
    """Format AI query suggestions."""
    lines = ["═══ AI Suggestions ═══"]
    if suggestions.get('variations'):
        lines.append("Query Variations:")
        lines.extend(f"  • {var}" for var in suggestions['variations'][:3])
    if suggestions.get('operators'):
        lines.append("Suggested Operators:")
        lines.extend(f"  • {op}: {val}" for op, val in suggestions['operators'].items())
    return lines


def _format_intelligence_sections(result: Dict) -> List[str]:
    """Format every intelligence section present in a process_query result."""
    intelligence = result.get('intelligence', {})
    lines: List[str] = []

    if 'email' in intelligence:
        lines.extend(_format_email_section(intelligence['email']))
    if 'email_batch' in intelligence:
        lines.extend(_format_email_batch_section(intelligence['email_batch']))
    if 'phone' in intelligence:
        lines.extend(_format_phone_section(intelligence['phone']))
    if 'phone_batch' in intelligence:
        lines.extend(_format_phone_batch_section(intelligence['phone_batch']))
    if 'domain' in intelligence:
        from core.osint import DomainIntelligence
        lines.append(DomainIntelligence().format_results(intelligence['domain']))
    if 'ip' in intelligence:
        lines.extend(_format_ip_section(intelligence['ip']))
    if 'social' in intelligence:
        lines.extend(_format_social_section(intelligence['social']))
    if result.get('suggestions'):
        lines.extend(_format_suggestions_section(result['suggestions']))

    return lines


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


# Data-driven dispatch tables for the memory commands. Each maps a command
# keyword to the memory-store method (resolved via getattr) plus its labels,
# replacing what used to be three long if/elif ladders.
_REMEMBER_DISPATCH = {
    'email':    ('remember_email',    'Email'),
    'phone':    ('remember_phone',    'Phone'),
    'ip':       ('remember_ip',       'IP'),
    'username': ('remember_username', 'Username'),
    'domain':   ('remember_domain',   'Domain'),
}

_RECALL_GETTERS = {
    'emails':    ('get_all_emails',    'emails'),
    'phones':    ('get_all_phones',    'phones'),
    'ips':       ('get_all_ips',       'IPs'),
    'usernames': ('get_all_usernames', 'usernames'),
    'domains':   ('get_all_domains',   'domains'),
    'notes':     ('get_all_notes',     'notes'),
}

_FORGET_DISPATCH = {
    'email':    ('forget_email',    'Email {v} forgotten',    'Email {v} not found in memory'),
    'phone':    ('forget_phone',    'Phone {v} forgotten',    'Phone {v} not found in memory'),
    'ip':       ('forget_ip',       'IP {v} forgotten',       'IP {v} not found in memory'),
    'username': ('forget_username', 'Username {v} forgotten', 'Username {v} not found in memory'),
    'category': ('clear_category',  'Category {v} cleared',   'Category {v} not found'),
}


def _handle_remember(osint_tool, parsed) -> Dict:
    """Handle remember operation (dispatch by remember_type)."""
    remember_type = parsed.remember_type.lower()
    value = parsed.remember_value

    result = {
        'operation': 'remember',
        'type': remember_type,
        'value': value,
        'success': False
    }

    try:
        if remember_type == 'note':
            result['success'] = osint_tool.memory.add_note(value)
            result['message'] = "Note added successfully"
        elif remember_type in _REMEMBER_DISPATCH:
            method_name, label = _REMEMBER_DISPATCH[remember_type]
            success = getattr(osint_tool.memory, method_name)(value)
            result['success'] = success
            result['message'] = (
                f"{label} {value} remembered" if success
                else f"{label} {value} already in memory"
            )
        else:
            result['message'] = f"Unknown remember type: {remember_type}"

    except Exception as e:
        result['message'] = f"Error: {str(e)}"
        logger.error(f"Remember operation failed: {e}")

    return result


def _handle_recall(osint_tool, parsed) -> Dict:
    """Handle recall operation (search, full dump, or single category)."""
    category = parsed.recall_category.lower() if parsed.recall_category else 'all'
    query = parsed.recall_query

    result = {
        'operation': 'recall',
        'category': category,
        'query': query,
        'data': {}
    }

    try:
        if query:
            # Search across all categories
            result['data'] = osint_tool.memory.search(query)
            result['message'] = f"Search results for '{query}'"
        elif category == 'all':
            # Get summary of all data
            result['data'] = {
                'summary': osint_tool.memory.get_summary(),
                'emails': osint_tool.memory.get_all_emails(),
                'phones': osint_tool.memory.get_all_phones(),
                'ips': osint_tool.memory.get_all_ips(),
                'usernames': osint_tool.memory.get_all_usernames(),
                'domains': osint_tool.memory.get_all_domains(),
                'notes': osint_tool.memory.get_all_notes()
            }
            result['message'] = "All stored data retrieved"
        elif category in _RECALL_GETTERS:
            getter, label = _RECALL_GETTERS[category]
            items = getattr(osint_tool.memory, getter)()
            result['data'][category] = items
            result['message'] = f"Retrieved {len(items)} {label}"
        else:
            result['message'] = f"Unknown category: {category}"

    except Exception as e:
        result['message'] = f"Error: {str(e)}"
        result['error'] = str(e)
        logger.error(f"Recall operation failed: {e}")

    return result


def _handle_forget(osint_tool, parsed) -> Dict:
    """Handle forget operation (dispatch by forget_type)."""
    forget_type = parsed.forget_type.lower()
    value = parsed.forget_value

    result = {
        'operation': 'forget',
        'type': forget_type,
        'value': value,
        'success': False
    }

    try:
        if forget_type == 'all':
            result['success'] = osint_tool.memory.clear_all()
            result['message'] = "All memory cleared"
        elif forget_type in _FORGET_DISPATCH:
            method_name, ok_msg, fail_msg = _FORGET_DISPATCH[forget_type]
            success = getattr(osint_tool.memory, method_name)(value)
            result['success'] = success
            result['message'] = (ok_msg if success else fail_msg).format(v=value)
        else:
            result['message'] = f"Unknown forget type: {forget_type}"

    except Exception as e:
        result['message'] = f"Error: {str(e)}"
        logger.error(f"Forget operation failed: {e}")

    return result


# Bind methods to OSINTTool class
OSINTTool._handle_remember = _handle_remember
OSINTTool._handle_recall = _handle_recall
OSINTTool._handle_forget = _handle_forget
