"""Domain Intelligence Module for OSINT (v1.4.1).

Provides:
- WHOIS-Daten (Registrar, Dates, Registrant Details)
- DNS Intelligence (A, MX, TXT Records, Subdomain Enumeration)
- SSL/TLS Analysis (Certificate Details, Validity, Issuer)
- Web Technology Detection (CMS, Server, Frameworks, Analytics)

APIs: WHOIS API, SecurityTrails, VirusTotal
Docs: https://www.whoisxmlapi.com/, https://securitytrails.com/corp/api
"""

import re
import logging
from typing import Dict, List, Optional, Any
import asyncio
import aiohttp
import socket
import ssl
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger("crawllama")


class DomainIntelligence:
    """Domain OSINT capabilities."""

    def __init__(self, whois_api_key: Optional[str] = None, securitytrails_key: Optional[str] = None, virustotal_key: Optional[str] = None):
        """
        Initialize domain intelligence.
        
        Args:
            whois_api_key: WHOIS API key (optional)
            securitytrails_key: SecurityTrails API key (optional)
            virustotal_key: VirusTotal API key (optional)
        """
        self.whois_api_key = whois_api_key
        self.securitytrails_key = securitytrails_key
        self.virustotal_key = virustotal_key
        self.has_whois_api = whois_api_key is not None
        self.has_securitytrails = securitytrails_key is not None
        self.has_virustotal = virustotal_key is not None
        
        logger.info(f"Domain Intelligence initialized (WHOIS: {self.has_whois_api}, SecurityTrails: {self.has_securitytrails}, VirusTotal: {self.has_virustotal})")

    async def analyze_domain(self, domain: str) -> Dict:
        """
        Comprehensive domain analysis.
        
        Args:
            domain: Domain name to analyze
            
        Returns:
            Dictionary with domain analysis:
            {
                'domain': str,
                'whois': Dict,
                'dns_records': Dict,
                'ssl_certificate': Dict,
                'technologies': List[Dict],
                'subdomains': List[str],
                'ip_addresses': List[str],
                'reputation': Dict,
                'security_score': float,
                'confidence': float
            }
        """
        logger.info(f"Analyzing domain: {domain}")
        
        # Clean domain
        domain = self._clean_domain(domain)
        
        results = {
            'domain': domain,
            'whois': {},
            'dns_records': {},
            'ssl_certificate': {},
            'technologies': [],
            'subdomains': [],
            'ip_addresses': [],
            'reputation': {},
            'security_score': 0.0,
            'confidence': 0.0,
            'error': None
        }

        # Validate domain
        if not self._validate_domain(domain):
            results['error'] = 'Invalid domain format'
            return results

        # Get WHOIS data
        if self.has_whois_api:
            whois_data = await self._get_whois_api_data(domain)
            results['whois'] = whois_data
        else:
            whois_data = await self._get_whois_basic(domain)
            results['whois'] = whois_data

        # Get DNS records
        dns_records = await self._get_dns_records(domain)
        results['dns_records'] = dns_records
        
        # Extract IP addresses from A records
        if dns_records.get('A'):
            results['ip_addresses'] = dns_records['A']

        # Get SSL certificate info
        ssl_info = await self._get_ssl_info(domain)
        results['ssl_certificate'] = ssl_info

        # Get subdomains (if SecurityTrails available)
        if self.has_securitytrails:
            subdomains = await self._enumerate_subdomains(domain)
            results['subdomains'] = subdomains

        # Get reputation (if VirusTotal available)
        if self.has_virustotal:
            reputation = await self._get_virustotal_reputation(domain)
            results['reputation'] = reputation

        # Detect web technologies
        technologies = await self._detect_technologies(domain)
        results['technologies'] = technologies

        # Calculate security score
        results['security_score'] = self._calculate_security_score(results)
        
        # Calculate confidence
        results['confidence'] = self._calculate_confidence(results)
        
        logger.info(f"Domain analysis complete: {domain} (confidence: {results['confidence']:.2f})")
        return results

    async def _get_whois_api_data(self, domain: str) -> Dict:
        """Get WHOIS data using API."""
        try:
            url = f"https://www.whoisxmlapi.com/whoisserver/WhoisService"
            params = {
                'apiKey': self.whois_api_key,
                'domainName': domain,
                'outputFormat': 'JSON'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        whois_record = data.get('WhoisRecord', {})
                        registrar_data = whois_record.get('registrarName', {})
                        registrant = whois_record.get('registrant', {})
                        
                        return {
                            'registrar': registrar_data,
                            'creation_date': whois_record.get('createdDate'),
                            'expiration_date': whois_record.get('expiresDate'),
                            'updated_date': whois_record.get('updatedDate'),
                            'registrant_name': registrant.get('name'),
                            'registrant_organization': registrant.get('organization'),
                            'registrant_country': registrant.get('country'),
                            'registrant_email': registrant.get('email'),
                            'name_servers': whois_record.get('nameServers', {}).get('hostNames', []),
                            'status': whois_record.get('status'),
                            'dnssec': whois_record.get('dnssec')
                        }
                    else:
                        logger.error(f"WHOIS API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"WHOIS API error: {e}")
        
        return {}

    async def _get_whois_basic(self, domain: str) -> Dict:
        """Get basic WHOIS data (fallback)."""
        logger.warning("Using basic WHOIS lookup - limited data")
        
        try:
            import whois as python_whois
            
            w = python_whois.whois(domain)
            
            return {
                'registrar': w.registrar,
                'creation_date': str(w.creation_date) if w.creation_date else None,
                'expiration_date': str(w.expiration_date) if w.expiration_date else None,
                'updated_date': str(w.updated_date) if w.updated_date else None,
                'name_servers': w.name_servers if w.name_servers else [],
                'status': w.status,
                'registrant_name': w.get('registrant_name'),
                'registrant_organization': w.get('org'),
                'registrant_country': w.get('country')
            }
        except ImportError:
            logger.warning("python-whois library not installed")
        except Exception as e:
            logger.error(f"WHOIS lookup error: {e}")
        
        return {}

    async def _get_dns_records(self, domain: str) -> Dict:
        """Get DNS records for domain."""
        records = {
            'A': [],
            'AAAA': [],
            'MX': [],
            'TXT': [],
            'NS': [],
            'CNAME': None,
            'SOA': None
        }
        
        try:
            import dns.resolver
            
            # A records
            try:
                answers = dns.resolver.resolve(domain, 'A')
                records['A'] = [str(rdata) for rdata in answers]
            except:
                pass
            
            # AAAA records (IPv6)
            try:
                answers = dns.resolver.resolve(domain, 'AAAA')
                records['AAAA'] = [str(rdata) for rdata in answers]
            except:
                pass
            
            # MX records
            try:
                answers = dns.resolver.resolve(domain, 'MX')
                records['MX'] = [{'priority': rdata.preference, 'server': str(rdata.exchange)} for rdata in answers]
            except:
                pass
            
            # TXT records
            try:
                answers = dns.resolver.resolve(domain, 'TXT')
                records['TXT'] = [str(rdata) for rdata in answers]
            except:
                pass
            
            # NS records
            try:
                answers = dns.resolver.resolve(domain, 'NS')
                records['NS'] = [str(rdata) for rdata in answers]
            except:
                pass
            
            # CNAME
            try:
                answers = dns.resolver.resolve(domain, 'CNAME')
                records['CNAME'] = str(answers[0]) if answers else None
            except:
                pass
                
        except ImportError:
            logger.warning("dnspython library not installed - using basic DNS lookup")
            # Fallback to basic socket lookup
            try:
                records['A'] = [socket.gethostbyname(domain)]
            except:
                pass
        except Exception as e:
            logger.error(f"DNS lookup error: {e}")
        
        return records

    async def _get_ssl_info(self, domain: str) -> Dict:
        """Get SSL/TLS certificate information."""
        ssl_info = {
            'valid': False,
            'issuer': None,
            'subject': None,
            'version': None,
            'serial_number': None,
            'not_before': None,
            'not_after': None,
            'expired': True,
            'days_until_expiry': 0,
            'san': []
        }
        
        try:
            context = ssl.create_default_context()
            
            async def check_ssl():
                reader, writer = await asyncio.open_connection(
                    domain, 443, ssl=context
                )
                
                ssl_object = writer.get_extra_info('ssl_object')
                cert = ssl_object.getpeercert()
                writer.close()
                await writer.wait_closed()
                
                return cert
            
            cert = await asyncio.wait_for(check_ssl(), timeout=10)
            
            if cert:
                ssl_info.update({
                    'valid': True,
                    'issuer': dict(x[0] for x in cert.get('issuer', [])),
                    'subject': dict(x[0] for x in cert.get('subject', [])),
                    'version': cert.get('version'),
                    'serial_number': cert.get('serialNumber'),
                    'not_before': cert.get('notBefore'),
                    'not_after': cert.get('notAfter'),
                    'san': cert.get('subjectAltName', [])
                })
                
                # Calculate expiry
                try:
                    not_after = datetime.strptime(cert.get('notAfter'), '%b %d %H:%M:%S %Y %Z')
                    days_until = (not_after - datetime.now()).days
                    ssl_info['expired'] = days_until <= 0
                    ssl_info['days_until_expiry'] = days_until
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"SSL check error: {e}")
        
        return ssl_info

    async def _enumerate_subdomains(self, domain: str) -> List[str]:
        """Enumerate subdomains using SecurityTrails."""
        if not self.has_securitytrails:
            return []
        
        try:
            url = f"https://api.securitytrails.com/v1/domain/{domain}/subdomains"
            headers = {
                'APIKEY': self.securitytrails_key,
                'Accept': 'application/json'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        subdomains = data.get('subdomains', [])
                        
                        # Prepend domain
                        return [f"{sub}.{domain}" for sub in subdomains]
                    else:
                        logger.error(f"SecurityTrails API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"Subdomain enumeration error: {e}")
        
        return []

    async def _get_virustotal_reputation(self, domain: str) -> Dict:
        """Get domain reputation from VirusTotal."""
        if not self.has_virustotal:
            return {}
        
        try:
            url = f"https://www.virustotal.com/api/v3/domains/{domain}"
            headers = {
                'x-apikey': self.virustotal_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        attributes = data.get('data', {}).get('attributes', {})
                        stats = attributes.get('last_analysis_stats', {})
                        
                        return {
                            'malicious': stats.get('malicious', 0),
                            'suspicious': stats.get('suspicious', 0),
                            'harmless': stats.get('harmless', 0),
                            'undetected': stats.get('undetected', 0),
                            'reputation': attributes.get('reputation', 0),
                            'categories': attributes.get('categories', {}),
                            'popularity_rank': attributes.get('popularity_ranks', {})
                        }
                    else:
                        logger.error(f"VirusTotal API error: {response.status}")
                        
        except Exception as e:
            logger.error(f"VirusTotal error: {e}")
        
        return {}

    async def _detect_technologies(self, domain: str) -> List[Dict]:
        """Detect web technologies used on domain."""
        technologies = []
        
        try:
            url = f"https://{domain}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10, allow_redirects=True) as response:
                    html = await response.text()
                    response_headers = response.headers
                    
                    # Detect from headers
                    if 'Server' in response_headers:
                        technologies.append({
                            'name': 'Server',
                            'value': response_headers['Server'],
                            'confidence': 1.0
                        })
                    
                    if 'X-Powered-By' in response_headers:
                        technologies.append({
                            'name': 'Framework',
                            'value': response_headers['X-Powered-By'],
                            'confidence': 1.0
                        })
                    
                    # Detect from HTML
                    # WordPress
                    if 'wp-content' in html or 'wordpress' in html.lower():
                        technologies.append({
                            'name': 'CMS',
                            'value': 'WordPress',
                            'confidence': 0.9
                        })
                    
                    # Joomla
                    if 'joomla' in html.lower() or '/components/com_' in html:
                        technologies.append({
                            'name': 'CMS',
                            'value': 'Joomla',
                            'confidence': 0.9
                        })
                    
                    # Drupal
                    if 'drupal' in html.lower() or '/sites/default/' in html:
                        technologies.append({
                            'name': 'CMS',
                            'value': 'Drupal',
                            'confidence': 0.9
                        })
                    
                    # Google Analytics
                    if 'google-analytics.com' in html or 'gtag(' in html:
                        technologies.append({
                            'name': 'Analytics',
                            'value': 'Google Analytics',
                            'confidence': 1.0
                        })
                    
                    # jQuery
                    if 'jquery' in html.lower():
                        technologies.append({
                            'name': 'JavaScript Library',
                            'value': 'jQuery',
                            'confidence': 0.9
                        })
                    
                    # React
                    if 'react' in html.lower() or '_react' in html:
                        technologies.append({
                            'name': 'JavaScript Framework',
                            'value': 'React',
                            'confidence': 0.8
                        })
                    
                    # Vue.js
                    if 'vue' in html.lower() or 'v-if' in html:
                        technologies.append({
                            'name': 'JavaScript Framework',
                            'value': 'Vue.js',
                            'confidence': 0.8
                        })
                        
        except Exception as e:
            logger.error(f"Technology detection error: {e}")
        
        return technologies

    def _clean_domain(self, domain: str) -> str:
        """Clean and normalize domain name."""
        # Lowercase first
        domain = domain.lower().strip()
        # Remove protocol
        domain = re.sub(r'^https?://', '', domain)
        # Remove www
        domain = re.sub(r'^www\.', '', domain)
        # Remove path
        domain = domain.split('/')[0]
        # Remove port
        domain = domain.split(':')[0]
        
        return domain

    def _validate_domain(self, domain: str) -> bool:
        """Validate domain format."""
        pattern = r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        return bool(re.match(pattern, domain))

    def _calculate_security_score(self, results: Dict) -> float:
        """Calculate domain security score."""
        score = 0.0
        
        # SSL certificate
        if results.get('ssl_certificate', {}).get('valid'):
            score += 0.3
            if not results['ssl_certificate'].get('expired'):
                score += 0.2
        
        # DNSSEC
        if results.get('whois', {}).get('dnssec'):
            score += 0.2
        
        # Reputation
        reputation = results.get('reputation', {})
        if reputation:
            malicious = reputation.get('malicious', 0)
            if malicious == 0:
                score += 0.3
        
        return min(score, 1.0)

    def _calculate_confidence(self, results: Dict) -> float:
        """Calculate confidence score."""
        if results.get('error'):
            return 0.0
        
        confidence = 0.0
        
        if results.get('whois'):
            confidence += 0.25
        if results.get('dns_records', {}).get('A'):
            confidence += 0.25
        if results.get('ssl_certificate', {}).get('valid'):
            confidence += 0.25
        if results.get('technologies'):
            confidence += 0.25
            
        return min(confidence, 1.0)
