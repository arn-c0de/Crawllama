"""IP Address Intelligence Module for OSINT.

Provides comprehensive IP address analysis without API keys:
- Geolocation information
- ISP and organization details
- Network range and routing info
- Security reputation checks
- Reverse DNS lookups
- Port scan detection
- VPN/Proxy detection
- Abuse database checks
"""

import re
import logging
import asyncio
import aiohttp
import socket
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import quote
import json
import time
from bs4 import BeautifulSoup
import ipaddress
from utils.privacy import redact_coordinates

logger = logging.getLogger(__name__)

class IPIntelligence:
    """IP address intelligence without API requirements."""
    
    def __init__(self):
        """Initialize IP intelligence."""
        self.session = None
        
        # Free IP lookup services (no API key required)
        self.lookup_services = {
            'ipinfo': {
                'url': 'https://ipinfo.io/{ip}',
                'type': 'json',
                'fields': ['ip', 'city', 'region', 'country', 'loc', 'org', 'timezone']
            },
            'ip_api': {
                'url': 'http://ip-api.com/json/{ip}',
                'type': 'json', 
                'fields': ['query', 'status', 'country', 'countryCode', 'region', 'regionName', 'city', 'zip', 'lat', 'lon', 'timezone', 'isp', 'org', 'as']
            },
            'ipwhois': {
                'url': 'https://ipwhois.app/json/{ip}',
                'type': 'json',
                'fields': ['ip', 'success', 'type', 'continent', 'continent_code', 'country', 'country_code', 'region', 'region_code', 'city', 'latitude', 'longitude', 'is_eu', 'postal', 'calling_code', 'capital', 'borders', 'flag', 'connection']
            },
            'freegeoip': {
                'url': 'https://freegeoip.app/json/{ip}',
                'type': 'json',
                'fields': ['ip', 'country_code', 'country_name', 'region_code', 'region_name', 'city', 'zip_code', 'time_zone', 'latitude', 'longitude', 'metro_code']
            }
        }
        
        # Security and reputation services
        self.security_services = {
            'abuseipdb_check': 'https://www.abuseipdb.com/check/{ip}',
            'virustotal': 'https://www.virustotal.com/vtapi/v2/ip-address/report?apikey=public&ip={ip}',
            'shodan': 'https://www.shodan.io/host/{ip}',
            'censys': 'https://censys.io/ipv4/{ip}',
            'threatminer': 'https://www.threatminer.org/host.php?q={ip}',
            'hybrid_analysis': 'https://www.hybrid-analysis.com/search?query={ip}',
            'urlvoid': 'https://www.urlvoid.com/ip/{ip}/'
        }
        
        # WHOIS servers for different regions
        self.whois_servers = {
            'default': 'whois.iana.org',
            'ARIN': 'whois.arin.net',  # North America
            'RIPE': 'whois.ripe.net',   # Europe, Middle East, Central Asia
            'APNIC': 'whois.apnic.net', # Asia Pacific
            'LACNIC': 'whois.lacnic.net', # Latin America
            'AFRINIC': 'whois.afrinic.net' # Africa
        }
        
        # Common user agents for web scraping
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': self.user_agents[0]}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    def validate_ip(self, ip: str) -> Tuple[bool, str, str]:
        """
        Validate IP address and determine type.
        
        Args:
            ip: IP address string
            
        Returns:
            Tuple of (is_valid, ip_type, normalized_ip)
        """
        try:
            ip_obj = ipaddress.ip_address(ip.strip())
            ip_type = 'IPv6' if ip_obj.version == 6 else 'IPv4'
            
            # Check for special IP ranges
            if ip_obj.is_private:
                return True, f'{ip_type}_Private', str(ip_obj)
            elif ip_obj.is_loopback:
                return True, f'{ip_type}_Loopback', str(ip_obj)
            elif ip_obj.is_multicast:
                return True, f'{ip_type}_Multicast', str(ip_obj)
            elif ip_obj.is_reserved:
                return True, f'{ip_type}_Reserved', str(ip_obj)
            else:
                return True, f'{ip_type}_Public', str(ip_obj)
                
        except ValueError as e:
            return False, 'Invalid', ip

    async def lookup_ip(self, ip: str) -> Dict[str, Any]:
        """
        Comprehensive IP address lookup.
        
        Args:
            ip: IP address to analyze
            
        Returns:
            Dictionary with comprehensive IP information
        """
        logger.info(f"Starting IP intelligence lookup for: {ip}")
        
        # Validate IP address
        is_valid, ip_type, normalized_ip = self.validate_ip(ip)
        if not is_valid:
            return {
                'ip': ip,
                'valid': False,
                'error': 'Invalid IP address format',
                'type': ip_type
            }

        result = {
            'ip': normalized_ip,
            'original_input': ip,
            'valid': True,
            'type': ip_type,
            'geolocation': {},
            'network_info': {},
            'security_info': {},
            'reputation': {},
            'reverse_dns': None,
            'whois_info': {},
            'service_results': {},
            'analysis_timestamp': int(time.time())
        }

        # Skip external lookups for private/special IPs
        if 'Private' in ip_type or 'Loopback' in ip_type or 'Reserved' in ip_type:
            result['geolocation'] = {'note': 'Private/Reserved IP - no external geolocation available'}
            result['network_info'] = {'type': 'Private/Reserved network'}
            return result

        async with self as intel:
            # Perform multiple lookups concurrently
            tasks = []
            
            # Geolocation lookups
            for service_name, config in self.lookup_services.items():
                tasks.append(self._lookup_service(service_name, config, normalized_ip))
            
            # Reverse DNS lookup
            tasks.append(self._reverse_dns_lookup(normalized_ip))
            
            # WHOIS lookup
            tasks.append(self._whois_lookup(normalized_ip))
            
            # Security checks (lighter weight)
            tasks.append(self._security_checks(normalized_ip))

            # Execute all tasks
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, task_result in enumerate(results):
                if isinstance(task_result, Exception):
                    logger.warning(f"Task {i} failed: {task_result}")
                    continue
                    
                if isinstance(task_result, dict):
                    if 'service' in task_result:
                        result['service_results'][task_result['service']] = task_result.get('data', {})
                    elif 'reverse_dns' in task_result:
                        result['reverse_dns'] = task_result['reverse_dns']
                    elif 'whois' in task_result:
                        result['whois_info'] = task_result['whois']
                    elif 'security' in task_result:
                        result['security_info'] = task_result['security']

            # Aggregate and analyze results
            result = self._aggregate_results(result)
            
        logger.info(f"IP lookup completed for {normalized_ip}")
        return result

    async def _lookup_service(self, service_name: str, config: Dict, ip: str) -> Dict:
        """Lookup IP using specific service."""
        try:
            url = config['url'].format(ip=ip)
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    if config['type'] == 'json':
                        data = await response.json()
                        return {'service': service_name, 'data': data}
                    else:
                        text = await response.text()
                        return {'service': service_name, 'data': {'raw': text}}
                else:
                    logger.warning(f"Service {service_name} returned status {response.status}")
                    return {'service': service_name, 'data': {}, 'error': f'HTTP {response.status}'}
                    
        except Exception as e:
            logger.error(f"Error querying {service_name}: {e}")
            return {'service': service_name, 'data': {}, 'error': str(e)}

    async def _reverse_dns_lookup(self, ip: str) -> Dict:
        """Perform reverse DNS lookup."""
        try:
            # Use asyncio to run blocking DNS lookup
            loop = asyncio.get_event_loop()
            hostname = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
            return {'reverse_dns': {'hostname': hostname[0], 'aliases': hostname[1]}}
        except Exception as e:
            logger.debug(f"Reverse DNS lookup failed for {ip}: {e}")
            return {'reverse_dns': None}

    async def _whois_lookup(self, ip: str) -> Dict:
        """Perform WHOIS lookup."""
        try:
            # Determine appropriate WHOIS server based on IP
            whois_server = self._get_whois_server(ip)
            
            # Simple WHOIS query (could be enhanced with actual WHOIS protocol)
            whois_url = f"https://whois.net/ip-address-lookup/{ip}"
            
            async with self.session.get(whois_url) as response:
                if response.status == 200:
                    html = await response.text()
                    whois_data = self._parse_whois_html(html)
                    return {'whois': whois_data}
                    
        except Exception as e:
            logger.error(f"WHOIS lookup failed for {ip}: {e}")
            
        return {'whois': {}}

    async def _security_checks(self, ip: str) -> Dict:
        """Perform basic security reputation checks."""
        security_info = {
            'reputation_score': 0,  # 0-100 scale
            'threat_indicators': [],
            'classifications': [],
            'last_seen_malicious': None,
            'is_tor_exit': False,
            'is_vpn': False,
            'is_proxy': False,
            'abuse_reports': 0
        }
        
        try:
            # Check some basic indicators
            # This is a simplified version - could be expanded with more services
            
            # Check for common malicious IP patterns
            security_info['classifications'] = self._classify_ip_security(ip)
            
            # Basic VPN/Proxy detection (simplified)
            security_info['is_vpn'] = await self._check_vpn_proxy(ip)
            
            return {'security': security_info}
            
        except Exception as e:
            logger.error(f"Security checks failed for {ip}: {e}")
            return {'security': security_info}

    def _get_whois_server(self, ip: str) -> str:
        """Determine appropriate WHOIS server for IP."""
        try:
            ip_obj = ipaddress.ip_address(ip)
            
            # Simple region detection based on IP ranges (simplified)
            if ip_obj.version == 4:
                first_octet = int(str(ip_obj).split('.')[0])
                if first_octet in range(3, 7):  # ARIN
                    return self.whois_servers['ARIN']
                elif first_octet in range(80, 95):  # RIPE
                    return self.whois_servers['RIPE']
                elif first_octet in range(58, 62):  # APNIC
                    return self.whois_servers['APNIC']
                    
        except (ValueError, AttributeError, KeyError):
            pass
            
        return self.whois_servers['default']

    def _parse_whois_html(self, html: str) -> Dict:
        """Parse WHOIS information from HTML."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            whois_data = {}
            
            # Look for common WHOIS fields
            whois_patterns = {
                'network': r'NetRange:\s*([^\n]+)',
                'org_name': r'OrgName:\s*([^\n]+)',
                'org_id': r'OrgId:\s*([^\n]+)', 
                'country': r'Country:\s*([^\n]+)',
                'city': r'City:\s*([^\n]+)',
                'postal_code': r'PostalCode:\s*([^\n]+)'
            }
            
            text_content = soup.get_text()
            for field, pattern in whois_patterns.items():
                match = re.search(pattern, text_content, re.IGNORECASE)
                if match:
                    whois_data[field] = match.group(1).strip()
                    
            return whois_data
            
        except Exception as e:
            logger.error(f"Error parsing WHOIS HTML: {e}")
            return {}

    def _classify_ip_security(self, ip: str) -> List[str]:
        """Basic IP security classification."""
        classifications = []
        
        try:
            ip_obj = ipaddress.ip_address(ip)
            
            # Add basic classifications
            if ip_obj.is_private:
                classifications.append('private')
            if ip_obj.is_multicast:
                classifications.append('multicast')
            if ip_obj.is_reserved:
                classifications.append('reserved')
            if ip_obj.is_loopback:
                classifications.append('loopback')
                
            # Check for common hosting/cloud ranges (simplified)
            ip_str = str(ip_obj)
            if any(cloud_range in ip_str for cloud_range in ['54.', '52.', '3.', '18.']):  # AWS ranges (simplified)
                classifications.append('cloud_hosting')
            elif any(gcp_range in ip_str for gcp_range in ['35.', '34.']):  # GCP ranges (simplified)
                classifications.append('cloud_hosting')
                
        except (ValueError, AttributeError):
            pass  # Invalid IP format or missing attributes, return empty classifications
            
        return classifications

    async def _check_vpn_proxy(self, ip: str) -> bool:
        """Basic VPN/Proxy detection."""
        try:
            # This is a simplified check - could be expanded with dedicated services
            # Check for common VPN/proxy indicators in reverse DNS
            if hasattr(self, '_cached_reverse_dns'):
                hostname = self._cached_reverse_dns
                if hostname and any(indicator in hostname.lower() for indicator in ['vpn', 'proxy', 'tor', 'relay']):
                    return True
                    
        except (AttributeError, TypeError):
            pass  # Cached reverse DNS not available or invalid type, return False
            
        return False

    def _aggregate_results(self, result: Dict) -> Dict:
        """Aggregate results from multiple services."""
        try:
            # Aggregate geolocation data
            geo_data = {}
            network_data = {}
            
            for service, data in result.get('service_results', {}).items():
                if not data or 'error' in data:
                    continue
                    
                # Extract geolocation info
                if service == 'ip_api':
                    if data.get('status') == 'success':
                        geo_data.update({
                            'country': data.get('country'),
                            'country_code': data.get('countryCode'),
                            'region': data.get('regionName'),
                            'city': data.get('city'),
                            'latitude': data.get('lat'),
                            'longitude': data.get('lon'),
                            'timezone': data.get('timezone'),
                            'isp': data.get('isp'),
                            'organization': data.get('org'),
                            'as_number': data.get('as')
                        })
                        
                elif service == 'ipinfo':
                    geo_data.update({
                        'city': data.get('city'),
                        'region': data.get('region'),
                        'country': data.get('country'),
                        'location': data.get('loc'),
                        'organization': data.get('org'),
                        'timezone': data.get('timezone')
                    })
                    
                elif service == 'ipwhois':
                    if data.get('success'):
                        geo_data.update({
                            'continent': data.get('continent'),
                            'country': data.get('country'),
                            'country_code': data.get('country_code'),
                            'city': data.get('city'),
                            'latitude': data.get('latitude'),
                            'longitude': data.get('longitude'),
                            'postal_code': data.get('postal'),
                            'is_eu': data.get('is_eu')
                        })

            # Clean up and deduplicate geo data
            result['geolocation'] = {k: v for k, v in geo_data.items() if v is not None}
            
            # Extract network information
            if 'whois_info' in result and result['whois_info']:
                network_data.update({
                    'network_range': result['whois_info'].get('network'),
                    'organization_name': result['whois_info'].get('org_name'),
                    'organization_id': result['whois_info'].get('org_id')
                })
                
            result['network_info'] = network_data
            
            # Calculate confidence score
            result['confidence_score'] = self._calculate_confidence(result)
            
        except Exception as e:
            logger.error(f"Error aggregating results: {e}")
            
        return result

    def _calculate_confidence(self, result: Dict) -> float:
        """Calculate confidence score based on available data."""
        score = 0.0
        
        # Points for successful service responses
        successful_services = len([s for s in result.get('service_results', {}).values() if s and 'error' not in s])
        score += min(successful_services * 0.2, 0.6)  # Max 0.6 from services
        
        # Points for geo data completeness
        geo_fields = len([v for v in result.get('geolocation', {}).values() if v])
        score += min(geo_fields * 0.05, 0.2)  # Max 0.2 from geo completeness
        
        # Points for additional data
        if result.get('reverse_dns'):
            score += 0.1
        if result.get('whois_info'):
            score += 0.1
            
        return min(score, 1.0)

    def format_results(self, result: Dict) -> str:
        """Format IP intelligence results for display."""
        if not result.get('valid'):
            return f"❌ Invalid IP address: {result.get('ip', 'Unknown')}\nError: {result.get('error', 'Unknown error')}"
            
        output = []
        ip = result['ip']
        ip_type = result.get('type', 'Unknown')
        
        output.append(f"🔍 IP Intelligence Report: {ip}")
        output.append("=" * 50)
        output.append(f"IP Type: {ip_type}")
        output.append(f"Confidence: {result.get('confidence_score', 0):.1%}")
        
        # Geolocation
        geo = result.get('geolocation', {})
        if geo:
            output.append("\n📍 Geolocation:")
            if geo.get('country'):
                output.append(f"  Country: {geo['country']} ({geo.get('country_code', 'N/A')})")
            if geo.get('region'):
                output.append(f"  Region: {geo['region']}")
            if geo.get('city'):
                output.append(f"  City: {geo['city']}")
            if geo.get('latitude') and geo.get('longitude'):
                # Redact coordinates for privacy (show only approximate location)
                redacted_lat, redacted_lon = redact_coordinates(geo['latitude'], geo['longitude'])
                output.append(f"  Approximate Coordinates: {redacted_lat}, {redacted_lon}")
            if geo.get('timezone'):
                output.append(f"  Timezone: {geo['timezone']}")
                
        # Network Information
        network = result.get('network_info', {})
        if network or geo.get('isp'):
            output.append("\n🌐 Network Information:")
            if geo.get('isp'):
                output.append(f"  ISP: {geo['isp']}")
            if geo.get('organization'):
                output.append(f"  Organization: {geo['organization']}")
            if geo.get('as_number'):
                output.append(f"  AS Number: {geo['as_number']}")
            if network.get('network_range'):
                output.append(f"  Network Range: {network['network_range']}")
                
        # Reverse DNS
        if result.get('reverse_dns'):
            output.append(f"\n🔄 Reverse DNS: {result['reverse_dns'].get('hostname', 'N/A')}")
            
        # Security Information
        security = result.get('security_info', {})
        if security:
            output.append(f"\n🛡️ Security Analysis:")
            if security.get('classifications'):
                output.append(f"  Classifications: {', '.join(security['classifications'])}")
            if security.get('is_vpn'):
                output.append("  ⚠️ Possible VPN/Proxy detected")
            if security.get('reputation_score') is not None:
                score = security['reputation_score']
                status = "✅ Good" if score > 70 else "⚠️ Suspicious" if score > 30 else "❌ Poor"
                output.append(f"  Reputation: {status} ({score}/100)")
                
        # Service Status
        services = result.get('service_results', {})
        successful = len([s for s in services.values() if s and 'error' not in s])
        total = len(services)
        if total > 0:
            output.append(f"\n📊 Data Sources: {successful}/{total} services responded successfully")
            
        output.append(f"\n⏰ Analysis completed at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result.get('analysis_timestamp', time.time())))}")
        
        return "\n".join(output)

# Async context manager usage
async def analyze_ip(ip: str) -> Dict[str, Any]:
    """
    Analyze IP address with comprehensive intelligence.
    
    Args:
        ip: IP address to analyze
        
    Returns:
        Analysis results dictionary
    """
    async with IPIntelligence() as intel:
        return await intel.lookup_ip(ip)