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
from core.osint.social_intel import SocialIntelligence
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
        if parsed.remember_type:
            result['memory_operation'] = self._handle_remember(parsed)
            return result
        
        if parsed.recall_category:
            result['memory_operation'] = self._handle_recall(parsed)
            return result
        
        if parsed.forget_type:
            result['memory_operation'] = self._handle_forget(parsed)
            return result

        # Email intelligence
        if parsed.email:
            result['intelligence']['email'] = self.analyze_email(parsed.email, user_id)
        
        # Batch email intelligence (NEW)
        if parsed.emails and len(parsed.emails) > 1:
            result['intelligence']['email_batch'] = self.analyze_emails_batch(parsed.emails, user_id)

        # Phone intelligence
        if parsed.phone:
            result['intelligence']['phone'] = self.analyze_phone(parsed.phone, user_id=user_id)
        
        # Batch phone intelligence (NEW)
        if parsed.phones and len(parsed.phones) > 1:
            result['intelligence']['phone_batch'] = self.analyze_phones_batch(parsed.phones, user_id=user_id)

        # Domain intelligence
        if parsed.domain:
            result['intelligence']['domain'] = self.analyze_domain(parsed.domain, user_id)

        # IP intelligence
        if parsed.ip:
            result['intelligence']['ip'] = self.analyze_ip(parsed.ip, user_id)

        # IP intelligence (auto-detected)
        if result['query_type'] == 'ip_intelligence' and not parsed.ip:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                ip_result = loop.run_until_complete(self._execute_ip_search(parsed))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                ip_result = loop.run_until_complete(self._execute_ip_search(parsed))
            result['intelligence']['ip'] = ip_result

        # Social intelligence
        if result['query_type'] == 'social_intelligence':
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                social_result = loop.run_until_complete(self._execute_social_search(parsed))
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                social_result = loop.run_until_complete(self._execute_social_search(parsed))
            result['intelligence']['social'] = social_result

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
        
        try:
            # Use asyncio to handle the async method
            import asyncio
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.ip_intel.lookup_ip(ip))
        except RuntimeError:
            # Create new event loop if none exists
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.ip_intel.lookup_ip(ip))

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
        try:
            # Use asyncio to handle the async method
            import asyncio
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.social_intel.discover_profiles_by_email(email))
        except RuntimeError:
            # Create new event loop if none exists
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.social_intel.discover_profiles_by_email(email))

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
        elif parsed_query.ip:
            return 'ip_intelligence'
        elif self._is_ip_query(parsed_query.text):
            return 'ip_intelligence'
        elif self._is_username_query(getattr(parsed_query, 'terms', None) or parsed_query.text):
            return 'social_intelligence'
        elif parsed_query.site or parsed_query.inurl or parsed_query.intext:
            return 'advanced_search'
        else:
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
            results = await self.social_intel.search_username(username)
            
            return {
                'username': username,
                'platforms_found': len([p for p in results.get('platforms', {}).values() if p.get('exists')]),
                'total_platforms': len(results.get('platforms', {})),
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
    
    # Batch Email Intelligence (NEW)
    if 'email_batch' in result.get('intelligence', {}):
        batch_data = result['intelligence']['email_batch']
        output.append("═══ Batch Email Intelligence ═══")
        output.append(f"Total Emails Analyzed: {batch_data['analyzed']}/{batch_data['total']}")
        output.append(f"Summary:")
        output.append(f"  ✅ Valid: {batch_data['summary']['valid']}")
        output.append(f"  ❌ Invalid: {batch_data['summary']['invalid']}")
        output.append(f"  🗑️  Disposable: {batch_data['summary']['disposable']}")
        output.append(f"  📊 Total Variations: {batch_data['summary']['total_variations']}")
        output.append("")
        output.append("Individual Results:")
        for i, email_result in enumerate(batch_data['results'], 1):
            if 'error' in email_result:
                output.append(f"  {i}. ❌ {email_result['email']}: {email_result['error']}")
            else:
                status = "✅" if email_result.get('valid') else "❌"
                disp = "🗑️" if email_result.get('disposable') else ""
                output.append(f"  {i}. {status} {disp} {email_result['email']} - {email_result.get('domain', 'N/A')}")
        output.append("")

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
    
    # Batch Phone Intelligence (NEW)
    if 'phone_batch' in result.get('intelligence', {}):
        batch_data = result['intelligence']['phone_batch']
        output.append("═══ Batch Phone Intelligence ═══")
        output.append(f"Total Phones Analyzed: {batch_data['analyzed']}/{batch_data['total']}")
        output.append(f"Summary:")
        output.append(f"  ✅ Valid: {batch_data['summary']['valid']}")
        output.append(f"  ❌ Invalid: {batch_data['summary']['invalid']}")
        output.append(f"  📱 Mobile: {batch_data['summary']['mobile']}")
        output.append(f"  📞 Landline: {batch_data['summary']['landline']}")
        output.append(f"  🌍 Countries: {', '.join(batch_data['summary']['countries'])}")
        output.append("")
        output.append("Individual Results:")
        for i, phone_result in enumerate(batch_data['results'], 1):
            if 'error' in phone_result:
                output.append(f"  {i}. ❌ {phone_result.get('phone', phone_result.get('input', 'Unknown'))}: {phone_result['error']}")
            else:
                status = "✅" if phone_result.get('valid') else "❌"
                ptype = phone_result.get('type', 'Unknown')
                country = phone_result.get('country', 'Unknown')
                formatted = phone_result.get('formatted', phone_result.get('input', 'N/A'))
                output.append(f"  {i}. {status} {formatted} - {country} ({ptype})")
        output.append("")

    # Domain intelligence
    if 'domain' in result.get('intelligence', {}):
        from core.osint import DomainIntelligence
        domain_intel = DomainIntelligence()
        domain_data = result['intelligence']['domain']
        # Use the formatted output from DomainIntelligence
        output.append(domain_intel.format_results(domain_data))

    # IP intelligence
    if 'ip' in result.get('intelligence', {}):
        ip_data = result['intelligence']['ip']
        if 'error' not in ip_data:
            # Use the format_results method from IPIntelligence
            from core.osint.ip_intel import IPIntelligence
            ip_intel = IPIntelligence()
            output.append(ip_intel.format_results(ip_data))
        else:
            output.append(f"❌ IP Analysis Error: {ip_data.get('error', 'Unknown error')}")

    # Social intelligence
    if 'social' in result.get('intelligence', {}):
        social_data = result['intelligence']['social']
        output.append("═══ Social Intelligence ═══")
        if 'error' not in social_data:
            output.append(f"Username: {social_data.get('username', 'Unknown')}")
            output.append(f"Platforms Found: {social_data.get('platforms_found', 0)} / {social_data.get('total_platforms', 0)}")
            
            # Display individual platform results
            social_intel = social_data.get('social_intelligence', {})
            platforms = social_intel.get('platforms', {})
            
            found_profiles = []
            for platform, data in platforms.items():
                if data.get('exists'):
                    profile_info = f"✓ {platform.title()}"
                    if data.get('profile_data'):
                        profile = data['profile_data']
                        if profile.get('display_name'):
                            profile_info += f" - {profile['display_name']}"
                        if profile.get('followers'):
                            profile_info += f" ({profile['followers']} followers)"
                    found_profiles.append(profile_info)
                    
            if found_profiles:
                output.append("\nProfiles Found:")
                for profile in found_profiles:
                    output.append(f"  {profile}")
            else:
                output.append("No profiles found on searched platforms")
                
            # Display search summary
            summary = social_intel.get('summary', {})
            if summary:
                output.append(f"\nSummary: Searched {summary.get('total_searched', 0)} platforms")
        else:
            output.append(f"Error: {social_data.get('error', 'Unknown error')}")
        output.append("")

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


def _handle_remember(osint_tool, parsed) -> Dict:
    """
    Handle remember operation.
    
    Args:
        osint_tool: OSINTTool instance
        parsed: Parsed query
    
    Returns:
        Memory operation result
    """
    remember_type = parsed.remember_type.lower()
    value = parsed.remember_value
    
    result = {
        'operation': 'remember',
        'type': remember_type,
        'value': value,
        'success': False
    }
    
    try:
        if remember_type == 'email':
            success = osint_tool.memory.remember_email(value)
            result['success'] = success
            result['message'] = f"Email {value} remembered" if success else f"Email {value} already in memory"
            
        elif remember_type == 'phone':
            success = osint_tool.memory.remember_phone(value)
            result['success'] = success
            result['message'] = f"Phone {value} remembered" if success else f"Phone {value} already in memory"
            
        elif remember_type == 'ip':
            success = osint_tool.memory.remember_ip(value)
            result['success'] = success
            result['message'] = f"IP {value} remembered" if success else f"IP {value} already in memory"
            
        elif remember_type == 'username':
            success = osint_tool.memory.remember_username(value)
            result['success'] = success
            result['message'] = f"Username {value} remembered" if success else f"Username {value} already in memory"
            
        elif remember_type == 'domain':
            success = osint_tool.memory.remember_domain(value)
            result['success'] = success
            result['message'] = f"Domain {value} remembered" if success else f"Domain {value} already in memory"
            
        elif remember_type == 'note':
            success = osint_tool.memory.add_note(value)
            result['success'] = success
            result['message'] = f"Note added successfully"
            
        else:
            result['message'] = f"Unknown remember type: {remember_type}"
            
    except Exception as e:
        result['message'] = f"Error: {str(e)}"
        logger.error(f"Remember operation failed: {e}")
    
    return result


def _handle_recall(osint_tool, parsed) -> Dict:
    """
    Handle recall operation.
    
    Args:
        osint_tool: OSINTTool instance
        parsed: Parsed query
    
    Returns:
        Memory recall result
    """
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
        elif category == 'emails':
            result['data']['emails'] = osint_tool.memory.get_all_emails()
            result['message'] = f"Retrieved {len(result['data']['emails'])} emails"
        elif category == 'phones':
            result['data']['phones'] = osint_tool.memory.get_all_phones()
            result['message'] = f"Retrieved {len(result['data']['phones'])} phones"
        elif category == 'ips':
            result['data']['ips'] = osint_tool.memory.get_all_ips()
            result['message'] = f"Retrieved {len(result['data']['ips'])} IPs"
        elif category == 'usernames':
            result['data']['usernames'] = osint_tool.memory.get_all_usernames()
            result['message'] = f"Retrieved {len(result['data']['usernames'])} usernames"
        elif category == 'domains':
            result['data']['domains'] = osint_tool.memory.get_all_domains()
            result['message'] = f"Retrieved {len(result['data']['domains'])} domains"
        elif category == 'notes':
            result['data']['notes'] = osint_tool.memory.get_all_notes()
            result['message'] = f"Retrieved {len(result['data']['notes'])} notes"
        else:
            result['message'] = f"Unknown category: {category}"
            
    except Exception as e:
        result['message'] = f"Error: {str(e)}"
        result['error'] = str(e)
        logger.error(f"Recall operation failed: {e}")
    
    return result


def _handle_forget(osint_tool, parsed) -> Dict:
    """
    Handle forget operation.
    
    Args:
        osint_tool: OSINTTool instance
        parsed: Parsed query
    
    Returns:
        Memory forget result
    """
    forget_type = parsed.forget_type.lower()
    value = parsed.forget_value
    
    result = {
        'operation': 'forget',
        'type': forget_type,
        'value': value,
        'success': False
    }
    
    try:
        if forget_type == 'email':
            success = osint_tool.memory.forget_email(value)
            result['success'] = success
            result['message'] = f"Email {value} forgotten" if success else f"Email {value} not found in memory"
            
        elif forget_type == 'phone':
            success = osint_tool.memory.forget_phone(value)
            result['success'] = success
            result['message'] = f"Phone {value} forgotten" if success else f"Phone {value} not found in memory"
            
        elif forget_type == 'ip':
            success = osint_tool.memory.forget_ip(value)
            result['success'] = success
            result['message'] = f"IP {value} forgotten" if success else f"IP {value} not found in memory"
            
        elif forget_type == 'username':
            success = osint_tool.memory.forget_username(value)
            result['success'] = success
            result['message'] = f"Username {value} forgotten" if success else f"Username {value} not found in memory"
            
        elif forget_type == 'category':
            success = osint_tool.memory.clear_category(value)
            result['success'] = success
            result['message'] = f"Category {value} cleared" if success else f"Category {value} not found"
            
        elif forget_type == 'all':
            success = osint_tool.memory.clear_all()
            result['success'] = success
            result['message'] = "All memory cleared"
            
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

