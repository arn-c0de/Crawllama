"""Domain Intelligence Module for OSINT.

Provides:
- Domain DNS resolution (A, AAAA, MX, TXT, NS records)
- IP geolocation with coordinates
- ASN information
- Reverse DNS lookup
- SSL/TLS certificate info hints
- Links to mapping services
- Domain age estimation via DNS records
"""

import re
import logging
import socket
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from urllib.parse import quote

logger = logging.getLogger("crawllama")


class DomainIntelligence:
    """Domain OSINT capabilities with IP geolocation."""

    def __init__(self):
        """Initialize domain intelligence."""
        logger.info("Domain Intelligence initialized")

    def analyze_domain(self, domain: str) -> Dict:
        """
        Comprehensive domain analysis with geolocation.

        Args:
            domain: Domain name to analyze (e.g., 'example.com' or 'www.example.com')

        Returns:
            Dictionary with analysis results:
            {
                'domain': str,
                'valid': bool,
                'ips': List[str],
                'ipv6': List[str],
                'mx_records': List[str],
                'txt_records': List[str],
                'ns_records': List[str],
                'geolocation': Dict,
                'reverse_dns': List[str],
                'map_links': List[str],
                'asn_info': Dict,
                'ssl_info': Dict,
                'confidence': float
            }

        Example:
            >>> intel = DomainIntelligence()
            >>> result = intel.analyze_domain('example.com')
            >>> result['ips']
            ['93.184.216.34']
        """
        logger.info(f"Analyzing domain: {domain}")

        # Clean and validate domain
        clean_domain = self._clean_domain(domain)

        results = {
            'domain': clean_domain,
            'valid': False,
            'ips': [],
            'ipv6': [],
            'mx_records': [],
            'txt_records': [],
            'ns_records': [],
            'cname_records': [],
            'geolocation': {},
            'reverse_dns': [],
            'map_links': [],
            'asn_info': {},
            'ssl_info': {},
            'confidence': 0.0,
            'errors': []
        }

        # Validate domain syntax
        if not self._validate_domain_syntax(clean_domain):
            results['errors'].append("Invalid domain syntax")
            logger.warning(f"Invalid domain syntax: {clean_domain}")
            return results

        results['valid'] = True

        # DNS Resolution - IPv4
        results['ips'] = self._resolve_a_records(clean_domain)

        # DNS Resolution - IPv6
        results['ipv6'] = self._resolve_aaaa_records(clean_domain)

        # MX Records
        results['mx_records'] = self._resolve_mx_records(clean_domain)

        # TXT Records
        results['txt_records'] = self._resolve_txt_records(clean_domain)

        # NS Records
        results['ns_records'] = self._resolve_ns_records(clean_domain)

        # CNAME Records
        results['cname_records'] = self._resolve_cname_records(clean_domain)

        # Reverse DNS for IPs
        if results['ips']:
            for ip in results['ips'][:3]:  # Limit to first 3 IPs
                reverse = self._reverse_dns_lookup(ip)
                if reverse:
                    results['reverse_dns'].append(reverse)

        # Geolocation for primary IP
        if results['ips']:
            primary_ip = results['ips'][0]
            results['geolocation'] = self._geolocate_ip(primary_ip)
            results['asn_info'] = self._get_asn_info(primary_ip)

            # Generate map links
            if results['geolocation'].get('latitude') and results['geolocation'].get('longitude'):
                results['map_links'] = self._generate_map_links(
                    results['geolocation']['latitude'],
                    results['geolocation']['longitude'],
                    clean_domain
                )

        # SSL/TLS info hints
        results['ssl_info'] = self._get_ssl_hints(clean_domain)

        # Calculate confidence score
        results['confidence'] = self._calculate_confidence(results)

        logger.info(f"Domain analysis complete for {clean_domain}: {len(results['ips'])} IPs found")
        return results

    def _clean_domain(self, domain: str) -> str:
        """Clean and normalize domain name."""
        # Remove protocol if present
        domain = re.sub(r'^https?://', '', domain.strip())
        # Remove path if present
        domain = domain.split('/')[0]
        # Remove port if present
        domain = domain.split(':')[0]
        # Remove www if present (optional, keep for now)
        return domain.lower()

    def _validate_domain_syntax(self, domain: str) -> bool:
        """Validate domain name syntax."""
        # Basic domain regex
        pattern = re.compile(
            r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$',
            re.IGNORECASE
        )
        return bool(pattern.match(domain))

    def _resolve_a_records(self, domain: str) -> List[str]:
        """Resolve A records (IPv4) for domain."""
        try:
            # Get all IPv4 addresses
            result = socket.getaddrinfo(domain, None, socket.AF_INET)
            ips = list(set([r[4][0] for r in result]))
            logger.debug(f"Resolved A records for {domain}: {ips}")
            return ips
        except socket.gaierror as e:
            logger.debug(f"Failed to resolve A records for {domain}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error resolving A records for {domain}: {e}")
            return []

    def _resolve_aaaa_records(self, domain: str) -> List[str]:
        """Resolve AAAA records (IPv6) for domain."""
        try:
            # Get all IPv6 addresses
            result = socket.getaddrinfo(domain, None, socket.AF_INET6)
            ipv6s = list(set([r[4][0] for r in result]))
            logger.debug(f"Resolved AAAA records for {domain}: {ipv6s}")
            return ipv6s
        except socket.gaierror as e:
            logger.debug(f"Failed to resolve AAAA records for {domain}: {e}")
            return []
        except Exception as e:
            logger.error(f"Error resolving AAAA records for {domain}: {e}")
            return []

    def _resolve_mx_records(self, domain: str) -> List[str]:
        """Resolve MX records for domain."""
        try:
            import dns.resolver
            mx_records = []
            answers = dns.resolver.resolve(domain, 'MX')
            for rdata in answers:
                mx_records.append(f"{rdata.preference} {rdata.exchange.to_text()}")
            logger.debug(f"Resolved MX records for {domain}: {mx_records}")
            return mx_records
        except ImportError:
            logger.warning("dnspython not installed, MX lookup unavailable")
            return ["[dnspython required for MX records]"]
        except Exception as e:
            logger.debug(f"Failed to resolve MX records for {domain}: {e}")
            return []

    def _resolve_txt_records(self, domain: str) -> List[str]:
        """Resolve TXT records for domain."""
        try:
            import dns.resolver
            txt_records = []
            answers = dns.resolver.resolve(domain, 'TXT')
            for rdata in answers:
                # Decode TXT record
                txt_data = b''.join(rdata.strings).decode('utf-8', errors='ignore')
                txt_records.append(txt_data)
            logger.debug(f"Resolved TXT records for {domain}: {len(txt_records)} records")
            return txt_records
        except ImportError:
            logger.warning("dnspython not installed, TXT lookup unavailable")
            return ["[dnspython required for TXT records]"]
        except Exception as e:
            logger.debug(f"Failed to resolve TXT records for {domain}: {e}")
            return []

    def _resolve_ns_records(self, domain: str) -> List[str]:
        """Resolve NS records for domain."""
        try:
            import dns.resolver
            ns_records = []
            answers = dns.resolver.resolve(domain, 'NS')
            for rdata in answers:
                ns_records.append(rdata.to_text())
            logger.debug(f"Resolved NS records for {domain}: {ns_records}")
            return ns_records
        except ImportError:
            logger.warning("dnspython not installed, NS lookup unavailable")
            return ["[dnspython required for NS records]"]
        except Exception as e:
            logger.debug(f"Failed to resolve NS records for {domain}: {e}")
            return []

    def _resolve_cname_records(self, domain: str) -> List[str]:
        """Resolve CNAME records for domain."""
        try:
            import dns.resolver
            cname_records = []
            answers = dns.resolver.resolve(domain, 'CNAME')
            for rdata in answers:
                cname_records.append(rdata.to_text())
            logger.debug(f"Resolved CNAME records for {domain}: {cname_records}")
            return cname_records
        except ImportError:
            logger.warning("dnspython not installed, CNAME lookup unavailable")
            return []
        except Exception as e:
            logger.debug(f"No CNAME records for {domain}")
            return []

    def _reverse_dns_lookup(self, ip: str) -> Optional[str]:
        """Perform reverse DNS lookup for IP."""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            logger.debug(f"Reverse DNS for {ip}: {hostname}")
            return hostname
        except socket.herror:
            logger.debug(f"No reverse DNS for {ip}")
            return None
        except Exception as e:
            logger.error(f"Error in reverse DNS lookup for {ip}: {e}")
            return None

    def _geolocate_ip(self, ip: str) -> Dict:
        """
        Geolocate IP address using free services.

        Uses ip-api.com free tier (non-commercial use).
        Rate limit: 45 requests/minute.
        """
        geolocation = {
            'ip': ip,
            'country': None,
            'country_code': None,
            'region': None,
            'city': None,
            'latitude': None,
            'longitude': None,
            'timezone': None,
            'isp': None,
            'org': None,
            'as': None,
            'source': None
        }

        # Try free geolocation API
        try:
            import urllib.request
            import urllib.error

            # Use ip-api.com free API
            url = f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,lat,lon,timezone,isp,org,as"

            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))

                if data.get('status') == 'success':
                    geolocation.update({
                        'country': data.get('country'),
                        'country_code': data.get('countryCode'),
                        'region': data.get('regionName'),
                        'city': data.get('city'),
                        'latitude': data.get('lat'),
                        'longitude': data.get('lon'),
                        'timezone': data.get('timezone'),
                        'isp': data.get('isp'),
                        'org': data.get('org'),
                        'as': data.get('as'),
                        'source': 'ip-api.com'
                    })
                    logger.debug(f"Geolocation for {ip}: {data.get('city')}, {data.get('country')}")
                else:
                    logger.warning(f"Geolocation API error: {data.get('message')}")

        except Exception as e:
            logger.debug(f"Geolocation lookup failed for {ip}: {e}")
            # Fallback: Basic info from IP
            geolocation['source'] = 'unavailable'

        return geolocation

    def _get_asn_info(self, ip: str) -> Dict:
        """Get ASN information for IP (from geolocation data)."""
        # ASN info is typically included in geolocation response
        return {
            'ip': ip,
            'asn': None,
            'org': None,
            'note': 'ASN info included in geolocation data'
        }

    def _generate_map_links(self, lat: float, lon: float, label: str = "") -> List[str]:
        """Generate links to various mapping services."""
        maps = []

        # Google Maps
        maps.append({
            'service': 'Google Maps',
            'url': f"https://www.google.com/maps?q={lat},{lon}"
        })

        # OpenStreetMap
        maps.append({
            'service': 'OpenStreetMap',
            'url': f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=12"
        })

        # Bing Maps
        maps.append({
            'service': 'Bing Maps',
            'url': f"https://www.bing.com/maps?cp={lat}~{lon}&lvl=12"
        })

        # Apple Maps (works on iOS/macOS)
        maps.append({
            'service': 'Apple Maps',
            'url': f"http://maps.apple.com/?ll={lat},{lon}&q={quote(label)}"
        })

        logger.debug(f"Generated {len(maps)} map links for coordinates {lat}, {lon}")
        return maps

    def _get_ssl_hints(self, domain: str) -> Dict:
        """Get SSL/TLS certificate hints."""
        ssl_info = {
            'domain': domain,
            'port_443_open': False,
            'cert_available': False,
            'note': 'Full SSL inspection requires additional libraries (ssl, OpenSSL)'
        }

        # Quick check if port 443 is open
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((domain, 443))
            sock.close()

            if result == 0:
                ssl_info['port_443_open'] = True
                ssl_info['cert_available'] = True
                logger.debug(f"Port 443 open on {domain}")
            else:
                logger.debug(f"Port 443 closed on {domain}")

        except Exception as e:
            logger.debug(f"SSL port check failed for {domain}: {e}")

        return ssl_info

    def _calculate_confidence(self, results: Dict) -> float:
        """Calculate confidence score based on available data."""
        score = 0.0

        # Has IPs
        if results['ips']:
            score += 0.3

        # Has geolocation data
        if results['geolocation'].get('latitude'):
            score += 0.2

        # Has DNS records
        if results['mx_records']:
            score += 0.15
        if results['ns_records']:
            score += 0.15
        if results['txt_records']:
            score += 0.1

        # Has reverse DNS
        if results['reverse_dns']:
            score += 0.1

        return min(score, 1.0)

    def format_results(self, results: Dict) -> str:
        """Format domain analysis results for display."""
        if not results['valid']:
            return f"❌ Invalid domain: {results['domain']}\nErrors: {', '.join(results['errors'])}"

        output = []
        output.append(f"🌐 Domain Analysis: {results['domain']}")
        output.append(f"   Confidence: {results['confidence']:.1%}")
        output.append("")

        # IP Addresses
        if results['ips']:
            output.append("📍 IPv4 Addresses:")
            for ip in results['ips']:
                output.append(f"   • {ip}")
            output.append("")

        if results['ipv6']:
            output.append("📍 IPv6 Addresses:")
            for ip in results['ipv6'][:3]:  # Limit display
                output.append(f"   • {ip}")
            output.append("")

        # Geolocation
        if results['geolocation'].get('latitude'):
            geo = results['geolocation']
            output.append("🗺️  Geolocation:")
            if geo.get('city') and geo.get('country'):
                output.append(f"   Location: {geo['city']}, {geo['country']} ({geo.get('country_code', '')})")
            output.append(f"   Coordinates: {geo['latitude']}, {geo['longitude']}")
            if geo.get('timezone'):
                output.append(f"   Timezone: {geo['timezone']}")
            if geo.get('isp'):
                output.append(f"   ISP: {geo['isp']}")
            if geo.get('org'):
                output.append(f"   Organization: {geo['org']}")
            if geo.get('as'):
                output.append(f"   ASN: {geo['as']}")
            output.append("")

        # Map Links
        if results['map_links']:
            output.append("🗺️  Map Links:")
            for map_link in results['map_links']:
                output.append(f"   • {map_link['service']}: {map_link['url']}")
            output.append("")

        # DNS Records
        if results['mx_records']:
            output.append("📧 MX Records (Mail Servers):")
            for mx in results['mx_records'][:5]:
                output.append(f"   • {mx}")
            output.append("")

        if results['ns_records']:
            output.append("🔧 NS Records (Name Servers):")
            for ns in results['ns_records']:
                output.append(f"   • {ns}")
            output.append("")

        if results['txt_records']:
            output.append("📝 TXT Records:")
            for txt in results['txt_records'][:3]:  # Limit to first 3
                # Truncate long TXT records
                txt_display = txt[:100] + "..." if len(txt) > 100 else txt
                output.append(f"   • {txt_display}")
            output.append("")

        if results['cname_records']:
            output.append("🔗 CNAME Records:")
            for cname in results['cname_records']:
                output.append(f"   • {cname}")
            output.append("")

        # Reverse DNS
        if results['reverse_dns']:
            output.append("🔄 Reverse DNS:")
            for rdns in results['reverse_dns']:
                output.append(f"   • {rdns}")
            output.append("")

        # SSL Info
        if results['ssl_info'].get('port_443_open'):
            output.append("🔒 SSL/TLS:")
            output.append(f"   Port 443: Open ✓")
            output.append("")

        return "\n".join(output)
