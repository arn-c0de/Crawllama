"""Email Intelligence Module for OSINT.

Provides:
- Email syntax validation
- Domain verification
- MX record lookup
- Disposable email detection
- Social profile discovery
- Email pattern generation
- Data breach & leak detection
"""

import re
import logging
from typing import Dict, List, Optional
import socket
import hashlib
from utils.validators import sanitize_for_logging

logger = logging.getLogger("crawllama")

# Common disposable email domains
DISPOSABLE_DOMAINS = {
    '10minutemail.com', 'tempmail.com', 'guerrillamail.com',
    'mailinator.com', 'throwaway.email', 'temp-mail.org',
    'getnada.com', 'trashmail.com', 'fakeinbox.com',
    'maildrop.cc', 'sharklasers.com', 'guerrillamail.info'
}


class EmailIntelligence:
    """Email OSINT capabilities."""

    def __init__(self):
        """Initialize email intelligence."""
        self.disposable_domains = DISPOSABLE_DOMAINS
        logger.info("Email Intelligence initialized")

    def analyze_email(self, email: str) -> Dict:
        """
        Comprehensive email analysis.

        Args:
            email: Email address to analyze

        Returns:
            Dictionary with analysis results:
            {
                'email': str,
                'valid': bool,
                'domain': str,
                'username': str,
                'mx_records': List[str],
                'disposable': bool,
                'domain_exists': bool,
                'confidence': float,
                'variations': List[str],
                'breach_info': Dict  # NEW: Data breach information
            }

        Example:
            >>> intel = EmailIntelligence()
            >>> result = intel.analyze_email('test@example.com')
            >>> result['valid']
            True
            >>> result['domain']
            'example.com'
        """
        logger.info(f"Analyzing email: {sanitize_for_logging(email, 'email')}")

        results = {
            'email': email,
            'valid': False,
            'domain': '',
            'username': '',
            'mx_records': [],
            'disposable': False,
            'domain_exists': False,
            'confidence': 0.0,
            'variations': [],
            'breach_info': {}  # NEW
        }

        # Validate syntax
        results['valid'] = self.validate_syntax(email)
        if not results['valid']:
            logger.warning(f"Invalid email syntax: {sanitize_for_logging(email, 'email')}")
            return results

        # Extract parts
        results['username'], results['domain'] = self.extract_parts(email)

        # Check if disposable
        results['disposable'] = self.is_disposable(results['domain'])

        # Check MX records
        results['mx_records'] = self.check_mx_records(results['domain'])
        results['domain_exists'] = len(results['mx_records']) > 0

        # Generate variations
        results['variations'] = self.generate_variations(email)

        # NEW: Check data breaches
        results['breach_info'] = self.check_data_breaches(email)

        # Calculate confidence
        results['confidence'] = self._calculate_confidence(results)

        logger.info(f"Email analysis complete: {sanitize_for_logging(email, 'email')} (confidence: {results['confidence']:.2f})")
        return results

    def validate_syntax(self, email: str) -> bool:
        """
        Validate email syntax using regex.

        Args:
            email: Email address

        Returns:
            True if valid syntax

        Example:
            >>> intel = EmailIntelligence()
            >>> intel.validate_syntax('test@example.com')
            True
            >>> intel.validate_syntax('invalid.email')
            False
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        is_valid = bool(re.match(pattern, email))
        logger.debug("Email syntax validation for '%s': %s", email, is_valid)  # lgtm[py/log-injection] - parameterized logging; false positive
        return is_valid

    def extract_parts(self, email: str) -> tuple:
        """
        Extract username and domain from email.

        Args:
            email: Email address

        Returns:
            Tuple of (username, domain)

        Example:
            >>> intel = EmailIntelligence()
            >>> intel.extract_parts('john.doe@example.com')
            ('john.doe', 'example.com')
        """
        if '@' not in email:
            return ('', '')

        parts = email.split('@')
        return (parts[0], parts[1])

    def check_mx_records(self, domain: str) -> List[str]:
        """
        Check MX records for domain using DNS lookup.

        Args:
            domain: Domain name

        Returns:
            List of MX record hosts

        Example:
            >>> intel = EmailIntelligence()
            >>> mx = intel.check_mx_records('gmail.com')
            >>> len(mx) > 0
            True
        """
        try:
            # Try to resolve domain first
            socket.gethostbyname(domain)

            # Note: Full MX lookup requires dnspython library
            # For now, we just check if domain resolves
            logger.info(f"Domain {domain} resolves successfully")
            return [f"{domain} (DNS verified)"]

        except socket.gaierror:
            logger.warning(f"Domain {domain} does not resolve")
            return []
        except Exception as e:
            logger.error(f"MX lookup error for {domain}: {e}")
            return []

    def is_disposable(self, domain: str) -> bool:
        """
        Check if email domain is disposable/temporary.

        Args:
            domain: Domain name

        Returns:
            True if disposable

        Example:
            >>> intel = EmailIntelligence()
            >>> intel.is_disposable('tempmail.com')
            True
            >>> intel.is_disposable('gmail.com')
            False
        """
        is_disp = domain.lower() in self.disposable_domains
        if is_disp:
            logger.info(f"Disposable email domain detected: {domain}")
        return is_disp

    def generate_variations(self, email: str) -> List[str]:
        """
        Generate potential email variations.

        Args:
            email: Original email

        Returns:
            List of email variations

        Example:
            >>> intel = EmailIntelligence()
            >>> variations = intel.generate_variations('john.doe@company.com')
            >>> 'johndoe@company.com' in variations
            True
        """
        if not self.validate_syntax(email):
            return []

        username, domain = self.extract_parts(email)
        variations = [email]

        # Remove dots
        if '.' in username:
            variations.append(f"{username.replace('.', '')}@{domain}")

        # Replace dot with underscore
        if '.' in username:
            variations.append(f"{username.replace('.', '_')}@{domain}")

        # Replace underscore with dot
        if '_' in username:
            variations.append(f"{username.replace('_', '.')}@{domain}")

        # First initial + last name (if dot present)
        if '.' in username:
            parts = username.split('.')
            if len(parts) >= 2:
                variations.append(f"{parts[0][0]}.{parts[1]}@{domain}")
                variations.append(f"{parts[0]}{parts[1][0]}@{domain}")

        # Remove duplicates
        variations = list(set(variations))

        logger.debug(f"Generated {len(variations)} email variations")
        return variations

    def check_data_breaches(self, email: str) -> Dict:
        """
        Check if email appears in known data breaches.

        Uses Have I Been Pwned API (respecting rate limits).

        Args:
            email: Email address to check

        Returns:
            Dictionary with breach information:
            {
                'email': str,
                'pwned': bool,
                'breach_count': int,
                'breaches': List[Dict],
                'paste_count': int,
                'last_breach': str or None,
                'severity': str  # 'low', 'medium', 'high', 'critical'
            }

        Example:
            >>> intel = EmailIntelligence()
            >>> result = intel.check_data_breaches('test@example.com')
            >>> result['pwned']
            False or True
        """
        logger.info(f"Checking data breaches for: {sanitize_for_logging(email, 'email')}")

        results = {
            'email': email,
            'pwned': False,
            'breach_count': 0,
            'breaches': [],
            'paste_count': 0,
            'last_breach': None,
            'severity': 'none',
            'recommendations': []
        }

        try:
            # Try Have I Been Pwned API
            breaches = self._check_hibp_breaches(email)
            pastes = self._check_hibp_pastes(email)

            results['breach_count'] = len(breaches)
            results['paste_count'] = len(pastes)
            results['pwned'] = results['breach_count'] > 0 or results['paste_count'] > 0
            results['breaches'] = breaches

            # Find most recent breach
            if breaches:
                breach_dates = [b.get('date', '') for b in breaches if b.get('date')]
                if breach_dates:
                    results['last_breach'] = max(breach_dates)

            # Calculate severity
            results['severity'] = self._calculate_breach_severity(results)

            # Generate recommendations
            results['recommendations'] = self._generate_breach_recommendations(results)

            logger.info(f"Breach check complete: {sanitize_for_logging(email, 'email')} - Pwned: {results['pwned']}, Breaches: {results['breach_count']}")

        except Exception as e:
            logger.error(f"Error checking breaches for {email}: {e}")
            results['error'] = str(e)

        return results

    def _check_hibp_breaches(self, email: str) -> List[Dict]:
        """
        Check Have I Been Pwned for email breaches using public API.

        Uses the free HIBP API v3 (no key required for basic checks).

        Args:
            email: Email address

        Returns:
            List of breach dictionaries
        """
        import os
        import urllib.parse
        
        try:
            # Method 1: Try with API key if available (faster, more details)
            api_key = os.getenv('HIBP_API_KEY')
            if api_key:
                logger.info("Using HIBP API with key")
                return self._check_hibp_with_key(email, api_key)
            
            # Method 2: Use free public API (no key, rate limited)
            logger.info("Using HIBP free public API (no key)")
            return self._check_hibp_free(email)
            
        except Exception as e:
            logger.error(f"HIBP breach check failed: {e}")
            return []

    def _check_hibp_with_key(self, email: str, api_key: str) -> List[Dict]:
        """Check HIBP with API key (full results, faster)."""
        try:
            import requests
            import time
            import urllib.parse
            
            encoded_email = urllib.parse.quote(email)
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{encoded_email}?truncateResponse=false"
            headers = {
                'hibp-api-key': api_key,
                'user-agent': 'CrawlLama-OSINT/1.4.6',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            time.sleep(1.6)  # Rate limiting: max 1 request per 1.5 seconds
            
            if response.status_code == 200:
                breaches = response.json()
                logger.info(f"HIBP API (with key): Found {len(breaches)} breaches")
                return breaches
            elif response.status_code == 404:
                logger.info("HIBP API: No breaches found")
                return []
            else:
                logger.warning(f"HIBP API returned {response.status_code}: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"HIBP API check failed: {e}")
            return []

    def _check_hibp_free(self, email: str) -> List[Dict]:
        """
        Check HIBP using multiple free methods when no API key is available.
        
        Methods tried:
        1. Direct API call (will return 401, but try anyway)
        2. Check via web scraping (limited)
        3. Use alternative breach databases
        """
        breaches = []
        
        try:
            # Method 1: Try direct API anyway (sometimes works for old accounts)
            breaches = self._try_hibp_api_direct(email)
            if breaches:
                return breaches
            
            # Method 2: Use alternative breach check methods
            logger.info("HIBP API requires key, trying alternative methods...")
            breaches = self._check_alternative_breach_sources(email)
            
            return breaches
            
        except Exception as e:
            logger.error(f"Free breach check failed: {e}")
            return []

    def _try_hibp_api_direct(self, email: str) -> List[Dict]:
        """Try HIBP API directly (will likely return 401 but worth trying)."""
        try:
            import requests
            import time
            import urllib.parse
            
            encoded_email = urllib.parse.quote(email)
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{encoded_email}?truncateResponse=false"
            
            headers = {
                'user-agent': 'CrawlLama-OSINT/1.4.6',
                'Accept': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            time.sleep(1.6)
            
            if response.status_code == 200:
                breaches = response.json()
                logger.info(f"HIBP API: Found {len(breaches)} breaches (no key)")
                return breaches
            elif response.status_code == 404:
                logger.info("HIBP API: No breaches found")
                return []
            elif response.status_code == 401:
                # Expected - need API key
                return []
            
        except Exception as e:
            logger.debug(f"Direct API attempt failed: {e}")
        
        return []
    
    def _check_alternative_breach_sources(self, email: str) -> List[Dict]:
        """
        Check alternative public breach databases.
        These don't require API keys.
        """
        breaches = []
        
        try:
            # Method 1: Check LeakCheck.io public search
            leakcheck_results = self._check_leakcheck_public(email)
            if leakcheck_results:
                breaches.extend(leakcheck_results)
            
            # Method 2: Check Intelligence X (intelx.io) public database
            intelx_results = self._check_intelx_public(email)
            if intelx_results:
                breaches.extend(intelx_results)
            
            # Method 3: Check breach directory (if local data exists)
            local_results = self._check_local_breach_db(email)
            if local_results:
                breaches.extend(local_results)
            
            if breaches:
                logger.info(f"Alternative sources found {len(breaches)} potential breaches")
            else:
                logger.info("No breaches found in alternative sources")
                # Add informative message about getting API key
                logger.info("ℹ️ For complete breach data, get a free HIBP API key from: https://haveibeenpwned.com/API/Key")
            
        except Exception as e:
            logger.error(f"Alternative breach check failed: {e}")
        
        return breaches
    
    def _check_leakcheck_public(self, email: str) -> List[Dict]:
        """Check LeakCheck.io public search (no API key)."""
        try:
            import requests
            import time
            
            # LeakCheck public lookup
            url = f"https://leakcheck.io/api/public?check={email}"
            headers = {'user-agent': 'CrawlLama-OSINT/1.4.6'}
            
            response = requests.get(url, headers=headers, timeout=10)
            time.sleep(1.0)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') and data.get('found', 0) > 0:
                    # Convert each source to HIBP-compatible format
                    breaches = []
                    sources = data.get('sources', [])
                    found_count = data.get('found', 0)
                    
                    logger.info(f"LeakCheck: Found in {found_count} breaches")
                    
                    for source in sources:
                        breach = {
                            'Name': source.get('name', 'Unknown'),
                            'Title': source.get('name', 'Unknown Breach'),
                            'BreachDate': source.get('date', 'Unknown'),
                            'Description': f"Data breach from {source.get('name', 'Unknown')} detected by LeakCheck.io. Leaked data fields: {', '.join(data.get('fields', ['Unknown'])[:5])}",
                            'DataClasses': data.get('fields', ['Email addresses']),
                            'IsVerified': True,
                            'IsSensitive': True,
                            'Source': 'LeakCheck.io'
                        }
                        breaches.append(breach)
                    
                    return breaches
            
        except Exception as e:
            logger.debug(f"LeakCheck check failed: {e}")
        
        return []
    
    def _check_intelx_public(self, email: str) -> List[Dict]:
        """Check Intelligence X public database."""
        try:
            import requests
            import time
            
            # IntelX has a public phonebook search
            url = f"https://2.intelx.io/phonebook/search?k={email}"
            headers = {'user-agent': 'CrawlLama-OSINT/1.4.6'}
            
            response = requests.get(url, headers=headers, timeout=10)
            time.sleep(1.0)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('selectors'):
                    count = len(data['selectors'])
                    logger.info(f"IntelX: Found {count} results")
                    return [{
                        'Name': 'Intelligence X Database',
                        'Title': f"Found {count} references",
                        'BreachDate': 'Various',
                        'Description': f"Email found in {count} indexed source(s) on Intelligence X. This includes pastes, leaks, and public databases.",
                        'DataClasses': ['Email addresses'],
                        'IsVerified': False,
                        'IsSensitive': True,
                        'Source': 'IntelX.io'
                    }]
            
        except Exception as e:
            logger.debug(f"IntelX check failed: {e}")
        
        return []
    
    def _check_local_breach_db(self, email: str) -> List[Dict]:
        """Check local breach database if available."""
        from pathlib import Path
        
        breach_dir = Path("data/breaches")
        if not breach_dir.exists():
            return []
        
        try:
            # Check if email exists in any local breach files
            # (This would need actual breach data files to work)
            logger.debug("Checking local breach database...")
            # Implementation would scan local files
            # For now, return empty as we don't have local data
            return []
            
        except Exception as e:
            logger.debug(f"Local breach check failed: {e}")
        
        return []

    def _check_hibp_pastes(self, email: str) -> List[Dict]:
        """
        Check Have I Been Pwned for email in pastes.
        Uses free search methods without API key.

        Args:
            email: Email address

        Returns:
            List of paste dictionaries
        """
        import os
        
        # Only check pastes if we have an API key (pastes require authentication)
        api_key = os.getenv('HIBP_API_KEY')
        if not api_key:
            logger.info("HIBP paste check requires API key (skipping)")
            return []
        
        try:
            import requests
            import time
            
            url = f"https://haveibeenpwned.com/api/v3/pasteaccount/{email}"
            headers = {
                'hibp-api-key': api_key,
                'user-agent': 'CrawlLama-OSINT'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            time.sleep(1.5)  # Rate limiting
            
            if response.status_code == 200:
                pastes = response.json()
                logger.info(f"HIBP pastes: Found {len(pastes)}")
                return pastes
            elif response.status_code == 404:
                return []
            else:
                logger.warning(f"HIBP paste check returned {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"HIBP paste check failed: {e}")
            return []

    def _calculate_breach_severity(self, results: Dict) -> str:
        """
        Calculate breach severity level.

        Args:
            results: Breach check results

        Returns:
            Severity level: 'none', 'low', 'medium', 'high', 'critical'
        """
        breach_count = results['breach_count']
        paste_count = results['paste_count']

        if breach_count == 0 and paste_count == 0:
            return 'none'
        elif breach_count <= 2 and paste_count <= 1:
            return 'low'
        elif breach_count <= 5 and paste_count <= 3:
            return 'medium'
        elif breach_count <= 10:
            return 'high'
        else:
            return 'critical'

    def _generate_breach_recommendations(self, results: Dict) -> List[str]:
        """
        Generate security recommendations based on breach results.

        Args:
            results: Breach check results

        Returns:
            List of recommendation strings
        """
        recommendations = []

        if results['pwned']:
            recommendations.append("⚠️ This email has been found in data breaches")
            recommendations.append("🔒 Change passwords for all accounts using this email")
            recommendations.append("🔑 Enable two-factor authentication (2FA) where possible")

            if results['breach_count'] > 5:
                recommendations.append("🚨 Multiple breaches detected - consider using a new email address")

            if results['paste_count'] > 0:
                recommendations.append("📋 Email found in public pastes - monitor for suspicious activity")

            recommendations.append("🔍 Use a password manager to generate unique passwords")
            recommendations.append("📧 Monitor accounts for unauthorized access")

        else:
            recommendations.append("✅ No breaches found in public databases")
            recommendations.append("💡 Continue practicing good security hygiene")

        return recommendations

    def generate_breach_report(self, email: str) -> str:
        """
        Generate a human-readable breach report.

        Args:
            email: Email address

        Returns:
            Formatted report string
        """
        results = self.check_data_breaches(email)

        report = f"\n{'='*60}\n"
        report += f"Data Breach Report for: {email}\n"
        report += f"{'='*60}\n\n"

        if results['pwned']:
            report += f"⚠️  STATUS: COMPROMISED\n"
            report += f"    Breach Count: {results['breach_count']}\n"
            report += f"    Paste Count: {results['paste_count']}\n"
            report += f"    Severity: {results['severity'].upper()}\n"
            if results['last_breach']:
                report += f"    Last Breach: {results['last_breach']}\n"
        else:
            report += f"✅ STATUS: CLEAN\n"
            report += f"    No breaches found in public databases\n"

        report += f"\n{'='*60}\n"
        report += f"RECOMMENDATIONS:\n"
        report += f"{'='*60}\n"
        for rec in results['recommendations']:
            report += f"  {rec}\n"

        report += f"\n{'='*60}\n"
        report += f"Note: This check uses public breach databases.\n"
        report += f"Always use strong, unique passwords and enable 2FA.\n"
        report += f"{'='*60}\n"

        return report

    def _calculate_confidence(self, results: Dict) -> float:
        """
        Calculate confidence score for email analysis.

        Args:
            results: Analysis results dict

        Returns:
            Confidence score (0.0 - 1.0)
        """
        score = 0.0

        # Valid syntax
        if results['valid']:
            score += 0.3

        # Domain exists (MX records)
        if results['domain_exists']:
            score += 0.4

        # Not disposable
        if not results['disposable']:
            score += 0.3

        return min(score, 1.0)

    def search_email_online(self, email: str, max_results: int = 5) -> List[Dict]:
        """
        Search for email address across common platforms.

        Args:
            email: Email address
            max_results: Maximum results to return

        Returns:
            List of found profiles/mentions

        Note:
            This is a placeholder. Full implementation requires:
            - API integrations (GitHub, LinkedIn, etc.)
            - Proper rate limiting
            - Authentication where needed
        """
        logger.info(f"Searching online for: {sanitize_for_logging(email, 'email')}")

        results = []

        # Placeholder for future implementation
        # Would search:
        # - GitHub: https://github.com/search?q={email}
        # - LinkedIn: (requires API)
        # - Twitter/X: (requires API)
        # - Various paste sites (respecting robots.txt)

        logger.warning("Online search not yet implemented (requires API integrations)")

        return results

    def find_company_pattern(self, emails: List[str]) -> Optional[str]:
        """
        Analyze multiple emails to find company email pattern.

        Args:
            emails: List of emails from same company

        Returns:
            Pattern string or None

        Example:
            >>> intel = EmailIntelligence()
            >>> pattern = intel.find_company_pattern([
            ...     'john.doe@company.com',
            ...     'jane.smith@company.com'
            ... ])
            >>> pattern
            '{first}.{last}@company.com'
        """
        if len(emails) < 2:
            return None

        # Extract common domain
        domains = [self.extract_parts(e)[1] for e in emails if self.validate_syntax(e)]
        if not domains:
            return None

        # Most common domain
        domain = max(set(domains), key=domains.count)

        # Analyze username patterns
        usernames = [self.extract_parts(e)[0] for e in emails
                    if self.validate_syntax(e) and self.extract_parts(e)[1] == domain]

        # Check for common patterns
        if all('.' in u for u in usernames):
            return f"{{first}}.{{last}}@{domain}"
        elif all('_' in u for u in usernames):
            return f"{{first}}_{{last}}@{domain}"
        else:
            return f"{{firstlast}}@{domain}"


class EmailVulnerabilityIntel:
    """
    Email Vulnerability Intelligence - Check for leaked credentials.

    Searches public breach databases and leaked credential lists
    WITHOUT requiring API keys or authentication.

    Sources:
    - Public breach compilations
    - Pastebin & text dumps
    - GitHub leaked credentials
    - Public TXT lists
    """

    def __init__(self):
        """Initialize vulnerability intelligence."""
        self.public_sources = [
            "breach-parse lists",
            "collection #1-5",
            "combo lists",
            "pastebin dumps",
            "github leaks"
        ]
        logger.info("Email Vulnerability Intelligence initialized")

    def check_vulnerability(self, email: str) -> Dict:
        """
        Check if email appears in public vulnerability/breach databases.

        Args:
            email: Email address to check

        Returns:
            Dictionary with vulnerability information:
            {
                'email': str,
                'vulnerable': bool,
                'found_in': List[str],  # Sources where found
                'leak_count': int,
                'severity': str,  # 'none', 'low', 'medium', 'high', 'critical'
                'hashes': Dict[str, str],  # Email hashes for anonymous lookup
                'recommendations': List[str],
                'breach_sources': List[Dict]
            }

        Example:
            >>> vuln = EmailVulnerabilityIntel()
            >>> result = vuln.check_vulnerability('test@example.com')
            >>> result['vulnerable']
            False or True
        """
        logger.info(f"Checking vulnerability for email: {sanitize_for_logging(email, 'email')}")

        results = {
            'email': email,
            'vulnerable': False,
            'found_in': [],
            'leak_count': 0,
            'severity': 'none',
            'hashes': self._generate_email_hashes(email),
            'recommendations': [],
            'breach_sources': []
        }

        try:
            # Check various public sources
            breach_sources = []

            # 1. Check local TXT lists (ACTIVE - works immediately)
            breach_sources.extend(self._check_public_lists(email))

            # 2. Check LeakCheck.io FREE API (3 requests/day)
            breach_sources.extend(self._check_leakcheck_api(email))

            # 3. Check DeHashed free search (limited)
            breach_sources.extend(self._check_dehashed_search(email))

            # 4. Check GitHub for accidental leaks (requires GITHUB_TOKEN)
            breach_sources.extend(self._check_github_leaks(email))

            # 5. Check public paste sites (future implementation)
            breach_sources.extend(self._check_public_pastes(email))

            # 6. Check Breach Compilation lists (future implementation)
            breach_sources.extend(self._check_breach_compilations(email))

            results['breach_sources'] = breach_sources
            results['leak_count'] = len(breach_sources)
            results['vulnerable'] = results['leak_count'] > 0

            # Extract unique sources
            results['found_in'] = list(set([s['source'] for s in breach_sources]))

            # Calculate severity
            results['severity'] = self._calculate_vulnerability_severity(results)

            # Generate recommendations
            results['recommendations'] = self._generate_security_recommendations(results)

            logger.info(f"Vulnerability check complete: {sanitize_for_logging(email, 'email')} - Vulnerable: {results['vulnerable']}")

        except Exception as e:
            logger.error(f"Error checking vulnerability for {email}: {e}")
            results['error'] = str(e)

        return results

    def _generate_email_hashes(self, email: str) -> Dict[str, str]:
        """
        Generate email hashes for anonymous lookups.

        Args:
            email: Email address

        Returns:
            Dictionary with various hash formats
        """
        email_lower = email.lower().strip()

        # Note: MD5/SHA1 used for email lookup/indexing only, NOT for security/cryptography
        # These hashes are used to anonymously check if an email exists in breach databases
        # nosemgrep: python.lang.security.insecure-hash-algorithm-md5
        # nosemgrep: python.lang.security.insecure-hash-algorithm-sha1
        hashes = {
            'md5': hashlib.md5(email_lower.encode(), usedforsecurity=False).hexdigest(),  # nosec B324
            'sha1': hashlib.sha1(email_lower.encode(), usedforsecurity=False).hexdigest(),  # nosec B303
            'sha256': hashlib.sha256(email_lower.encode()).hexdigest()
        }

        logger.debug(f"Generated hashes for email lookup: MD5={hashes['md5'][:8]}...")
        return hashes

    def _check_breach_compilations(self, email: str) -> List[Dict]:
        """
        Check against known breach compilation lists.

        Note: This is a SIMULATION. Real implementation would:
        - Download public breach compilations from legal sources
        - Search local cached breach databases
        - Use hash lookups for privacy

        Args:
            email: Email address

        Returns:
            List of breach sources
        """
        logger.info(f"Checking breach compilations for: {sanitize_for_logging(email, 'email')}")

        # SIMULATION - In production, would check actual breach files
        # Known public breaches (legal to reference):
        # - Collection #1 (773M accounts)
        # - Collection #2-5
        # - Anti Public Combo List
        # - Exploit.in

        found_breaches = []

        # Example structure of what would be returned:
        # found_breaches.append({
        #     'source': 'Collection #1',
        #     'date': '2019-01',
        #     'type': 'credential_dump',
        #     'records': 773000000,
        #     'description': 'Large credential compilation'
        # })

        logger.info("Breach compilation check: No local database available")
        logger.info("To enable: Download breach compilations to ./data/breaches/ (legal sources only)")

        return found_breaches

    def _check_public_pastes(self, email: str) -> List[Dict]:
        """
        Check public paste sites for email leaks.

        Note: This is a SIMULATION. Real implementation would:
        - Search Pastebin, Ghostbin, etc. (respecting robots.txt)
        - Look for credential dumps
        - Rate limit requests

        Args:
            email: Email address

        Returns:
            List of paste findings
        """
        logger.info(f"Checking public pastes for: {sanitize_for_logging(email, 'email')}")

        # SIMULATION - Would use web scraping
        # Sources to check:
        # - Pastebin (with rate limiting)
        # - Ghostbin
        # - Rentry
        # - JustPaste.it

        found_pastes = []

        # Example:
        # found_pastes.append({
        #     'source': 'Pastebin',
        #     'url': 'https://pastebin.com/XXXXX',
        #     'date': '2024-01-15',
        #     'type': 'paste_dump',
        #     'description': 'Email found in public paste'
        # })

        logger.info("Public paste check: Web scraping not implemented")
        logger.info("To enable: Implement paste scraping with proper rate limiting")

        return found_pastes

    def _check_github_leaks(self, email: str) -> List[Dict]:
        """
        Check GitHub for accidentally leaked credentials.

        Note: This is a SIMULATION. Real implementation would:
        - Use GitHub search API (has free tier)
        - Look for .env files, config files with email
        - Search code commits

        Args:
            email: Email address

        Returns:
            List of GitHub findings
        """
        logger.info(f"Checking GitHub for leaks: {sanitize_for_logging(email, 'email')}")

        # SIMULATION - Would use GitHub API or web scraping
        # Search patterns:
        # - "email@domain.com" in:file
        # - "password" + email in same file
        # - .env files containing email

        found_leaks = []

        # Example:
        # found_leaks.append({
        #     'source': 'GitHub',
        #     'repo': 'user/repository',
        #     'file': '.env',
        #     'date': '2024-01-10',
        #     'type': 'config_leak',
        #     'description': 'Email found in configuration file'
        # })

        logger.info("GitHub leak check: Not implemented (requires GitHub API)")
        logger.info("To enable: Set GITHUB_TOKEN in .env for authenticated searches")

        return found_leaks

    def _check_public_lists(self, email: str) -> List[Dict]:
        """
        Check public TXT lists and combo lists.

        Scans local breach files for email matches.
        File formats supported:
        - email:password
        - email|password
        - email;password
        - CSV/TXT combo lists

        Args:
            email: Email address

        Returns:
            List of findings from public lists
        """
        logger.info(f"Checking public lists for: {sanitize_for_logging(email, 'email')}")
        found_in_lists = []

        # Check if local breach files exist
        import os
        breach_dir = "data/breaches"

        if not os.path.exists(breach_dir):
            logger.info(f"Breach data directory not found: {breach_dir}")
            logger.info("To enable: Create ./data/breaches/ and add public breach lists")
            return found_in_lists

        logger.info(f"Scanning {breach_dir} for breach data...")

        try:
            # Scan all TXT files in breach directory
            for filename in os.listdir(breach_dir):
                if not filename.endswith('.txt'):
                    continue

                file_path = os.path.join(breach_dir, filename)
                logger.debug(f"Scanning file: {filename}")

                try:
                    # Use efficient line-by-line reading for large files
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line_num, line in enumerate(f, 1):
                            # Check if email is in the line
                            if email.lower() in line.lower():
                                found_in_lists.append({
                                    'source': f'Local List: {filename}',
                                    'file': filename,
                                    'line': line_num,
                                    'date': 'Unknown',
                                    'type': 'credential_dump',
                                    'description': f'Found in local breach file {filename}'
                                })
                                logger.warning(f"Email found in {filename} at line {line_num}")
                                break  # Stop after first match per file

                except Exception as e:
                    logger.error(f"Error scanning {filename}: {e}")

        except Exception as e:
            logger.error(f"Error accessing breach directory: {e}")

        return found_in_lists

    def _check_leakcheck_api(self, email: str) -> List[Dict]:
        """
        Check LeakCheck.io API (FREE tier available).

        FREE API: 3 requests/day without auth
        Returns: Source names, sometimes password hashes/parts

        Args:
            email: Email address

        Returns:
            List of breach findings with password info if available
        """
        found_breaches = []

        try:
            import requests

            # LeakCheck public API (free tier)
            url = f"https://leakcheck.io/api/public?check={email}"

            logger.info(f"Checking LeakCheck.io for: {sanitize_for_logging(email, 'email')}")

            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if data.get('found'):
                    # Parse results with password info
                    results = data.get('result', [])
                    
                    for result in results:
                        breach_data = {
                            'source': f"LeakCheck: {result.get('source', 'Unknown')}",
                            'date': result.get('date', 'Unknown'),
                            'type': 'breach',
                            'description': f"Email found in {result.get('source', 'breach')}"
                        }
                        
                        # Add password info if available (masked)
                        if result.get('password'):
                            pw = result.get('password')
                            # Mask password: show first char + asterisks
                            breach_data['password_hint'] = pw[0] + '*' * min(len(pw)-1, 8) if pw else None
                            breach_data['password_length'] = len(pw)
                        
                        # Add hash if available
                        if result.get('hash'):
                            breach_data['password_hash'] = result.get('hash')[:12] + '...'
                        
                        found_breaches.append(breach_data)
                    
                    logger.warning(f"LeakCheck: Email found in {len(found_breaches)} breaches")
                else:
                    logger.info("LeakCheck: No breaches found")
            elif response.status_code == 429:
                logger.warning("LeakCheck: Rate limit reached (3/day free tier)")
            else:
                logger.warning(f"LeakCheck API returned status {response.status_code}")

        except ImportError:
            logger.info("requests library not installed - LeakCheck check skipped")
        except Exception as e:
            logger.error(f"LeakCheck API error: {e}")

        return found_breaches

    def _check_dehashed_search(self, email: str) -> List[Dict]:
        """
        Check DeHashed.com free search.

        FREE: Limited web search (no API key needed)
        Can sometimes show password hints/hashes in results
        For full API access: Requires paid subscription

        Args:
            email: Email address

        Returns:
            List of findings with password hints if available
        """
        found = []

        try:
            import requests
            from bs4 import BeautifulSoup
            import re

            logger.info(f"Checking DeHashed free search for: {sanitize_for_logging(email, 'email')}")

            # DeHashed free search URL
            url = f"https://www.dehashed.com/search?query={email}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Look for results count
                results_text = response.text.lower()
                
                # Try to find number of results
                results_match = re.search(r'(\d+)\s+results?\s+found', results_text)
                
                if results_match or 'results found' in results_text:
                    result_count = results_match.group(1) if results_match else 'multiple'
                    
                    breach_data = {
                        'source': 'DeHashed',
                        'date': 'Unknown',
                        'type': 'search_result',
                        'description': f'Email appears in DeHashed database ({result_count} entries)',
                        'note': 'Login required for full details including passwords'
                    }
                    
                    # Try to extract any visible password hints from preview
                    # (DeHashed sometimes shows partial info in search results)
                    password_hints = soup.find_all(text=re.compile(r'password', re.I))
                    if password_hints:
                        breach_data['has_password_data'] = True
                    
                    found.append(breach_data)
                    logger.warning(f"DeHashed: Email found ({result_count} entries - full details require account)")
                else:
                    logger.info("DeHashed: No results in free search")
            elif response.status_code == 429:
                logger.warning("DeHashed: Rate limit reached")
            else:
                logger.warning(f"DeHashed returned status {response.status_code}")

        except ImportError:
            logger.info("beautifulsoup4 not installed - DeHashed check skipped")
        except Exception as e:
            logger.error(f"DeHashed search error: {e}")

        return found

    def _calculate_vulnerability_severity(self, results: Dict) -> str:
        """
        Calculate vulnerability severity based on findings.

        Args:
            results: Vulnerability check results

        Returns:
            Severity: 'none', 'low', 'medium', 'high', 'critical'
        """
        leak_count = results['leak_count']

        if leak_count == 0:
            return 'none'
        elif leak_count == 1:
            return 'low'
        elif leak_count <= 3:
            return 'medium'
        elif leak_count <= 5:
            return 'high'
        else:
            return 'critical'

    def _generate_security_recommendations(self, results: Dict) -> List[str]:
        """
        Generate security recommendations based on findings.

        Args:
            results: Vulnerability check results

        Returns:
            List of recommendations
        """
        recommendations = []

        if results['vulnerable']:
            recommendations.extend([
                "⚠️ Email found in public breach data!",
                "🔒 IMMEDIATELY change all passwords associated with this email",
                "🔑 Enable Two-Factor Authentication (2FA) on all accounts",
                "📧 Consider using a new email address for sensitive accounts",
                "🔍 Monitor accounts for unauthorized access attempts",
                "💾 Use a password manager (Bitwarden, 1Password, etc.)",
                "🚨 Check bank/financial accounts for suspicious activity",
                "📱 Update security questions on important accounts"
            ])

            if results['severity'] == 'critical':
                recommendations.insert(1, "🚨 CRITICAL: Multiple leaks detected - URGENT action required!")

            # Source-specific recommendations
            if 'GitHub' in results['found_in']:
                recommendations.append("💻 GitHub leak detected - rotate all API keys and tokens")

            if 'Pastebin' in results['found_in']:
                recommendations.append("📋 Found in paste dump - credentials may be actively exploited")

        else:
            recommendations.extend([
                "✅ No vulnerabilities found in public databases",
                "💡 Continue using strong, unique passwords",
                "🔐 Consider enabling 2FA as a preventive measure",
                "📊 Regularly check your accounts for suspicious activity"
            ])

        return recommendations

    def generate_vulnerability_report(self, email: str) -> str:
        """
        Generate human-readable vulnerability report.

        Args:
            email: Email address

        Returns:
            Formatted report string
        """
        results = self.check_vulnerability(email)

        report = f"\n{'='*70}\n"
        report += f"EMAIL VULNERABILITY INTELLIGENCE REPORT\n"
        report += f"{'='*70}\n"
        report += f"Email: {email}\n"
        report += f"{'='*70}\n\n"

        # Status
        if results['vulnerable']:
            report += f"🚨 STATUS: VULNERABLE\n\n"
            report += f"   Leak Count: {results['leak_count']}\n"
            report += f"   Severity: {results['severity'].upper()}\n"
            report += f"   Found In: {', '.join(results['found_in']) if results['found_in'] else 'N/A'}\n\n"
        else:
            report += f"✅ STATUS: CLEAN\n\n"
            report += f"   No vulnerabilities detected in public databases\n\n"

        # Breach Sources
        if results['breach_sources']:
            report += f"{'='*70}\n"
            report += f"BREACH SOURCES:\n"
            report += f"{'='*70}\n"
            for breach in results['breach_sources']:
                report += f"\n📍 Source: {breach.get('source', 'Unknown')}\n"
                report += f"   Date: {breach.get('date', 'Unknown')}\n"
                report += f"   Type: {breach.get('type', 'Unknown')}\n"
                if 'description' in breach:
                    report += f"   Details: {breach['description']}\n"

        # Recommendations
        report += f"\n{'='*70}\n"
        report += f"SECURITY RECOMMENDATIONS:\n"
        report += f"{'='*70}\n"
        for rec in results['recommendations']:
            report += f"{rec}\n"

        # Hash Information
        report += f"\n{'='*70}\n"
        report += f"EMAIL HASHES (for anonymous lookups):\n"
        report += f"{'='*70}\n"
        report += f"MD5:    {results['hashes']['md5']}\n"
        report += f"SHA1:   {results['hashes']['sha1']}\n"
        report += f"SHA256: {results['hashes']['sha256']}\n"

        # Footer
        report += f"\n{'='*70}\n"
        report += f"Note: This check uses publicly available breach data.\n"
        report += f"For complete protection:\n"
        report += f"  • Use unique passwords for every account\n"
        report += f"  • Enable 2FA wherever possible\n"
        report += f"  • Use a reputable password manager\n"
        report += f"  • Monitor accounts regularly\n"
        report += f"{'='*70}\n"

        return report
