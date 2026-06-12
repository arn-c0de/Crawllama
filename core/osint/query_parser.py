"""OSINT Query Parser for advanced search operators.

Supports operators like:
- site:example.com
- inurl:admin
- intext:"confidential"
- intitle:"index of"
- filetype:pdf
- email:test@example.com
- phone:"+49 123 456789"
"""

import re
import logging
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("crawllama")


@dataclass
class SearchQuery:
    """Parsed search query with operators."""
    text: str  # Remaining search text
    site: Optional[str] = None
    inurl: Optional[str] = None
    intext: Optional[str] = None
    intitle: Optional[str] = None
    filetype: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    domain: Optional[str] = None
    ip: Optional[str] = None
    username: Optional[str] = None
    country: Optional[str] = None
    lang: Optional[str] = None
    region: Optional[str] = None
    exclude: List[str] = field(default_factory=list)
    raw_query: str = ""  # Original query
    
    # Multiple targets support
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    ips: List[str] = field(default_factory=list)
    
    # Memory operations
    remember_type: Optional[str] = None  # email, phone, ip, username, domain, note
    remember_value: Optional[str] = None
    recall_category: Optional[str] = None  # emails, phones, ips, usernames, domains, notes, all, search
    recall_query: Optional[str] = None
    forget_type: Optional[str] = None  # email, phone, ip, username, category, all
    forget_value: Optional[str] = None

    def __repr__(self):
        parts = [f"text='{self.text}'"]
        if self.site:
            parts.append(f"site={self.site}")
        if self.inurl:
            parts.append(f"inurl={self.inurl}")
        if self.intext:
            parts.append(f"intext='{self.intext}'")
        if self.intitle:
            parts.append(f"intitle='{self.intitle}'")
        if self.filetype:
            parts.append(f"filetype={self.filetype}")
        if self.email:
            parts.append(f"email={self.email}")
        if self.phone:
            parts.append(f"phone='{self.phone}'")
        if self.domain:
            parts.append(f"domain={self.domain}")
        if self.ip:
            parts.append(f"ip={self.ip}")
        if self.username:
            parts.append(f"username={self.username}")
        if self.country:
            parts.append(f"country={self.country}")
        if self.lang:
            parts.append(f"lang={self.lang}")
        if self.region:
            parts.append(f"region={self.region}")
        if self.exclude:
            parts.append(f"exclude={self.exclude}")
        return f"SearchQuery({', '.join(parts)})"


