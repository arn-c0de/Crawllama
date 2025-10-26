"""Email Intelligence Module for OSINT.

Provides:
- Email syntax validation
- Domain verification
- MX record lookup
- Disposable email detection
- Social profile discovery
- Email pattern generation
- Breach detection (HaveIBeenPwned free API)
- Email reputation checking
- Provider identification
"""

import re
import logging
from typing import Dict, List, Optional
import socket
import asyncio
import aiohttp

logger = logging.getLogger("crawllama")

# Common disposable email domains
DISPOSABLE_DOMAINS = {
    '10minutemail.com', 'tempmail.com', 'guerrillamail.com',
    'mailinator.com', 'throwaway.email', 'temp-mail.org',
    'getnada.com', 'trashmail.com', 'fakeinbox.com',
    'maildrop.cc', 'sharklasers.com', 'guerrillamail.info',
    'yopmail.com', 'mohmal.com', 'emailondeck.com',
    'mintemail.com', 'mytemp.email', 'tempinbox.com'
}

# Common email providers
EMAIL_PROVIDERS = {
    'gmail.com': 'Google Gmail',
    'googlemail.com': 'Google Gmail',
    'yahoo.com': 'Yahoo Mail',
    'yahoo.de': 'Yahoo Mail',
    'outlook.com': 'Microsoft Outlook',
    'hotmail.com': 'Microsoft Hotmail',
    'live.com': 'Microsoft Live',
    'protonmail.com': 'ProtonMail (Encrypted)',
    'proton.me': 'ProtonMail (Encrypted)',
    'icloud.com': 'Apple iCloud',
    'me.com': 'Apple iCloud',
    'aol.com': 'AOL Mail',
    'gmx.de': 'GMX',
    'gmx.net': 'GMX',
    'web.de': 'Web.de',
    't-online.de': 'T-Online',
    'mail.ru': 'Mail.ru',
    'yandex.com': 'Yandex Mail',
    'zoho.com': 'Zoho Mail',
    'tutanota.com': 'Tutanota (Encrypted)'
}


