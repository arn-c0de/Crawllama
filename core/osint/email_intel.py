"""Email Intelligence Module for OSINT.

Provides:
- Email syntax validation
- Domain verification
- MX record lookup
- Disposable email detection
- Social profile discovery
- Email pattern generation
"""

import re
import logging
from typing import Dict, List, Optional
import socket

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
                'variations': List[str]
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
            'variations': []
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

        # Check MX records
        results['mx_records'] = self.check_mx_records(results['domain'])
        results['domain_exists'] = len(results['mx_records']) > 0

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
