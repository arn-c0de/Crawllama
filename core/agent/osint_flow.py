"""OSINT processing flow for SearchAgent."""
import asyncio
import logging
from typing import Optional

from core.robustness import safe_execute
from core.memory_store import get_memory_store
from utils.secure_hash import hmac_sha256_hex
from utils.validators import sanitize_for_logging

logger = logging.getLogger("crawllama")


class OSINTFlow:
    def __init__(self, agent):
        self.agent = agent

    def handle_osint_query(self, query: str) -> str:
        """
        Handle OSINT query with operators.
        Refactored: Main orchestrator method.
        """
        components = self._initialize_osint_components()
        if isinstance(components, str):
            return components

        parser, email_intel, phone_intel, domain_intel, ip_intel, social_intel, enhancer, compliance = components
        logger.info("OSINT query detected")

        compliance_result = self._check_osint_compliance(compliance, query)
        if compliance_result:
            return compliance_result

        parsed = self._parse_osint_query(parser, query)
        if isinstance(parsed, str):
            return parsed

        logger.info("Parsed OSINT query")
        response_parts = []

        if parsed.email and email_intel:
            email_parts = self._process_email_intelligence(parsed.email, email_intel)
            response_parts.extend(email_parts)

        if parsed.phone and phone_intel:
            phone_parts = self._process_phone_intelligence(parsed.phone, phone_intel)
            response_parts.extend(phone_parts)

        if parsed.domain and domain_intel:
            domain_parts = self._process_domain_intelligence(parsed.domain, domain_intel)
            response_parts.extend(domain_parts)

        if parsed.ip and ip_intel:
            ip_parts = self._process_ip_intelligence(parsed.ip, ip_intel)
            response_parts.extend(ip_parts)

        if parsed.username and social_intel:
            username_parts = self._process_username_intelligence(parsed.username, social_intel)
            response_parts.extend(username_parts)

        if parsed.forget_type:
            forget_parts = self._process_forget_command(parsed.forget_type, parsed.forget_value)
            response_parts.extend(forget_parts)

        if parsed.site or parsed.inurl or parsed.intext or parsed.intitle or parsed.filetype:
            search_parts = self._process_advanced_search(parser, parsed, query)
            response_parts.extend(search_parts)

        if not (parsed.email or parsed.phone or parsed.domain or parsed.ip or parsed.username) and enhancer:
            ai_parts = self._generate_ai_suggestions(enhancer, query)
            response_parts.extend(ai_parts)

        if not response_parts:
            response_parts.append("No OSINT operators detected or processed.")

        stats_parts = self._append_usage_stats(compliance)
        response_parts.extend(stats_parts)

        return "\n".join(response_parts)

    def handle_company_query(self, query: str) -> str:
        """Handle company-intelligence query without explicit OSINT operators."""
        try:
            from core.osint import OSINTCompliance, CompanyIntelligence
        except ImportError as e:
            logger.error(f"Failed to import company OSINT modules: {e}")
            return "⚠️ Company intelligence modules are not available."

        success, compliance = safe_execute(
            OSINTCompliance,
            config=self.agent.config,
            default=None,
            log_error=True
        )
        if not success or not compliance:
            return "⚠️ OSINT compliance could not be initialized."

        compliance_result = self._check_osint_compliance(compliance, query)
        if compliance_result:
            return compliance_result

        success, company_intel = safe_execute(
            CompanyIntelligence,
            config=self.agent.config,
            default=None,
            log_error=True
        )
        if not success or not company_intel:
            return "⚠️ Company intelligence could not be initialized."

        analysis = company_intel.analyze_company(query)
        report = company_intel.format_report(analysis)

        if not analysis.get("error"):
            self._save_company_session(analysis)

        # Persist likely domain for later follow-up in memory store.
        likely_domain = analysis.get("official_domain")
        if likely_domain:
            try:
                memory = get_memory_store()
                memory.remember_domain(
                    likely_domain,
                    metadata={
                        "source": "company_intelligence",
                        "query": sanitize_for_logging(query, "query")
                    }
                )
            except Exception as mem_error:
                logger.debug(f"Could not save company domain to memory: {mem_error}")

        stats_parts = self._append_usage_stats(compliance)
        return report + "\n" + "\n".join(stats_parts)

    def _initialize_osint_components(self):
        try:
            from core.osint import (
                OSINTQueryParser,
                EmailIntelligence,
                PhoneIntelligence,
                DomainIntelligence,
                IPIntelligence,
                SocialIntelligence,
                QueryEnhancer,
                OSINTCompliance
            )
        except ImportError as e:
            logger.error(f"Failed to import OSINT modules: {e}")
            return "⚠️ OSINT features are not available. Modules missing."

        success, parser = safe_execute(OSINTQueryParser, default=None, log_error=True)
        if not success or not parser:
            return "⚠️ OSINT Parser could not be initialized."

        success, email_intel = safe_execute(EmailIntelligence, default=None, log_error=True)
        success, phone_intel = safe_execute(PhoneIntelligence, default=None, log_error=True)
        success, domain_intel = safe_execute(DomainIntelligence, default=None, log_error=True)
        success, ip_intel = safe_execute(IPIntelligence, default=None, log_error=True)
        success, social_intel = safe_execute(SocialIntelligence, default=None, log_error=True)
        success, enhancer = safe_execute(QueryEnhancer, self.agent.llm, default=None, log_error=False)
        success, compliance = safe_execute(OSINTCompliance, config=self.agent.config, default=None, log_error=True)

        if not compliance:
            return "⚠️ OSINT Compliance konnte nicht initialisiert werden."

        return (parser, email_intel, phone_intel, domain_intel, ip_intel, social_intel, enhancer, compliance)

    def _check_osint_compliance(self, compliance, query: str):
        success, (allowed, reason) = safe_execute(
            compliance.check_query,
            query,
            "default",
            "general_osint",
            default=(False, "Compliance check failed"),
            log_error=True
        )

        if not success or not allowed:
            logger.warning("OSINT query blocked")
            if "terms of use" in reason.lower():
                return (
                    "⚠️ OSINT Features müssen erst aktiviert werden.\n\n"
                    "Starten Sie CrawlLama neu, um die Terms zu akzeptieren, oder akzeptieren Sie "
                    "die Terms manuell in der Konfiguration."
                )
            return f"⚠️ OSINT Query blockiert: {reason}"
        return None

    def _parse_osint_query(self, parser, query: str):
        success, parsed = safe_execute(
            parser.parse,
            query,
            default=None,
            log_error=True
        )
        if not success or not parsed:
            return f"⚠️ Error parsing OSINT query: {query}"
        return parsed

    def _sanitize_email_for_logging(self, email: str) -> str:
        email_hash = hmac_sha256_hex(email, length=8)
        return f"email_{email_hash}"

    def _sanitize_phone_for_logging(self, phone: str) -> str:
        phone_hash = hmac_sha256_hex(phone, length=8)
        return f"phone_{phone_hash}"

    def _process_email_intelligence(self, email: str, email_intel) -> list:
        logger.info(f"Processing email intelligence: {self._sanitize_email_for_logging(email)}")
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

        response_parts.extend(self._format_email_results(email_result, email))

        if email_result.get('valid'):
            online_parts = self._search_email_online(email)
            response_parts.extend(online_parts)

        return response_parts

    def _format_email_results(self, email_result: dict, email: str) -> list:
        parts = ["═══ Email Intelligence ═══\n"]
        parts.append(f"**Email:** {email_result.get('email', email)}")
        parts.append(f"**Valid:** {'✓' if email_result.get('valid') else '✗'} {email_result.get('valid', False)}")

        if email_result.get('valid'):
            parts.append(f"**Domain:** {email_result['domain']}")
            parts.append(f"**Username:** {email_result['username']}")
            parts.append(f"**Disposable:** {email_result['disposable']}")
            parts.append(f"**Domain exists:** {email_result['domain_exists']}")
            parts.append(f"**Confidence:** {email_result['confidence']:.2f}")

        return parts

    def _search_email_online(self, email: str) -> list:
        from core.osint.social_intel import SocialIntelligence
        from core.osint.email_intel import EmailIntelligence, EmailVulnerabilityIntel

        response_parts = ["\n═══ Platform & Breach Analysis ═══\n"]
        logger.info(f"Analyzing email presence: {self._sanitize_email_for_logging(email)}")

        try:
            social_intel = SocialIntelligence()

            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    raise RuntimeError("Event loop is closed")
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            social_results = loop.run_until_complete(
                social_intel.discover_profiles_by_email(email)
            )

            email_intel = EmailIntelligence()
            breach_info = email_intel.check_data_breaches(email)

            vuln_intel = EmailVulnerabilityIntel()
            vuln_info = vuln_intel.check_vulnerability(email)

            platform_count = 0
            if social_results.get('username_matches'):
                response_parts.append("**🔍 Found on Social Platforms:**\n")
                for match in social_results['username_matches']:
                    platform = match.get('platform', 'Unknown').title()
                    url = match.get('url', '')
                    profile_data = match.get('profile_data', {})

                    response_parts.append(f"✓ **{platform}**")
                    if profile_data.get('display_name'):
                        response_parts.append(f"    Name: {profile_data['display_name']}")
                    if url:
                        response_parts.append(f"    URL: {url}")
                    response_parts.append("")
                    platform_count += 1

            if breach_info.get('pwned'):
                response_parts.append("**⚠️ DATA BREACH ALERT:**\n")
                response_parts.append("**Status:** COMPROMISED")
                response_parts.append(f"**Breach Count:** {breach_info['breach_count']}")
                response_parts.append(f"**Paste Count:** {breach_info['paste_count']}")
                response_parts.append(f"**Severity:** {breach_info['severity'].upper()}")

                if breach_info.get('last_breach'):
                    response_parts.append(f"**Last Breach:** {breach_info['last_breach']}")

                if breach_info.get('breaches'):
                    response_parts.append("\n**Known Breaches:**")
                    for i, breach in enumerate(breach_info['breaches'][:10], 1):
                        breach_name = breach.get('Name') or breach.get('name') or breach.get('Title') or 'Unknown'
                        breach_date = breach.get('BreachDate') or breach.get('date') or breach.get('Date') or 'Unknown'
                        breach_desc = breach.get('Description') or breach.get('description') or ''

                        response_parts.append(f"  {i}. **{breach_name}** ({breach_date})")
                        if breach_desc and len(breach_desc) > 0:
                            desc_preview = breach_desc[:150] + '...' if len(breach_desc) > 150 else breach_desc
                            response_parts.append(f"     {desc_preview}")

                if breach_info.get('recommendations'):
                    response_parts.append("\n**🔒 Security Recommendations:**")
                    for rec in breach_info['recommendations'][:3]:
                        response_parts.append(f"  • {rec}")

                response_parts.append("")
            else:
                response_parts.append("**✅ Breach Status:** CLEAN")
                response_parts.append("No known data breaches found in HIBP database.\n")

            if vuln_info.get('vulnerable'):
                response_parts.append("**🔓 VULNERABILITY ALERT (Public Lists):**\n")
                response_parts.append("**Status:** EXPOSED IN PUBLIC LISTS")
                response_parts.append(f"**Leak Count:** {vuln_info['leak_count']}")
                response_parts.append(f"**Severity:** {vuln_info['severity'].upper()}")
                response_parts.append(f"**Found in:** {', '.join(vuln_info['found_in'])}")

                if vuln_info.get('breach_sources'):
                    response_parts.append("\n**📋 Leak Sources:**")
                    for i, source in enumerate(vuln_info['breach_sources'][:5], 1):
                        source_name = source.get('source', 'Unknown')
                        source_type = source.get('type', 'unknown')
                        response_parts.append(f"  {i}. {source_name} ({source_type})")

                response_parts.append("\n**🔐 Email Hashes (for anonymous lookup):**")
                response_parts.append(f"  MD5: {vuln_info['hashes']['md5']}")
                response_parts.append(f"  SHA1: {vuln_info['hashes']['sha1'][:16]}...")
                response_parts.append("")
            else:
                response_parts.append("**✅ Vulnerability Status:** NOT FOUND IN PUBLIC LISTS")
                response_parts.append("No email found in public credential dumps.\n")

            response_parts.append("**📊 Summary:**")
            response_parts.append(f"  • Platforms found: {platform_count}")
            response_parts.append(
                f"  • Breach status: {'⚠️ COMPROMISED' if breach_info.get('pwned') else '✅ CLEAN'}"
            )
            response_parts.append(
                f"  • Vulnerability status: {'🔓 EXPOSED' if vuln_info.get('vulnerable') else '✅ CLEAN'}"
            )

            if platform_count == 0 and not breach_info.get('pwned') and not vuln_info.get('vulnerable'):
                response_parts.append("\n**Note:** Limited online presence detected.")
                response_parts.append("This may indicate good privacy practices or a private email.")

            try:
                memory_store = get_memory_store()
                memory_store.remember_email(email, metadata={'source': 'osint_scan'})
                memory_store.update_email_breach_info(email, breach_info, vuln_info)
                logger.info(f"Saved breach data to memory for: {self._sanitize_email_for_logging(email)}")
            except Exception as mem_error:
                logger.error(f"Could not save breach data to memory: {mem_error}")

        except Exception as e:
            logger.error(f"Error in email platform analysis: {e}", exc_info=True)
            response_parts.append(f"**Error:** Could not complete analysis: {str(e)}")

        return response_parts

    def _process_phone_intelligence(self, phone: str, phone_intel) -> list:
        logger.info(f"Processing phone intelligence: {self._sanitize_phone_for_logging(phone)}")
        phone_result = phone_intel.analyze_phone(phone)

        response_parts = ["\n═══ Phone Intelligence ═══\n"]
        response_parts.append(f"**Phone:** {phone_result['input']}")
        response_parts.append(f"**Valid:** {'✓' if phone_result['valid'] else '✗'} {phone_result['valid']}")

        if phone_result['valid']:
            response_parts.extend(self._format_phone_results(phone_result))

            ai_queries = self._generate_phone_ai_suggestions(phone_result)
            if ai_queries:
                response_parts.append("\n═══ AI Analysis ═══\n")
                response_parts.append("**Entity Type:** phone")
                response_parts.append("\n**Alternative Queries:**")
                for query in ai_queries:
                    response_parts.append(f"  • {query}")

            online_parts = self._search_phone_online(phone_result)
            response_parts.extend(online_parts)

        return response_parts

    def _generate_phone_ai_suggestions(self, phone_result: dict) -> list:
        queries = []

        country = phone_result.get('country', '')
        phone_type = phone_result.get('type', 'unknown')
        carrier = phone_result.get('carrier', '')
        formatted = phone_result.get('formatted', '')

        type_map = {
            'fixed_line': 'landline',
            'mobile': 'mobile',
            'fixed_line_or_mobile': 'phone',
            'toll_free': 'toll-free number',
            'voip': 'VoIP number'
        }
        type_text = type_map.get(phone_type, 'phone number')

        if country and formatted:
            queries.append(f"{country} {type_text} {formatted}")

        if carrier and formatted:
            queries.append(f"{carrier} {formatted}")

        if phone_result.get('variations'):
            for var in phone_result['variations'][:2]:
                if var != phone_result['input'] and var != formatted:
                    queries.append(f'"{var}" contact')
                    break

        queries = list(dict.fromkeys(queries))[:3]
        return queries

    def _format_phone_results(self, phone_result: dict) -> list:
        parts = []
        parts.append(f"**Formatted:** {phone_result['formatted']}")
        parts.append(f"**Country:** {phone_result['country']}")
        parts.append(f"**Type:** {phone_result['type']}")
        if phone_result.get('carrier'):
            parts.append(f"**Carrier:** {phone_result['carrier']}")
        parts.append(f"**Confidence:** {phone_result['confidence']:.2f}")

        if phone_result.get('variations'):
            parts.append("\n**Phone Variations:**")
            for var in phone_result['variations'][:5]:
                parts.append(f"  • {var}")

        return parts

    def _search_phone_online(self, phone_result: dict) -> list:
        from tools.web_search import web_search

        response_parts = ["\n═══ Online Search Results ═══\n"]
        sanitized_phone = self._sanitize_phone_for_logging(phone_result['input'])
        logger.info(f"Searching web for phone: {sanitized_phone}")

        search_config = self.agent.config.get("search", {})
        osint_config = self.agent.config.get("osint", {})
        safesearch = osint_config.get("safesearch", "strict")
        search_queries = [f'"{var}"' for var in phone_result['variations'][:3]]

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

        unique_results = self._deduplicate_results(all_results)

        if unique_results:
            self.agent.session.last_search_results = unique_results
            self.agent.session.last_search_query = f'phone:{phone_result["input"]}'
            logger.info(f"Stored {len(unique_results)} phone search results in session state")

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

    def _process_domain_intelligence(self, domain: str, domain_intel) -> list:
        logger.info(f"Processing domain intelligence: {domain}")

        success, domain_result = safe_execute(
            domain_intel.analyze_domain,
            domain,
            default={'valid': False, 'domain': domain},
            log_error=True
        )

        if not success or not domain_result:
            return ["⚠️ Domain-Analyse fehlgeschlagen."]

        response_parts = ["\n═══ Domain Intelligence ═══\n"]

        success, formatted = safe_execute(
            domain_intel.format_results,
            domain_result,
            default="",
            log_error=True
        )

        if success and formatted:
            response_parts.append(formatted)
        else:
            response_parts.append(f"**Domain:** {domain_result.get('domain', domain)}")
            response_parts.append(f"**Valid:** {'✓' if domain_result.get('valid') else '✗'} {domain_result.get('valid', False)}")

            if domain_result.get('valid'):
                if domain_result.get('ips'):
                    response_parts.append(f"**IPs:** {', '.join(domain_result['ips'][:3])}")
                if domain_result.get('geolocation', {}).get('country'):
                    geo = domain_result['geolocation']
                    response_parts.append(
                        f"**Location:** {geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}"
                    )
                response_parts.append(f"**Confidence:** {domain_result.get('confidence', 0):.2f}")

        if domain_result.get('valid'):
            try:
                memory_store = get_memory_store()
                clean_domain = domain_result.get('domain', domain)
                if '://' in clean_domain:
                    clean_domain = clean_domain.split('://')[1]
                if '/' in clean_domain:
                    clean_domain = clean_domain.split('/')[0]

                metadata = {
                    'source': 'osint_scan',
                    'ips': domain_result.get('ips', []),
                    'confidence': domain_result.get('confidence', 0)
                }

                if domain_result.get('geolocation'):
                    metadata['geolocation'] = domain_result['geolocation']

                memory_store.remember_domain(clean_domain, metadata=metadata)
                logger.info("Saved domain to memory")
            except Exception as mem_error:
                logger.error(f"Could not save domain to memory: {mem_error}")

        self.agent.session.last_search_query = f'domain:{domain}'
        logger.info(f"Processed domain intelligence for {sanitize_for_logging(domain, 'domain')}")

        return response_parts

    def _process_ip_intelligence(self, ip: str, ip_intel) -> list:
        logger.info(f"Processing IP intelligence: {ip}")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                ip_result = loop.run_until_complete(ip_intel.lookup_ip(ip))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"IP analysis failed: {e}")
            return ["⚠️ IP-Analyse fehlgeschlagen."]

        response_parts = ["\n═══ IP Intelligence ═══\n"]

        success, formatted = safe_execute(
            ip_intel.format_results,
            ip_result,
            default="",
            log_error=True
        )

        if success and formatted:
            response_parts.append(formatted)
        else:
            response_parts.append(f"**IP:** {ip_result.get('ip', ip)}")
            response_parts.append(f"**Valid:** {'✓' if ip_result.get('valid') else '✗'} {ip_result.get('valid', False)}")

            if ip_result.get('valid'):
                response_parts.append(f"**Type:** {ip_result.get('type', 'Unknown')}")
                if ip_result.get('geolocation', {}).get('country'):
                    geo = ip_result['geolocation']
                    response_parts.append(
                        f"**Location:** {geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}"
                    )
                if ip_result.get('geolocation', {}).get('isp'):
                    response_parts.append(f"**ISP:** {ip_result['geolocation']['isp']}")
                response_parts.append(f"**Confidence:** {ip_result.get('confidence_score', 0):.2f}")

        if ip_result.get('valid'):
            try:
                memory_store = get_memory_store()

                metadata = {
                    'source': 'osint_scan',
                    'type': ip_result.get('type', 'Unknown'),
                    'confidence': ip_result.get('confidence_score', 0)
                }

                if ip_result.get('geolocation'):
                    metadata['geolocation'] = ip_result['geolocation']
                if ip_result.get('network_info'):
                    metadata['network_info'] = ip_result['network_info']

                memory_store.remember_ip(ip_result.get('ip', ip), metadata=metadata)
                logger.info(f"Saved IP to memory: {ip}")
            except Exception as mem_error:
                logger.error(f"Could not save IP to memory: {mem_error}")

        self.agent.session.last_search_query = f'ip:{ip}'
        logger.info(f"Processed IP intelligence for {ip}")

        return response_parts

    def _process_username_intelligence(self, username: str, social_intel) -> list:
        logger.info(f"Processing username intelligence: {username}")
        response_parts = []

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                username_result = loop.run_until_complete(social_intel.analyze_username(username))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"Username analysis failed: {e}")
            return ["⚠️ Username-Analyse fehlgeschlagen."]

        if not username_result:
            response_parts.append("⚠️ Keine Username-Daten gefunden.")
            return response_parts

        response_parts.append("\n═══ Username / Social Media Intelligence ═══\n")
        response_parts.append(f"**Username:** {username_result.get('username', username)}")

        platforms_found = username_result.get('platforms_found', [])
        if platforms_found:
            response_parts.append(f"**Platforms gefunden:** {len(platforms_found)}")
            response_parts.append("\n**Profile:**")
            for platform_data in platforms_found[:10]:
                platform_name = platform_data.get('platform', 'Unknown')
                profile_url = platform_data.get('url', '')
                confidence = platform_data.get('confidence', 0)
                response_parts.append(f"  • **{platform_name}** (Confidence: {confidence:.2f})")
                if profile_url:
                    response_parts.append(f"    URL: {profile_url}")
        else:
            response_parts.append("**Platforms gefunden:** 0 (Username auf keiner Plattform gefunden)")

        total_platforms = username_result.get('total_platforms_checked', 0)
        response_parts.append(f"\n**Gesamt geprüfte Platforms:** {total_platforms}")
        response_parts.append(f"**Confidence Score:** {username_result.get('overall_confidence', 0):.2f}")

        if platforms_found:
            try:
                memory_store = get_memory_store()

                metadata = {
                    'source': 'osint_scan',
                    'platforms_found': len(platforms_found),
                    'platforms': [p.get('platform') for p in platforms_found[:5]],
                    'confidence': username_result.get('overall_confidence', 0)
                }

                memory_store.remember_username(username, metadata=metadata)
                logger.info(f"Saved username to memory: {username}")
            except Exception as mem_error:
                logger.error(f"Could not save username to memory: {mem_error}")

        self.agent.session.last_search_query = f'username:{username}'
        logger.info(f"Processed username intelligence for {username}")

        return response_parts

    def _deduplicate_results(self, results: list) -> list:
        seen_urls = set()
        unique_results = []
        for result in results:
            url = result.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        return unique_results

    def _process_forget_command(self, forget_type: str, forget_value: str) -> list:
        memory = get_memory_store()
        response_parts = ["\n═══ Memory Store Forget ═══\n"]

        try:
            if forget_type.lower() == 'all':
                memory.clear_all()
                response_parts.append("✅ **Alle Einträge aus dem Speicher gelöscht.**")
                logger.info("Cleared all memory entries via forget:all command")
                return response_parts

            if forget_type.lower() == 'category':
                category = forget_value.lower()
                if category in ['email', 'emails', 'e-mail', 'e-mails']:
                    category = 'emails'
                elif category in ['phone', 'phones', 'telefon', 'telefonnummern']:
                    category = 'phones'
                elif category in ['ip', 'ips']:
                    category = 'ips'
                elif category in ['username', 'usernames', 'benutzername', 'benutzernamen']:
                    category = 'usernames'
                elif category in ['domain', 'domains']:
                    category = 'domains'
                elif category in ['note', 'notes', 'notizen']:
                    category = 'notes'
                else:
                    response_parts.append(f"⚠️ **Unknown category:** {forget_value}")
                    response_parts.append("Available categories: emails, phones, ips, usernames, domains, notes")
                    return response_parts

                if memory.clear_category(category):
                    count = {
                        'emails': 'emails',
                        'phones': 'phone numbers',
                        'ips': 'IP addresses',
                        'usernames': 'usernames',
                        'domains': 'domains',
                        'notes': 'notes'
                    }
                    response_parts.append(f"✅ **All {count.get(category, category)} deleted from memory.**")
                    logger.info(f"Cleared category {category} via forget:category:{forget_value}")
                else:
                    response_parts.append(f"⚠️ **Could not delete category:** {category}")
                return response_parts

            deleted = False
            if forget_type.lower() in ['email', 'emails']:
                deleted = memory.forget_email(forget_value)
                item_type = "email"
            elif forget_type.lower() in ['phone', 'phones']:
                deleted = memory.forget_phone(forget_value)
                item_type = "phone number"
            elif forget_type.lower() in ['ip', 'ips']:
                deleted = memory.forget_ip(forget_value)
                item_type = "IP address"
            elif forget_type.lower() in ['username', 'usernames']:
                deleted = memory.forget_username(forget_value)
                item_type = "username"
            else:
                response_parts.append(f"⚠️ **Unknown type:** {forget_type}")
                response_parts.append("Available types: email, phone, ip, username, category, all")
                return response_parts

            if deleted:
                response_parts.append(f"✅ **{item_type} deleted:** {forget_value}")
                logger.info(f"Forgot {forget_type}:{forget_value} from memory")
            else:
                response_parts.append(f"⚠️ **{item_type} not found:** {forget_value}")
                logger.info(f"Failed to forget {forget_type}:{forget_value} - not found in memory")

        except Exception as e:
            logger.error(f"Error processing forget command: {e}", exc_info=True)
            response_parts.append(f"⚠️ **Error deleting:** {str(e)}")

        return response_parts

    def _process_advanced_search(self, parser, parsed, query: str) -> list:
        response_parts = ["\n═══ Advanced Search Query ═══\n"]
        response_parts.append(f"**Original:** {query}")
        response_parts.append("**Parsed:**")

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
        if parsed.country:
            response_parts.append(f"  • Country: {parsed.country}")
        if parsed.lang:
            response_parts.append(f"  • Language: {parsed.lang}")
        if parsed.region:
            response_parts.append(f"  • Region: {parsed.region}")
        if parsed.exclude:
            response_parts.append(f"  • Exclude: {', '.join(parsed.exclude)}")

        search_query = parser.build_search_query(parsed)
        response_parts.append(f"\n**Optimized Search Query:**\n`{search_query}`")

        search_results_parts = self._execute_osint_search(search_query, parsed)
        response_parts.extend(search_results_parts)

        return response_parts

    def _execute_osint_search(self, search_query: str, parsed) -> list:
        from tools.web_search import search_with_fallback, resolve_region_from_preferences

        response_parts = []
        osint_config = self.agent.config.get("osint", {})
        search_config = self.agent.config.get("search", {})
        max_results = osint_config.get("max_results", 25)
        default_region = search_config.get("region", "de-de")
        safesearch = osint_config.get("safesearch", "strict")
        ranking_profile = osint_config.get(
            "ranking_profile",
            search_config.get("ranking_profile", "osint")
        )
        session_max_results = osint_config.get("session_max_results", 8)
        context_max_results = osint_config.get("context_max_results", 6)
        max_snippet_chars = osint_config.get("max_snippet_chars", 220)
        region = resolve_region_from_preferences(
            default_region=default_region,
            region=getattr(parsed, "region", None),
            country=getattr(parsed, "country", None),
            lang=getattr(parsed, "lang", None),
        )

        logger.info(
            f"Executing OSINT search: {search_query} (max_results={max_results}, region={region}, safesearch={safesearch})"
        )
        results = search_with_fallback(
            search_query,
            max_results=max_results,
            region=region,
            safesearch=safesearch,
            ranking_profile=ranking_profile,
        )

        if results:
            compact_results = self.agent._compact_search_results(
                results,
                max_results=session_max_results,
                max_snippet_chars=max_snippet_chars,
            )
            context_results = compact_results[:max(1, context_max_results)]

            self.agent.session.last_search_results = compact_results
            self.agent.session.last_search_query = search_query
            logger.info(
                "Stored %s compact OSINT search results in session state (context uses %s)",
                len(compact_results),
                len(context_results),
            )

            response_parts.append("\n**Search Results:**")
            for i, result in enumerate(context_results, 1):
                response_parts.append(f"\n[{i}] **{result.get('title', 'No Title')}**")
                response_parts.append(f"    {result.get('url', '')}")
                if result.get('snippet'):
                    response_parts.append(f"    {result.get('snippet', '')[:200]}...")

        return response_parts

    def _generate_ai_suggestions(self, enhancer, query: str) -> list:
        response_parts = []
        try:
            entity_type = enhancer.identify_entity_type(query)
            response_parts.append("\n═══ AI Analysis ═══\n")
            response_parts.append(f"**Entity Type:** {entity_type}")

            variations = enhancer.generate_variations(query, max_variations=3)
            if variations:
                response_parts.append("\n**Alternative Queries:**")
                for var in variations:
                    response_parts.append(f"  • {var}")
        except Exception as e:
            logger.debug(f"AI suggestions skipped: {e}")

        return response_parts

    def _save_company_session(self, analysis: dict) -> None:
        """Persist the last company intelligence analysis to data/session.json."""
        import json
        from pathlib import Path
        from datetime import datetime, timezone

        session_path = Path(__file__).parent.parent.parent / "data" / "session.json"

        sources_by_cat = analysis.get("sources_by_category", {})
        top_sources = []
        for cat, sources in sources_by_cat.items():
            for src in sources[:5]:
                snippet = src.get("snippet", "")
                top_sources.append({
                    "category": cat,
                    "title": src.get("title", ""),
                    "url": src.get("url", ""),
                    "snippet": snippet[:200] if snippet else "",
                })

        session_data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "type": "company_intelligence",
            "company_name": analysis.get("company_name", ""),
            "official_domain": analysis.get("official_domain", "") or None,
            "source_count": analysis.get("source_count", 0),
            "leadership": analysis.get("leadership_signals", []),
            "structure": analysis.get("structure_signals", []),
            "risks": analysis.get("risk_signals", []),
            "domains": analysis.get("domains", []),
            "top_sources": top_sources,
            "domain_intelligence": analysis.get("domain_intelligence", {}),
        }

        try:
            session_path.parent.mkdir(parents=True, exist_ok=True)
            with session_path.open("w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            logger.debug("Company analysis saved to %s", session_path)
        except Exception as e:
            logger.debug("Could not save company session: %s", e)

    def _append_usage_stats(self, compliance) -> list:
        stats = compliance.get_usage_stats("default")
        parts = [
            "\n\n═══ Usage Stats ═══",
            f"Queries this hour: {stats['total_requests_last_hour']}",
            "Remaining limits:",
            f"  • Email: {stats['remaining_limits']['email_search']}/50",
            f"  • Phone: {stats['remaining_limits']['phone_search']}/50",
            f"  • General: {stats['remaining_limits']['general_osint']}/100"
        ]
        return parts