class EmailIntelligence:
    """Email OSINT capabilities."""

    def __init__(self):
        """Initialize email intelligence."""
        self.disposable_domains = DISPOSABLE_DOMAINS
        self.email_providers = EMAIL_PROVIDERS
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
                'provider': str,
                'provider_type': str,
                'breaches': List[Dict],
                'breach_count': int,
                'gravatar_found': bool,
                'social_profiles': List[Dict]
            }

        Example:
            >>> intel = EmailIntelligence()
            >>> result = intel.analyze_email('test@example.com')
            >>> result['valid']
            True
            >>> result['domain']
            'example.com'
        """
        logger.info(f"Analyzing email: {email}")

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
            'provider': 'Unknown',
            'provider_type': 'Unknown',
            'breaches': [],
            'breach_count': 0,
            'gravatar_found': False,
            'social_profiles': []
        }

        # Validate syntax
        results['valid'] = self.validate_syntax(email)
        if not results['valid']:
            logger.warning(f"Invalid email syntax: {email}")
            return results

        # Extract parts
        results['username'], results['domain'] = self.extract_parts(email)

        # Check if disposable
        results['disposable'] = self.is_disposable(results['domain'])

        # Identify provider
        results['provider'] = self.identify_provider(results['domain'])
        results['provider_type'] = self.get_provider_type(results['domain'])

        # Check MX records
        results['mx_records'] = self.check_mx_records(results['domain'])
        results['domain_exists'] = len(results['mx_records']) > 0

        # Check for data breaches (async call wrapped)
        try:
            breach_data = asyncio.run(self.check_breaches(email))
            results['breaches'] = breach_data.get('breaches', [])
            results['breach_count'] = len(results['breaches'])
        except Exception as e:
            logger.error(f"Breach check error: {e}")

        # Check Gravatar
        results['gravatar_found'] = self.check_gravatar(email)

        # Generate variations
        results['variations'] = self.generate_variations(email)

        # Calculate confidence
        results['confidence'] = self._calculate_confidence(results)

        logger.info(f"Email analysis complete: {email} (confidence: {results['confidence']:.2f})")
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
        logger.debug(f"Email syntax validation for '{email}': {is_valid}")
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

    def identify_provider(self, domain: str) -> str:
        """
        Identify email provider from domain.
        
        Args:
            domain: Email domain
            
        Returns:
            Provider name or 'Unknown'
        """
        return self.email_providers.get(domain.lower(), 'Custom Domain')

    def get_provider_type(self, domain: str) -> str:
        """
        Get provider type (Personal, Business, Encrypted, Disposable).
        
        Args:
            domain: Email domain
            
        Returns:
            Provider type
        """
        if self.is_disposable(domain):
            return 'Disposable/Temporary'
        elif domain.lower() in self.email_providers:
            provider = self.email_providers[domain.lower()]
            if 'Encrypted' in provider:
                return 'Encrypted Email Provider'
            return 'Public Email Provider'
        else:
            return 'Custom/Business Domain'

    async def check_breaches(self, email: str) -> Dict:
        """
        Check if email appears in data breaches using HaveIBeenPwned API.
        Free API, no key required, but rate-limited.
        
        Args:
            email: Email address to check
            
        Returns:
            Dict with breach information
        """
        try:
            url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
            headers = {
                'User-Agent': 'CrawlLama-OSINT-Tool',
                'api-version': '3'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        breaches = await response.json()
                        logger.info(f"Found {len(breaches)} breaches for email")
                        return {
                            'breaches': [
                                {
                                    'name': breach.get('Name'),
                                    'domain': breach.get('Domain'),
                                    'breach_date': breach.get('BreachDate'),
                                    'pwn_count': breach.get('PwnCount'),
                                    'data_classes': breach.get('DataClasses', [])
                                }
                                for breach in breaches
                            ]
                        }
                    elif response.status == 404:
                        logger.info(f"No breaches found for email (good news!)")
                        return {'breaches': []}
                    elif response.status == 429:
                        logger.warning("Rate limited by HaveIBeenPwned API")
                        return {'breaches': [], 'error': 'Rate limited'}
                        
        except Exception as e:
            logger.error(f"Breach check error: {e}")
            
        return {'breaches': []}

    def check_gravatar(self, email: str) -> bool:
        """
        Check if email has a Gravatar profile (indicates active use).
        
        Args:
            email: Email address
            
        Returns:
            True if Gravatar exists
        """
        try:
            import hashlib
            
            # Generate MD5 hash of email
            email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
            
            # Gravatar uses email hash in URL
            url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
            
            import urllib.request
            try:
                urllib.request.urlopen(url, timeout=5)
                logger.info(f"Gravatar found for email")
                return True
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return False
                    
        except Exception as e:
            logger.error(f"Gravatar check error: {e}")
            
        return False

    def get_social_profile_urls(self, email: str) -> List[Dict]:
        """
        Generate potential social profile URLs based on email.
        Note: These are potential URLs, not confirmed profiles.
        
        Args:
            email: Email address
            
        Returns:
            List of potential profile URLs
        """
        username, domain = self.extract_parts(email)
        
        # Extract possible username (remove dots, numbers)
        clean_username = username.replace('.', '').replace('_', '')
        
        profiles = [
            {
                'platform': 'GitHub',
                'url': f"https://github.com/{username}",
                'search_url': f"https://github.com/search?q={email}&type=users"
            },
            {
                'platform': 'Twitter/X',
                'url': f"https://twitter.com/{clean_username}",
                'search_url': f"https://twitter.com/search?q={email}"
            },
            {
                'platform': 'LinkedIn',
                'url': f"https://www.linkedin.com/search/results/all/?keywords={email}",
                'search_url': f"https://www.linkedin.com/search/results/all/?keywords={email}"
            },
            {
                'platform': 'Reddit',
                'url': f"https://www.reddit.com/user/{clean_username}",
                'search_url': f"https://www.reddit.com/search/?q={email}"
            },
            {
                'platform': 'Stack Overflow',
                'url': f"https://stackoverflow.com/search?q={email}",
                'search_url': f"https://stackoverflow.com/search?q={email}"
            }
        ]
        
        return profiles

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
            score += 0.2

        # Domain exists (MX records)
        if results['domain_exists']:
            score += 0.3

        # Not disposable
        if not results['disposable']:
            score += 0.2
        
        # Gravatar found (indicates active use)
        if results.get('gravatar_found'):
            score += 0.15
        
        # Known provider
        if results.get('provider') != 'Unknown':
            score += 0.15

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
        logger.info(f"Searching online for: {email}")

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
