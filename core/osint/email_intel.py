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

import hashlib
import logging
import re
import socket

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
        self._breach_manager = None
        logger.info("Email Intelligence initialized")

    def analyze_email(self, email: str) -> dict:
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

    def check_mx_records(self, domain: str) -> list[str]:
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

    def generate_variations(self, email: str) -> list[str]:
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

    def check_data_breaches(self, email: str) -> dict:
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
            if self._breach_manager is None:
                from core.osint.sources import create_default_manager
                self._breach_manager = create_default_manager()

            manager_results = self._breach_manager.query_all(email)
            breaches = manager_results.get('breaches', [])
            paste_count = manager_results.get('paste_count', 0)

            results['breach_count'] = len(breaches)
            results['paste_count'] = paste_count
            results['pwned'] = results['breach_count'] > 0 or results['paste_count'] > 0
            results['breaches'] = breaches

            # Find most recent breach
            if breaches:
                breach_dates = [
                    b.get('BreachDate', '') or b.get('date', '')
                    for b in breaches
                    if b.get('BreachDate') or b.get('date')
                ]
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

    def _calculate_breach_severity(self, results: dict) -> str:
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

    def _generate_breach_recommendations(self, results: dict) -> list[str]:
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
            report += "⚠️  STATUS: COMPROMISED\n"
            report += f"    Breach Count: {results['breach_count']}\n"
            report += f"    Paste Count: {results['paste_count']}\n"
            report += f"    Severity: {results['severity'].upper()}\n"
            if results['last_breach']:
                report += f"    Last Breach: {results['last_breach']}\n"
        else:
            report += "✅ STATUS: CLEAN\n"
            report += "    No breaches found in public databases\n"

        report += f"\n{'='*60}\n"
        report += "RECOMMENDATIONS:\n"
        report += f"{'='*60}\n"
        for rec in results['recommendations']:
            report += f"  {rec}\n"

        report += f"\n{'='*60}\n"
        report += "Note: This check uses public breach databases.\n"
        report += "Always use strong, unique passwords and enable 2FA.\n"
        report += f"{'='*60}\n"

        return report

    def _calculate_confidence(self, results: dict) -> float:
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

    def search_email_online(self, email: str, max_results: int = 5) -> list[dict]:
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

    def find_company_pattern(self, emails: list[str]) -> str | None:
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
        self._breach_manager = None
        logger.info("Email Vulnerability Intelligence initialized")

    def check_vulnerability(self, email: str) -> dict:
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
            breach_sources = self._collect_breach_sources(email)

            results['breach_sources'] = breach_sources
            results['leak_count'] = len(breach_sources)
            results['vulnerable'] = results['leak_count'] > 0
            results['found_in'] = list(set(s['source'] for s in breach_sources))
            results['severity'] = self._calculate_vulnerability_severity(results)
            results['recommendations'] = self._generate_security_recommendations(results)

            logger.info(f"Vulnerability check complete: {sanitize_for_logging(email, 'email')} - Vulnerable: {results['vulnerable']}")

        except Exception as e:
            logger.error(f"Error checking vulnerability for {email}: {e}")
            results['error'] = str(e)

        return results

    def _collect_breach_sources(self, email: str) -> list[dict]:
        """Gather breach records for an email from all configured sources."""
        # 1. Local TXT lists (active - works immediately)
        breach_sources = list(self._check_public_lists(email))

        # 2. LeakCheck.io free API (3 requests/day)
        breach_sources.extend(self._check_leakcheck_api(email))

        # 3. Additional breach sources via BreachManager
        if self._breach_manager is None:
            from core.osint.sources import create_default_manager
            self._breach_manager = create_default_manager()

        manager_results = self._breach_manager.query_all(email)
        for breach in manager_results.get('breaches', []):
            source_name = breach.get('Source', 'Unknown')
            if source_name in ("LeakCheck", "LocalDB"):
                continue  # already covered by the checks above
            breach_sources.append({
                'source': source_name,
                'date': breach.get('BreachDate', 'Unknown'),
                'type': 'breach',
                'description': breach.get('Description') or breach.get('Title', 'Unknown'),
                'metadata': breach.get('Metadata')
            })
        return breach_sources

    def _generate_email_hashes(self, email: str) -> dict[str, str]:
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

    def _check_public_lists(self, email: str) -> list[dict]:
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
                    with open(file_path, encoding='utf-8', errors='ignore') as f:
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

    def _check_leakcheck_api(self, email: str) -> list[dict]:
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

    def _calculate_vulnerability_severity(self, results: dict) -> str:
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

    def _generate_security_recommendations(self, results: dict) -> list[str]:
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
        report += "EMAIL VULNERABILITY INTELLIGENCE REPORT\n"
        report += f"{'='*70}\n"
        report += f"Email: {email}\n"
        report += f"{'='*70}\n\n"

        # Status
        if results['vulnerable']:
            report += "🚨 STATUS: VULNERABLE\n\n"
            report += f"   Leak Count: {results['leak_count']}\n"
            report += f"   Severity: {results['severity'].upper()}\n"
            report += f"   Found In: {', '.join(results['found_in']) if results['found_in'] else 'N/A'}\n\n"
        else:
            report += "✅ STATUS: CLEAN\n\n"
            report += "   No vulnerabilities detected in public databases\n\n"

        # Breach Sources
        if results['breach_sources']:
            report += f"{'='*70}\n"
            report += "BREACH SOURCES:\n"
            report += f"{'='*70}\n"
            for breach in results['breach_sources']:
                report += f"\n📍 Source: {breach.get('source', 'Unknown')}\n"
                report += f"   Date: {breach.get('date', 'Unknown')}\n"
                report += f"   Type: {breach.get('type', 'Unknown')}\n"
                if 'description' in breach:
                    report += f"   Details: {breach['description']}\n"

        # Recommendations
        report += f"\n{'='*70}\n"
        report += "SECURITY RECOMMENDATIONS:\n"
        report += f"{'='*70}\n"
        for rec in results['recommendations']:
            report += f"{rec}\n"

        # Hash Information
        report += f"\n{'='*70}\n"
        report += "EMAIL HASHES (for anonymous lookups):\n"
        report += f"{'='*70}\n"
        report += f"MD5:    {results['hashes']['md5']}\n"
        report += f"SHA1:   {results['hashes']['sha1']}\n"
        report += f"SHA256: {results['hashes']['sha256']}\n"

        # Footer
        report += f"\n{'='*70}\n"
        report += "Note: This check uses publicly available breach data.\n"
        report += "For complete protection:\n"
        report += "  • Use unique passwords for every account\n"
        report += "  • Enable 2FA wherever possible\n"
        report += "  • Use a reputable password manager\n"
        report += "  • Monitor accounts regularly\n"
        report += f"{'='*70}\n"

        return report
