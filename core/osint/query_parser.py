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

        # Extract site operator
        site_match = re.search(self.OPERATORS['site'], remaining)
        if site_match:
            parsed.site = site_match.group(1)
            remaining = remaining.replace(site_match.group(0), '')
            logger.debug(f"Extracted site: {parsed.site}")

        # Extract inurl operator
        inurl_match = re.search(self.OPERATORS['inurl'], remaining)
        if inurl_match:
            parsed.inurl = inurl_match.group(1)
            remaining = remaining.replace(inurl_match.group(0), '')
            logger.debug(f"Extracted inurl: {parsed.inurl}")

        # Extract intext operator
        intext_match = re.search(self.OPERATORS['intext'], remaining)
        if intext_match:
            # Handle both quoted and unquoted intext
            parsed.intext = intext_match.group(1) if intext_match.group(1) else intext_match.group(2)
            remaining = remaining.replace(intext_match.group(0), '')
            logger.debug(f"Extracted intext: {parsed.intext}")

        # Extract intitle operator
        intitle_match = re.search(self.OPERATORS['intitle'], remaining)
        if intitle_match:
            # Handle both quoted and unquoted intitle
            parsed.intitle = intitle_match.group(1) if intitle_match.group(1) else intitle_match.group(2)
            remaining = remaining.replace(intitle_match.group(0), '')
            logger.debug(f"Extracted intitle: {parsed.intitle}")

        # Extract filetype operator
        filetype_match = re.search(self.OPERATORS['filetype'], remaining)
        if filetype_match:
            parsed.filetype = filetype_match.group(1)
            remaining = remaining.replace(filetype_match.group(0), '')
            logger.debug(f"Extracted filetype: {parsed.filetype}")

        # Extract email operator
        email_match = re.search(self.OPERATORS['email'], remaining)
        if email_match:
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

        # Extract phone operator
        phone_match = re.search(self.OPERATORS['phone'], remaining)
        if phone_match:
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

        # Extract domain operator
        domain_match = re.search(self.OPERATORS['domain'], remaining)
        if domain_match:
            parsed.domain = domain_match.group(1)
            remaining = remaining.replace(domain_match.group(0), '')
            logger.debug(f"Extracted domain: {parsed.domain}")

        # Extract IP operator
        ip_match = re.search(self.OPERATORS['ip'], remaining)
        if ip_match:
            parsed.ip = ip_match.group(1)
            remaining = remaining.replace(ip_match.group(0), '')
            logger.debug(f"Extracted ip: {parsed.ip}")

        # Extract username operator
        username_match = re.search(self.OPERATORS['username'], remaining)
        if username_match:
            parsed.username = username_match.group(1)
            remaining = remaining.replace(username_match.group(0), '')
            logger.debug(f"Extracted username: {parsed.username}")

        # Extract country operator
        country_match = re.search(self.OPERATORS['country'], remaining)
        if country_match:
            parsed.country = country_match.group(1)
            remaining = remaining.replace(country_match.group(0), '')
            logger.debug(f"Extracted country: {parsed.country}")

        # Extract language operator
        lang_match = re.search(self.OPERATORS['lang'], remaining)
        if lang_match:
            parsed.lang = lang_match.group(1)
            remaining = remaining.replace(lang_match.group(0), '')
            logger.debug(f"Extracted lang: {parsed.lang}")

        # Extract explicit DDGS region operator
        region_match = re.search(self.OPERATORS['region'], remaining)
        if region_match:
            parsed.region = region_match.group(1)
            remaining = remaining.replace(region_match.group(0), '')
            logger.debug(f"Extracted region: {parsed.region}")

        # Extract exclusions (- operator) - ONLY if not part of phone/email operators
        # Look for standalone words starting with - (not within phone:... or email:...)
        exclude_pattern = r'\s-(\w+)(?=\s|$)'
        exclude_matches = re.findall(exclude_pattern, remaining)
        if exclude_matches:
            parsed.exclude = exclude_matches
            # Remove exclusions from remaining text
            for exc in exclude_matches:
                remaining = re.sub(rf'\s-{re.escape(exc)}(?=\s|$)', '', remaining)
            logger.debug(f"Extracted exclusions: {parsed.exclude}")

        # Clean up remaining text
        parsed.text = ' '.join(remaining.split()).strip()

        logger.info(f"Parsed query: {parsed}")
        return parsed

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
