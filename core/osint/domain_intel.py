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
import requests
from contextlib import contextmanager
from typing import Callable, Dict, List, Optional
from urllib.parse import quote
from utils.validators import sanitize_for_logging
from utils.privacy import redact_coordinates

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
        logger.info(f"Analyzing domain: {sanitize_for_logging(domain, 'domain')}")

        # Clean and validate domain
        clean_domain = self._clean_domain(domain)
        results = self._empty_analysis_results(clean_domain)

        # Validate domain syntax
        if not self._validate_domain_syntax(clean_domain):
            results['errors'].append("Invalid domain syntax")
            logger.warning(f"Invalid domain syntax: {sanitize_for_logging(clean_domain, 'domain')}")
            return results

        results['valid'] = True

        self._collect_dns_records(results, clean_domain)
        self._collect_reverse_dns(results)
        self._collect_geolocation(results, clean_domain)

        # SSL/TLS info hints
        results['ssl_info'] = self._get_ssl_hints(clean_domain)

        # Calculate confidence score
        results['confidence'] = self._calculate_confidence(results)

        logger.info(f"Domain analysis complete for {sanitize_for_logging(clean_domain, 'domain')}: {len(results['ips'])} IPs found")
        return results

    @staticmethod
    def _empty_analysis_results(domain: str) -> Dict:
        """Build the initial (empty) analysis results dictionary."""
        return {
            'domain': domain,
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

    def _collect_dns_records(self, results: Dict, domain: str) -> None:
        """Resolve A, AAAA, MX, TXT, NS and CNAME records into the results dict."""
        results['ips'] = self._resolve_a_records(domain)
        results['ipv6'] = self._resolve_aaaa_records(domain)
        results['mx_records'] = self._resolve_mx_records(domain)
        results['txt_records'] = self._resolve_txt_records(domain)
        results['ns_records'] = self._resolve_ns_records(domain)
        results['cname_records'] = self._resolve_cname_records(domain)

    def _collect_reverse_dns(self, results: Dict) -> None:
        """Perform reverse DNS lookups for the first resolved IPs."""
        for ip in results['ips'][:3]:  # Limit to first 3 IPs
            reverse = self._reverse_dns_lookup(ip)
            if reverse:
                results['reverse_dns'].append(reverse)

    def _collect_geolocation(self, results: Dict, domain: str) -> None:
        """Geolocate the primary IP and generate map links if coordinates exist."""
        if not results['ips']:
            return

        primary_ip = results['ips'][0]
        results['geolocation'] = self._geolocate_ip(primary_ip)
        results['asn_info'] = self._get_asn_info(primary_ip)

        # Generate map links
        if results['geolocation'].get('latitude') and results['geolocation'].get('longitude'):
            results['map_links'] = self._generate_map_links(
                results['geolocation']['latitude'],
                results['geolocation']['longitude'],
                domain
            )

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

    @staticmethod
    @contextmanager
    def _socket_timeout(seconds: float = 5.0):
        """Temporarily set the global socket timeout, restoring it afterwards."""
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(seconds)
        try:
            yield
        finally:
            socket.setdefaulttimeout(old_timeout)

    def _resolve_address_records(self, domain: str, family: int, label: str) -> List[str]:
        """Resolve A (IPv4) or AAAA (IPv6) records via getaddrinfo."""
        try:
            with self._socket_timeout(5.0):
                result = socket.getaddrinfo(domain, None, family)
                ips = list({r[4][0] for r in result})
                logger.debug(f"Resolved {label} records for {domain}: {ips}")
                return ips
        except socket.gaierror as e:
            logger.debug(f"Failed to resolve {label} records for {domain}: {e}")
            return []
        except socket.timeout:
            logger.warning(f"Timeout resolving {label} records for {sanitize_for_logging(domain, 'domain')}")
            return []
        except Exception as e:
            logger.error(f"Error resolving {label} records for {domain}: {e}")
            return []

    def _resolve_a_records(self, domain: str) -> List[str]:
        """Resolve A records (IPv4) for domain."""
        return self._resolve_address_records(domain, socket.AF_INET, "A")

    def _resolve_aaaa_records(self, domain: str) -> List[str]:
        """Resolve AAAA records (IPv6) for domain."""
        return self._resolve_address_records(domain, socket.AF_INET6, "AAAA")

    def _resolve_dns_records(
        self,
        domain: str,
        record_type: str,
        formatter: Callable[[object], str],
        unavailable: Optional[List[str]] = None,
    ) -> List[str]:
        """Resolve a DNS record type via dnspython, formatting each answer.

        ``unavailable`` is returned when dnspython is not installed (MX/TXT/NS
        surface a hint string; CNAME passes an empty list).
        """
        try:
            import dns.resolver
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5.0
            resolver.lifetime = 5.0
            answers = resolver.resolve(domain, record_type)
            records = [formatter(rdata) for rdata in answers]
            logger.debug(f"Resolved {record_type} records for {domain}: {len(records)} records")
            return records
        except ImportError:
            logger.warning(f"dnspython not installed, {record_type} lookup unavailable")
            return list(unavailable) if unavailable else []
        except dns.resolver.Timeout:
            logger.warning(f"Timeout resolving {record_type} records for {sanitize_for_logging(domain, 'domain')}")
            return []
        except Exception as e:
            logger.debug(f"Failed to resolve {record_type} records for {domain}: {e}")
            return []

    def _resolve_mx_records(self, domain: str) -> List[str]:
        """Resolve MX records for domain."""
        return self._resolve_dns_records(
            domain, 'MX',
            lambda r: f"{r.preference} {r.exchange.to_text()}",
            unavailable=["[dnspython required for MX records]"],
        )

    def _resolve_txt_records(self, domain: str) -> List[str]:
        """Resolve TXT records for domain."""
        return self._resolve_dns_records(
            domain, 'TXT',
            lambda r: b''.join(r.strings).decode('utf-8', errors='ignore'),
            unavailable=["[dnspython required for TXT records]"],
        )

    def _resolve_ns_records(self, domain: str) -> List[str]:
        """Resolve NS records for domain."""
        return self._resolve_dns_records(
            domain, 'NS', lambda r: r.to_text(),
            unavailable=["[dnspython required for NS records]"],
        )

    def _resolve_cname_records(self, domain: str) -> List[str]:
        """Resolve CNAME records for domain."""
        return self._resolve_dns_records(domain, 'CNAME', lambda r: r.to_text())

    def _reverse_dns_lookup(self, ip: str) -> Optional[str]:
        """Perform reverse DNS lookup for IP."""
        try:
            with self._socket_timeout(5.0):
                hostname = socket.gethostbyaddr(ip)[0]
                logger.debug(f"Reverse DNS for {ip}: {hostname}")
                return hostname
        except socket.timeout:
            logger.debug(f"Timeout during reverse DNS lookup for {ip}")
            return None
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

            from urllib.parse import urlparse

            # Use ip-api.com free API
            url = f"http://ip-api.com/json/{ip}?fields=status,message,country,countryCode,region,regionName,city,lat,lon,timezone,isp,org,as"

            # Validate URL scheme before opening
            parsed_url = urlparse(url)
            if parsed_url.scheme not in ("http", "https"):
                logger.warning(f"Blocked attempt to open URL with unsupported scheme: {parsed_url.scheme}")
                raise ValueError("Unsupported URL scheme for geolocation API.")

            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

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

        except requests.RequestException as e:
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

        # Redact coordinates in logs for privacy
        redacted_lat, redacted_lon = redact_coordinates(lat, lon)
        logger.debug(f"Generated {len(maps)} map links")  # lgtm[py/clear-text-logging-sensitive-data] - Coordinate details are not logged to protect privacy
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

        output = [
            f"🌐 Domain Analysis: {results['domain']}",
            f"   Confidence: {results['confidence']:.1%}",
            "",
        ]
        output.extend(self._format_ip_lines(results))
        output.extend(self._format_geolocation_lines(results['geolocation']))
        output.extend(self._format_map_link_lines(results['map_links']))
        output.extend(self._format_dns_record_lines(results))
        output.extend(self._format_reverse_dns_lines(results['reverse_dns']))
        output.extend(self._format_ssl_lines(results['ssl_info']))

        return "\n".join(output)

    @staticmethod
    def _format_bullet_section(title: str, items: List[str]) -> List[str]:
        """Format a section header plus bulleted items; empty list if no items."""
        if not items:
            return []
        return [title] + [f"   • {item}" for item in items] + [""]

    def _format_ip_lines(self, results: Dict) -> List[str]:
        """Format IPv4 and IPv6 address sections."""
        lines = self._format_bullet_section("📍 IPv4 Addresses:", results['ips'])
        lines += self._format_bullet_section(
            "📍 IPv6 Addresses:", results['ipv6'][:3]  # Limit display
        )
        return lines

    @staticmethod
    def _format_geolocation_lines(geo: Dict) -> List[str]:
        """Format the geolocation section."""
        if not geo.get('latitude'):
            return []

        lines = ["🗺️  Geolocation:"]
        if geo.get('city') and geo.get('country'):
            lines.append(f"   Location: {geo['city']}, {geo['country']} ({geo.get('country_code', '')})")
        lines.append(f"   Coordinates: {geo['latitude']}, {geo['longitude']}")
        if geo.get('timezone'):
            lines.append(f"   Timezone: {geo['timezone']}")
        if geo.get('isp'):
            lines.append(f"   ISP: {geo['isp']}")
        if geo.get('org'):
            lines.append(f"   Organization: {geo['org']}")
        if geo.get('as'):
            lines.append(f"   ASN: {geo['as']}")
        lines.append("")
        return lines

    def _format_map_link_lines(self, map_links: List[Dict]) -> List[str]:
        """Format the map links section."""
        items = [f"{map_link['service']}: {map_link['url']}" for map_link in map_links]
        return self._format_bullet_section("🗺️  Map Links:", items)

    def _format_dns_record_lines(self, results: Dict) -> List[str]:
        """Format MX, NS, TXT and CNAME record sections."""
        lines = self._format_bullet_section(
            "📧 MX Records (Mail Servers):", results['mx_records'][:5]
        )
        lines += self._format_bullet_section(
            "🔧 NS Records (Name Servers):", results['ns_records']
        )

        # Truncate long TXT records, limit to first 3
        txt_items = [
            txt[:100] + "..." if len(txt) > 100 else txt
            for txt in results['txt_records'][:3]
        ]
        lines += self._format_bullet_section("📝 TXT Records:", txt_items)
        lines += self._format_bullet_section("🔗 CNAME Records:", results['cname_records'])
        return lines

    def _format_reverse_dns_lines(self, reverse_dns: List[str]) -> List[str]:
        """Format the reverse DNS section."""
        return self._format_bullet_section("🔄 Reverse DNS:", reverse_dns)

    @staticmethod
    def _format_ssl_lines(ssl_info: Dict) -> List[str]:
        """Format the SSL/TLS section."""
        if not ssl_info.get('port_443_open'):
            return []
        return ["🔒 SSL/TLS:", "   Port 443: Open ✓", ""]