class OSINTQueryParser:
    """Parse OSINT search queries with operators."""

    # Operator patterns
    OPERATORS = {
        'site': r'site:([^\s]+)',
        'inurl': r'inurl:([^\s]+)',
        'intext': r'intext:(?:"([^"]+)"|([^\s]+))',
        'intitle': r'intitle:(?:"([^"]+)"|([^\s]+))',
        'filetype': r'filetype:([^\s]+)',
        'email': (
            r'email:(.+?)(?=\s(?:site:|inurl:|intext:|intitle:|filetype:|phone:|domain:|ip:|'
            r'username:|country:|lang:|region:|remember\s|recall|forget\s)|$)'
        ),  # Support multiple emails without swallowing following operators
        'phone': r'(?:phone|phonenumber):(?:"([^"]+)"|([^\s]+(?:[\s/\-][^\s]+)*))',  # Support with/without quotes, handle spaces/slashes/dashes
        'domain': r'domain:([^\s]+)',
        'ip': r'ip:([^\s]+)',
        'username': r'username:([^\s]+)',
        'country': r'country:([^\s]+)',
        'lang': r'lang:([^\s]+)',
        'region': r'region:([^\s]+)',
        'exclude': r'-([^\s]+)',
        # Memory operators
        'remember': r'remember\s+(\w+):(.+?)(?:\s|$)',
        'recall': r'recall(?:\s+(\w+))?(?:\s+search:(.+))?',
        'forget': r'forget\s+(\w+):(\S+)'  # Fixed: use \S+ to match any non-whitespace (emails, IPs, etc.)
    }
    
    # Pattern to detect multiple emails/phones in text
    EMAIL_PATTERN = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
    PHONE_PATTERN = re.compile(r'(?:\+?\d{1,3}[\s-]?)?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4}')

    def __init__(self):
        """Initialize query parser."""
        logger.info("OSINT Query Parser initialized")

    def parse(self, query: str) -> SearchQuery:
        """
        Parse query string into structured search.

        Args:
            query: Raw search query

        Returns:
            SearchQuery object with parsed operators

        Examples:
            >>> parser = OSINTQueryParser()
            >>> q = parser.parse('site:github.com inurl:python "machine learning"')
            >>> print(q.site)
            'github.com'
            >>> print(q.text)
            '"machine learning"'

            >>> q = parser.parse('email:test@example.com site:linkedin.com')
            >>> print(q.email)
            'test@example.com'
        """
        remaining = query.strip()
        parsed = SearchQuery(text="", raw_query=query)

        # IMPORTANT: Parse memory operators FIRST (forget, remember, recall)
        # These need priority because they can contain other operator keywords like "email:" or "phone:"
        remaining = self._extract_memory_operators(parsed, remaining)

        remaining = self._extract_plain_operator(parsed, 'site', remaining)
        remaining = self._extract_plain_operator(parsed, 'inurl', remaining)
        remaining = self._extract_quoted_operator(parsed, 'intext', remaining)
        remaining = self._extract_quoted_operator(parsed, 'intitle', remaining)
        remaining = self._extract_plain_operator(parsed, 'filetype', remaining)
        remaining = self._extract_email_operator(parsed, remaining)
        remaining = self._extract_phone_operator(parsed, remaining)
        remaining = self._extract_plain_operator(parsed, 'domain', remaining)
        remaining = self._extract_plain_operator(parsed, 'ip', remaining)
        remaining = self._extract_plain_operator(parsed, 'username', remaining)
        remaining = self._extract_plain_operator(parsed, 'country', remaining)
        remaining = self._extract_plain_operator(parsed, 'lang', remaining)
        # Explicit DDGS region operator
        remaining = self._extract_plain_operator(parsed, 'region', remaining)
        remaining = self._extract_exclusions(parsed, remaining)

        # Clean up remaining text
        parsed.text = ' '.join(remaining.split()).strip()

        logger.info(f"Parsed query: {parsed}")
        return parsed

    def _extract_memory_operators(self, parsed: SearchQuery, remaining: str) -> str:
        """Extract memory operators (remember, recall, forget) from the query."""
        # Remember
        remember_match = re.search(self.OPERATORS['remember'], remaining)
        if remember_match:
            parsed.remember_type = remember_match.group(1)  # email, phone, ip, username, category, note
            parsed.remember_value = remember_match.group(2).strip()
            remaining = remaining.replace(remember_match.group(0), '')
            logger.debug(f"Extracted remember: {parsed.remember_type}={parsed.remember_value}")

        # Recall
        recall_match = re.search(self.OPERATORS['recall'], remaining)
        if recall_match:
            parsed.recall_category = recall_match.group(1) if recall_match.group(1) else 'all'
            parsed.recall_query = recall_match.group(2).strip() if recall_match.group(2) else None
            remaining = remaining.replace(recall_match.group(0), '')
            logger.debug(f"Extracted recall: category={parsed.recall_category}, query={parsed.recall_query}")

        # Forget
        forget_match = re.search(self.OPERATORS['forget'], remaining)
        if forget_match:
            parsed.forget_type = forget_match.group(1)  # email, phone, ip, username, category, all
            parsed.forget_value = forget_match.group(2).strip()
            remaining = remaining.replace(forget_match.group(0), '')
            logger.debug(f"Extracted forget: {parsed.forget_type}={parsed.forget_value}")

        return remaining

    def _extract_plain_operator(self, parsed: SearchQuery, name: str, remaining: str) -> str:
        """Extract an operator with a single unquoted value (e.g. site:example.com)."""
        match = re.search(self.OPERATORS[name], remaining)
        if not match:
            return remaining

        setattr(parsed, name, match.group(1))
        logger.debug(f"Extracted {name}: {match.group(1)}")
        return remaining.replace(match.group(0), '')

    def _extract_quoted_operator(self, parsed: SearchQuery, name: str, remaining: str) -> str:
        """Extract an operator that supports quoted or unquoted values (intext, intitle)."""
        match = re.search(self.OPERATORS[name], remaining)
        if not match:
            return remaining

        # Handle both quoted and unquoted values
        value = match.group(1) if match.group(1) else match.group(2)
        setattr(parsed, name, value)
        logger.debug(f"Extracted {name}: {value}")
        return remaining.replace(match.group(0), '')

    def _extract_email_operator(self, parsed: SearchQuery, remaining: str) -> str:
        """Extract the email operator, supporting multiple emails in one value."""
        email_match = re.search(self.OPERATORS['email'], remaining)
        if not email_match:
            return remaining

        email_string = email_match.group(1)
        # Extract all emails from the string
        emails = self.EMAIL_PATTERN.findall(email_string)
        if emails:
            parsed.email = emails[0]  # Keep first for backward compatibility
            parsed.emails = emails
            logger.debug(f"Extracted {len(emails)} emails: {emails}")
        else:
            # Single email without proper format
            parsed.email = email_string.strip()
            parsed.emails = [email_string.strip()]
        remaining = remaining.replace(email_match.group(0), '')
        logger.debug(f"Extracted email(s): {parsed.emails}")
        return remaining

    def _extract_phone_operator(self, parsed: SearchQuery, remaining: str) -> str:
        """Extract the phone operator, supporting multiple comma/semicolon-separated numbers."""
        phone_match = re.search(self.OPERATORS['phone'], remaining)
        if not phone_match:
            return remaining

        # Handle both quoted and unquoted phone
        phone_string = phone_match.group(1) if phone_match.group(1) else phone_match.group(2)
        # Split by common separators for multiple phones
        phones = [p.strip() for p in re.split(r'[,;]', phone_string) if p.strip()]
        if phones:
            parsed.phone = phones[0]  # Keep first for backward compatibility
            parsed.phones = phones
            logger.debug(f"Extracted {len(phones)} phone numbers: {phones}")
        remaining = remaining.replace(phone_match.group(0), '')
        logger.debug(f"Extracted phone(s): {parsed.phones}")
        return remaining

    def _extract_exclusions(self, parsed: SearchQuery, remaining: str) -> str:
        """Extract exclusions (- operator) - ONLY if not part of phone/email operators."""
        # Look for standalone words starting with - (not within phone:... or email:...)
        exclude_pattern = r'\s-(\w+)(?=\s|$)'
        exclude_matches = re.findall(exclude_pattern, remaining)
        if not exclude_matches:
            return remaining

        parsed.exclude = exclude_matches
        # Remove exclusions from remaining text
        for exc in exclude_matches:
            remaining = re.sub(rf'\s-{re.escape(exc)}(?=\s|$)', '', remaining)
        logger.debug(f"Extracted exclusions: {parsed.exclude}")
        return remaining

    def build_search_query(self, parsed: SearchQuery) -> str:
        """
        Build search engine query from parsed operators.

        Args:
            parsed: SearchQuery object

        Returns:
            Formatted query string for search engines

        Example:
            >>> parser = OSINTQueryParser()
            >>> q = parser.parse('site:github.com python')
            >>> parser.build_search_query(q)
            'site:github.com python'
        """
        parts = []

        # Add operators
        if parsed.site:
            parts.append(f'site:{parsed.site}')
        if parsed.inurl:
            parts.append(f'inurl:{parsed.inurl}')
        if parsed.intext:
            parts.append(f'intext:"{parsed.intext}"')
        if parsed.intitle:
            parts.append(f'intitle:"{parsed.intitle}"')
        if parsed.filetype:
            parts.append(f'filetype:{parsed.filetype}')

        # Add email search (improved query for better results)
        if parsed.email:
            # Search for exact email with quotes for precise matches
            parts.append(f'"{parsed.email}"')
            # Add contact/impressum keywords to find relevant pages
            if '@' in parsed.email:
                domain = parsed.email.split('@')[1] if '@' in parsed.email else ''
                if domain and not parsed.site:
                    # If no site specified, search within that domain
                    parts.append(f'site:{domain}')
                parts.append('(contact OR impressum OR kontakt OR about)')
            else:
                # If just username without @, search for it with email-related terms
                parts.append('email OR contact OR "@"')

        # Add phone search (improved query)
        if parsed.phone:
            # Search for exact phone number with quotes
            parts.append(f'"{parsed.phone}"')
            # Add contact keywords
            parts.append('(contact OR impressum OR kontakt OR phone OR telefon)')

        # Add main text
        if parsed.text:
            parts.append(parsed.text)

        # Add exclusions
        for exc in parsed.exclude:
            parts.append(f'-{exc}')

        # Exclude common irrelevant results for email/phone searches
        if parsed.email or parsed.phone:
            parts.append('-"was bedeutet" -"bedeutung" -"定义" -"什么意思"')

        return ' '.join(parts)

    def is_osint_query(self, query: str) -> bool:
        """
        Check if query contains OSINT operators.

        Args:
            query: Search query

        Returns:
            True if query contains any OSINT operator
        """
        for operator_pattern in self.OPERATORS.values():
            if re.search(operator_pattern, query):
                return True
        return False

    def extract_targets(self, query: str) -> dict:
        """
        Extract specific targets (email, phone, domain) from query.

        Args:
            query: Search query

        Returns:
            Dictionary with extracted targets

        Example:
            >>> parser = OSINTQueryParser()
            >>> targets = parser.extract_targets('email:test@example.com phone:"+49123" domain:example.com')
            >>> targets['email']
            'test@example.com'
            >>> targets['domain']
            'example.com'
        """
        parsed = self.parse(query)

        targets = {}
        if parsed.email:
            targets['email'] = parsed.email
        if parsed.phone:
            targets['phone'] = parsed.phone
        if parsed.domain:
            targets['domain'] = parsed.domain

        return targets
