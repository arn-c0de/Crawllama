"""IP Intelligence Module for OSINT (v1.4.1).

Provides:
- Geo-Location (Country, Region, City, ISP, ASN)
- Reputation Checking (Malicious Activity, Spam-Blacklists, Threats)
- Port Scanning & Services (ethical, rate-limited)
- Historical Data (DNS-History, WHOIS-History)

APIs: IPinfo.io, AbuseIPDB, Shodan (optional)
Docs: https://ipinfo.io/developers, https://docs.abuseipdb.com/
"""

import re
import logging
from typing import Dict, List, Optional, Any
import asyncio
import aiohttp
import socket
from datetime import datetime

logger = logging.getLogger("crawllama")


class IPIntelligence:
    """IP Address OSINT capabilities."""

    def __init__(self, ipinfo_token: Optional[str] = None, abuseipdb_key: Optional[str] = None, shodan_key: Optional[str] = None):
        """
        Initialize IP intelligence.
        
        Args:
            ipinfo_token: IPinfo.io access token (optional)
            abuseipdb_key: AbuseIPDB API key (optional)
            shodan_key: Shodan API key (optional)
        """
        self.ipinfo_token = ipinfo_token
        self.abuseipdb_key = abuseipdb_key
        self.shodan_key = shodan_key
        self.has_ipinfo = ipinfo_token is not None
        self.has_abuseipdb = abuseipdb_key is not None
        self.has_shodan = shodan_key is not None
        
        logger.info(f"IP Intelligence initialized (IPinfo: {self.has_ipinfo}, AbuseIPDB: {self.has_abuseipdb}, Shodan: {self.has_shodan})")

    async def analyze_ip(self, ip_address: str) -> Dict:
        """
        Comprehensive IP address analysis.
        
        Args:
            ip_address: IP address to analyze
            
        Returns:
            Dictionary with IP analysis:
            {
                'ip': str,
                'hostname': str,
                'geolocation': Dict,
                'isp': str,
                'asn': str,
                'organization': str,
                'country': str,
                'region': str,
                'city': str,
                'postal': str,
                'timezone': str,
                'reputation': Dict,
                'threats': List[Dict],
                'open_ports': List[int],
                'services': List[Dict],
                'dns_history': List[Dict],
                'confidence': float
            }
        """
        logger.info(f"Analyzing IP address: {ip_address}")
        
        results = {
            'ip': ip_address,
            'hostname': None,
            'geolocation': {},
            'isp': None,
            'asn': None,
            'organization': None,
            'country': None,
            'region': None,
            'city': None,
            'postal': None,
            'timezone': None,
            'reputation': {},
            'threats': [],
            'open_ports': [],
            'services': [],
            'dns_history': [],
            'confidence': 0.0,
            'error': None
        }

        # Validate IP format
        if not self._validate_ip(ip_address):
            results['error'] = 'Invalid IP address format'
            return results

        # Get hostname
        results['hostname'] = await self._get_hostname(ip_address)

        # Get geolocation data
        if self.has_ipinfo:
            geo_data = await self._get_ipinfo_data(ip_address)
            if geo_data and not geo_data.get('error'):
                results.update(geo_data)
        else:
            # Fallback to free geolocation
            geo_data = await self._get_free_geolocation(ip_address)
            results.update(geo_data)

        # Get reputation data
        if self.has_abuseipdb:
            reputation = await self._get_abuseipdb_data(ip_address)
            results['reputation'] = reputation

        # Get Shodan data (if available)
        if self.has_shodan:
            shodan_data = await self._get_shodan_data(ip_address)
            if shodan_data:
                results['open_ports'] = shodan_data.get('ports', [])
                results['services'] = shodan_data.get('services', [])

        # Calculate confidence
        results['confidence'] = self._calculate_confidence(results)
        
        logger.info(f"IP analysis complete: {ip_address} (confidence: {results['confidence']:.2f})")
        return results

    async def _get_ipinfo_data(self, ip_address: str) -> Dict:
        """Get IP data from IPinfo.io."""
        try:
            url = f"https://ipinfo.io/{ip_address}/json"
            params = {'token': self.ipinfo_token}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        return {
                            'hostname': data.get('hostname'),
                            'isp': data.get('org'),
                            'asn': data.get('org', '').split()[0] if data.get('org') else None,
                            'organization': data.get('org'),
                            'country': data.get('country'),
                            'region': data.get('region'),
                            'city': data.get('city'),
                            'postal': data.get('postal'),
                            'timezone': data.get('timezone'),
                            'geolocation': {
                                'latitude': data.get('loc', ',').split(',')[0] if data.get('loc') else None,
                                'longitude': data.get('loc', ',').split(',')[1] if data.get('loc') else None
                            }
                        }
                    else:
                        logger.error(f"IPinfo API error: {response.status}")
                        return {'error': f"API error: {response.status}"}
                        
        except Exception as e:
            logger.error(f"IPinfo error: {e}")
            return {'error': str(e)}

    async def _get_free_geolocation(self, ip_address: str) -> Dict:
        """Get IP geolocation from free API (fallback)."""
        try:
            url = f"http://ip-api.com/json/{ip_address}"
            params = {
                'fields': 'status,country,regionName,city,zip,isp,org,as,query,lat,lon,timezone'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('status') == 'success':
                            return {
                                'isp': data.get('isp'),
                                'asn': data.get('as'),
                                'organization': data.get('org'),
                                'country': data.get('country'),
                                'region': data.get('regionName'),
                                'city': data.get('city'),
                                'postal': data.get('zip'),
                                'timezone': data.get('timezone'),
                                'geolocation': {
                                    'latitude': data.get('lat'),
                                    'longitude': data.get('lon')
                                }
                            }
                        
        except Exception as e:
            logger.error(f"Free geolocation error: {e}")
        
        return {}

    async def _get_abuseipdb_data(self, ip_address: str) -> Dict:
        """Get IP reputation from AbuseIPDB."""
        try:
            url = "https://api.abuseipdb.com/api/v2/check"
            headers = {
                'Key': self.abuseipdb_key,
                'Accept': 'application/json'
            }
            params = {
                'ipAddress': ip_address,
                'maxAgeInDays': 90,
                'verbose': ''
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        ip_data = data.get('data', {})
                        
                        return {
                            'abuse_confidence_score': ip_data.get('abuseConfidenceScore', 0),
                            'total_reports': ip_data.get('totalReports', 0),
                            'num_distinct_users': ip_data.get('numDistinctUsers', 0),
                            'is_whitelisted': ip_data.get('isWhitelisted', False),
                            'is_tor': ip_data.get('isTor', False),
                            'last_reported_at': ip_data.get('lastReportedAt'),
                            'usage_type': ip_data.get('usageType'),
                            'domain': ip_data.get('domain')
                        }
                    else:
                        logger.error(f"AbuseIPDB API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"AbuseIPDB error: {e}")
        
        return {}

    async def _get_shodan_data(self, ip_address: str) -> Optional[Dict]:
        """Get IP data from Shodan."""
        try:
            url = f"https://api.shodan.io/shodan/host/{ip_address}"
            params = {'key': self.shodan_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        services = []
                        for item in data.get('data', []):
                            services.append({
                                'port': item.get('port'),
                                'protocol': item.get('transport'),
                                'service': item.get('product'),
                                'version': item.get('version'),
                                'banner': item.get('data', '')[:200]  # Truncate
                            })
                        
                        return {
                            'ports': data.get('ports', []),
                            'services': services,
                            'hostnames': data.get('hostnames', []),
                            'organization': data.get('org'),
                            'os': data.get('os')
                        }
                    else:
                        logger.error(f"Shodan API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Shodan error: {e}")
        
        return None

    async def _get_hostname(self, ip_address: str) -> Optional[str]:
        """Get hostname from IP address via reverse DNS."""
        try:
            loop = asyncio.get_event_loop()
            hostname = await loop.run_in_executor(None, socket.gethostbyaddr, ip_address)
            return hostname[0] if hostname else None
        except:
            return None

    async def check_reputation(self, ip_address: str) -> Dict:
        """
        Check IP reputation across multiple databases.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            Dictionary with reputation data
        """
        logger.info(f"Checking IP reputation: {ip_address}")
        
        reputation = {
            'ip': ip_address,
            'is_malicious': False,
            'is_tor': False,
            'is_proxy': False,
            'is_vpn': False,
            'threat_score': 0.0,
            'reports': [],
            'blacklists': []
        }

        if self.has_abuseipdb:
            abuse_data = await self._get_abuseipdb_data(ip_address)
            if abuse_data:
                score = abuse_data.get('abuse_confidence_score', 0)
                reputation['threat_score'] = score / 100.0
                reputation['is_malicious'] = score > 50
                reputation['is_tor'] = abuse_data.get('is_tor', False)
                reputation['reports'].append({
                    'source': 'AbuseIPDB',
                    'score': score,
                    'reports': abuse_data.get('total_reports', 0)
                })

        return reputation

    async def scan_ports(self, ip_address: str, ports: Optional[List[int]] = None) -> List[int]:
        """
        Scan for open ports (ethical, rate-limited).
        
        Args:
            ip_address: IP address to scan
            ports: List of ports to scan (default: common ports)
            
        Returns:
            List of open ports
        """
        logger.info(f"Scanning ports: {ip_address}")
        
        if ports is None:
            # Common ports
            ports = [21, 22, 23, 25, 53, 80, 110, 143, 443, 3306, 3389, 5432, 8080, 8443]
        
        open_ports = []
        
        for port in ports:
            if await self._check_port(ip_address, port):
                open_ports.append(port)
                logger.info(f"Port {port} is open")
            
            # Rate limiting - wait between checks
            await asyncio.sleep(0.5)
        
        return open_ports

    async def _check_port(self, ip_address: str, port: int) -> bool:
        """Check if a port is open."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip_address, port),
                timeout=2
            )
            writer.close()
            await writer.wait_closed()
            return True
        except:
            return False

    def _validate_ip(self, ip_address: str) -> bool:
        """Validate IP address format."""
        # IPv4
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if re.match(ipv4_pattern, ip_address):
            parts = ip_address.split('.')
            return all(0 <= int(part) <= 255 for part in parts)
        
        # IPv6 (basic check)
        ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){7}[0-9a-fA-F]{0,4}$'
        if re.match(ipv6_pattern, ip_address):
            return True
        
        return False

    def _calculate_confidence(self, results: Dict) -> float:
        """Calculate confidence score."""
        if results.get('error'):
            return 0.0
        
        confidence = 0.0
        
        if results.get('country'):
            confidence += 0.2
        if results.get('city'):
            confidence += 0.15
        if results.get('isp'):
            confidence += 0.15
        if results.get('asn'):
            confidence += 0.15
        if results.get('hostname'):
            confidence += 0.15
        if results.get('reputation'):
            confidence += 0.2
            
        return min(confidence, 1.0)
