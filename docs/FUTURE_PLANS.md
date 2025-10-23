









**Version:** 1.2+
**Status:** Planning Phase
**Last Updated:** 2025-01-23

---

## 🎯 Vision

CrawlLama soll sich zu einer umfassenden **AI-gestützten OSINT-Plattform** entwickeln, die professionelle Recherche, Security-Analysen und investigative Aufgaben unterstützt.

---

## 🔍 Phase 5: OSINT & Advanced Search (v1.2)

### Übersicht

Integration von **OSINT** (Open Source Intelligence) Capabilities mit AI-gestützter Analyse für:
- 🔎 Erweiterte Suchoperatoren
- 📧 Email/Domain Intelligence
- 📱 Telefonnummern-Analyse
- 👤 Person/Entity Research
- 🌐 Social Media Intelligence
- 🔗 Relationship Mapping

### ⚖️ Legal & Ethical Framework

**WICHTIG:** Alle OSINT-Features sind ausschließlich für legitime Zwecke:
- ✅ Security Research
- ✅ Threat Intelligence
- ✅ Investigative Journalism
- ✅ Compliance & Due Diligence
- ✅ Academic Research
- ❌ NICHT für Stalking, Harassment oder illegale Aktivitäten

**Implementierung:**
```python
# Nutzer muss Terms of Use akzeptieren
OSINT_DISCLAIMER = """
OSINT-Features nur für legitime, legale Zwecke nutzen.
Respektiere Privacy-Rechte und lokale Gesetze.
Missbrauch wird geloggt und kann zu Account-Sperre führen.
"""
```

---

## 🔎 Feature 1: Advanced Search Operators

### Konzept

AI-gestützte Interpretation von erweiterten Google-ähnlichen Suchoperatoren:

```
site:example.com "John Doe"
inurl:admin filetype:pdf
intext:"email" site:linkedin.com
intitle:"index of" password.txt
phonenumber:"+49 123 456789"
email:test@example.com
```

### Technische Umsetzung

#### 1. Query Parser

```python
# core/osint/query_parser.py

import re
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class SearchQuery:
    """Parsed search query with operators."""
    text: str
    site: Optional[str] = None
    inurl: Optional[str] = None
    intext: Optional[str] = None
    intitle: Optional[str] = None
    filetype: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    exclude: List[str] = None

class OSINTQueryParser:
    """Parse OSINT search queries with operators."""

    OPERATORS = {
        'site:': r'site:([^\s]+)',
        'inurl:': r'inurl:([^\s]+)',
        'intext:': r'intext:"([^"]+)"',
        'intitle:': r'intitle:"([^"]+)"',
        'filetype:': r'filetype:([^\s]+)',
        'email:': r'email:([^\s]+)',
        'phone:': r'phone:"([^"]+)"',
        'phonenumber:': r'phonenumber:"([^"]+)"',
        '-': r'-([^\s]+)'  # Exclude
    }

    def parse(self, query: str) -> SearchQuery:
        """
        Parse query string into structured search.

        Args:
            query: Raw search query

        Returns:
            SearchQuery object

        Example:
            >>> parser = OSINTQueryParser()
            >>> q = parser.parse('site:github.com inurl:python "machine learning"')
            >>> q.site
            'github.com'
        """
        parsed = SearchQuery(text=query)

        # Extract site operator
        site_match = re.search(self.OPERATORS['site:'], query)
        if site_match:
            parsed.site = site_match.group(1)
            query = query.replace(site_match.group(0), '')

        # Extract inurl
        inurl_match = re.search(self.OPERATORS['inurl:'], query)
        if inurl_match:
            parsed.inurl = inurl_match.group(1)
            query = query.replace(inurl_match.group(0), '')

        # Extract intext
        intext_match = re.search(self.OPERATORS['intext:'], query)
        if intext_match:
            parsed.intext = intext_match.group(1)
            query = query.replace(intext_match.group(0), '')

        # Extract email
        email_match = re.search(self.OPERATORS['email:'], query)
        if email_match:
            parsed.email = email_match.group(1)
            query = query.replace(email_match.group(0), '')

        # Extract phone
        phone_patterns = [
            self.OPERATORS['phone:'],
            self.OPERATORS['phonenumber:']
        ]
        for pattern in phone_patterns:
            phone_match = re.search(pattern, query)
            if phone_match:
                parsed.phone = phone_match.group(1)
                query = query.replace(phone_match.group(0), '')
                break

        # Extract exclusions
        exclude_matches = re.findall(self.OPERATORS['-'], query)
        if exclude_matches:
            parsed.exclude = exclude_matches

        # Remaining text
        parsed.text = query.strip()

        return parsed
```

#### 2. AI-Assisted Query Enhancement

```python
# core/osint/query_enhancer.py

from typing import List, Dict
from core.llm_client import OllamaClient

class QueryEnhancer:
    """Use AI to enhance and expand OSINT queries."""

    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client

    def generate_variations(self, query: str) -> List[str]:
        """
        Generate query variations for better coverage.

        Args:
            query: Original query

        Returns:
            List of query variations

        Example:
            Input: "John Doe security researcher"
            Output: [
                "John Doe cybersecurity",
                "John Doe infosec",
                "John Doe hacker",
                ...
            ]
        """
        prompt = f"""Generiere 5 alternative Suchanfragen für:
"{query}"

Nutze Synonyme, verwandte Begriffe und alternative Formulierungen.
Antworte nur mit den Varianten, eine pro Zeile."""

        response = self.llm.generate(prompt)

        # Parse variations
        variations = [line.strip() for line in response.split('\n')
                     if line.strip() and not line.startswith('#')]

        return variations[:5]

    def suggest_operators(self, query: str) -> Dict[str, str]:
        """
        Suggest appropriate operators for query.

        Args:
            query: Search query

        Returns:
            Dictionary with operator suggestions
        """
        prompt = f"""Analysiere diese Suchanfrage: "{query}"

Welche Suchoperatoren würden die Suche verbessern?

Verfügbare Operatoren:
- site: (spezifische Domain)
- inurl: (Text in URL)
- intext: (Text im Inhalt)
- filetype: (Dateityp)

Antworte im Format:
operator: "wert" - Begründung"""

        response = self.llm.generate(prompt)

        # Parse suggestions (simplified)
        suggestions = {}
        for line in response.split('\n'):
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    suggestions[parts[0].strip()] = parts[1].strip()

        return suggestions
```

#### 3. OSINT Search Engine

```python
# core/osint/search_engine.py

from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import re

class OSINTSearchEngine:
    """Execute OSINT searches with advanced operators."""

    def __init__(self, rate_limiter, safe_fetch):
        self.rate_limiter = rate_limiter
        self.safe_fetch = safe_fetch

    def search_with_operators(self, parsed_query: SearchQuery) -> List[Dict]:
        """
        Execute search with parsed operators.

        Args:
            parsed_query: ParsedQuery object

        Returns:
            List of search results
        """
        results = []

        # Build search query for different engines
        if parsed_query.site:
            results.extend(self._site_search(parsed_query))

        if parsed_query.email:
            results.extend(self._email_search(parsed_query.email))

        if parsed_query.phone:
            results.extend(self._phone_search(parsed_query.phone))

        # General text search
        if parsed_query.text:
            results.extend(self._text_search(parsed_query))

        return results

    def _site_search(self, query: SearchQuery) -> List[Dict]:
        """Search specific site."""
        # Use DuckDuckGo with site: operator
        search_query = f"site:{query.site} {query.text}"

        # Use existing web_search
        from tools.web_search import web_search
        results = web_search(search_query)

        return self._parse_results(results)

    def _email_search(self, email: str) -> List[Dict]:
        """
        Search for email address across sources.

        IMPORTANT: Respects rate limits and robots.txt
        """
        results = []

        # Construct queries
        queries = [
            f'"{email}"',
            f'site:linkedin.com "{email}"',
            f'site:github.com "{email}"',
            f'site:twitter.com "{email}"'
        ]

        for query in queries:
            try:
                # Rate limit
                self.rate_limiter.wait("email_search")

                # Search (respecting robots.txt via safe_fetch)
                result = self._execute_search(query)
                results.extend(result)

            except Exception as e:
                logger.error(f"Email search error: {e}")

        return results

    def _phone_search(self, phone: str) -> List[Dict]:
        """
        Search for phone number.

        Formats phone number in different variations.
        """
        # Normalize phone number
        normalized = re.sub(r'[^\d+]', '', phone)

        # Generate variations
        variations = self._phone_variations(normalized)

        results = []
        for variant in variations:
            try:
                query = f'"{variant}"'
                result = self._execute_search(query)
                results.extend(result)
            except Exception as e:
                logger.error(f"Phone search error: {e}")

        return results

    def _phone_variations(self, phone: str) -> List[str]:
        """Generate phone number format variations."""
        variations = [phone]

        # Remove country code variants
        if phone.startswith('+'):
            variations.append(phone[1:])

        # Add spaces (German format)
        if len(phone) >= 10:
            # +49 123 456789
            variations.append(f"{phone[:3]} {phone[3:6]} {phone[6:]}")
            # 0123 456789
            if phone.startswith('+49'):
                variations.append(f"0{phone[3:]}")

        return list(set(variations))
```

---

## 📧 Feature 2: Email Intelligence

### Capabilities

1. **Email Validation**
   - Syntax check
   - Domain verification
   - MX record lookup
   - Disposable email detection

2. **Email Enrichment**
   - Find associated accounts (GitHub, LinkedIn, etc.)
   - Breach database check (HaveIBeenPwned API)
   - Social media profiles
   - Related domains

3. **Email Pattern Analysis**
   - Company email patterns
   - Common variations
   - Potential aliases

### Implementation

```python
# tools/osint/email_intel.py

import dns.resolver
import re
import requests
from typing import Dict, List, Optional

class EmailIntelligence:
    """Email OSINT capabilities."""

    def __init__(self):
        self.disposable_domains = self._load_disposable_list()

    def analyze_email(self, email: str) -> Dict:
        """
        Comprehensive email analysis.

        Returns:
            {
                'valid': bool,
                'domain': str,
                'mx_records': List[str],
                'disposable': bool,
                'breaches': List[str],
                'social_profiles': Dict,
                'confidence': float
            }
        """
        results = {
            'email': email,
            'valid': self.validate_syntax(email),
            'domain': self.extract_domain(email),
            'mx_records': [],
            'disposable': False,
            'breaches': [],
            'social_profiles': {},
            'confidence': 0.0
        }

        if not results['valid']:
            return results

        # Check MX records
        results['mx_records'] = self.check_mx_records(results['domain'])

        # Check if disposable
        results['disposable'] = self.is_disposable(results['domain'])

        # Check breaches (requires API key)
        results['breaches'] = self.check_breaches(email)

        # Find social profiles
        results['social_profiles'] = self.find_social_profiles(email)

        # Calculate confidence
        results['confidence'] = self._calculate_confidence(results)

        return results

    def validate_syntax(self, email: str) -> bool:
        """Validate email syntax."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def extract_domain(self, email: str) -> str:
        """Extract domain from email."""
        return email.split('@')[1] if '@' in email else ''

    def check_mx_records(self, domain: str) -> List[str]:
        """Check MX records for domain."""
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            return [str(r.exchange) for r in mx_records]
        except Exception as e:
            logger.error(f"MX lookup failed: {e}")
            return []

    def is_disposable(self, domain: str) -> bool:
        """Check if disposable email domain."""
        return domain.lower() in self.disposable_domains

    def check_breaches(self, email: str) -> List[str]:
        """
        Check if email in known breaches.
        Uses HaveIBeenPwned API (requires API key).
        """
        # Placeholder - requires API key
        # https://haveibeenpwned.com/API/v3
        return []

    def find_social_profiles(self, email: str) -> Dict:
        """
        Find social media profiles associated with email.

        Searches public sources only.
        """
        profiles = {}

        # Search GitHub
        profiles['github'] = self._search_github(email)

        # Search LinkedIn (limited public data)
        profiles['linkedin'] = self._search_linkedin(email)

        return profiles

    def generate_variations(self, email: str) -> List[str]:
        """
        Generate potential email variations.

        Example:
            john.doe@company.com ->
            - j.doe@company.com
            - johndoe@company.com
            - john_doe@company.com
        """
        local, domain = email.split('@')
        variations = [email]

        # Remove dots
        variations.append(f"{local.replace('.', '')}@{domain}")

        # Replace dot with underscore
        variations.append(f"{local.replace('.', '_')}@{domain}")

        # First initial + last name
        if '.' in local:
            parts = local.split('.')
            variations.append(f"{parts[0][0]}.{parts[1]}@{domain}")

        return list(set(variations))
```

---

## 📱 Feature 3: Phone Number Intelligence

### Capabilities

1. **Number Validation & Formatting**
2. **Carrier Lookup**
3. **Location Estimation**
4. **Social Media Search**
5. **Reverse Lookup**

### Implementation

```python
# tools/osint/phone_intel.py

import phonenumbers
from phonenumbers import geocoder, carrier
from typing import Dict, Optional

class PhoneIntelligence:
    """Phone number OSINT capabilities."""

    def analyze_phone(self, phone: str, region: str = None) -> Dict:
        """
        Comprehensive phone number analysis.

        Args:
            phone: Phone number (any format)
            region: Country code (e.g., 'DE', 'US')

        Returns:
            {
                'valid': bool,
                'formatted': str,
                'country': str,
                'carrier': str,
                'location': str,
                'type': str,  # mobile/fixed/voip
                'social_profiles': Dict
            }
        """
        results = {
            'input': phone,
            'valid': False,
            'formatted': None,
            'country': None,
            'carrier': None,
            'location': None,
            'type': None,
            'social_profiles': {}
        }

        try:
            # Parse number
            parsed = phonenumbers.parse(phone, region)

            # Validate
            results['valid'] = phonenumbers.is_valid_number(parsed)

            if not results['valid']:
                return results

            # Format
            results['formatted'] = phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )

            # Country
            results['country'] = geocoder.description_for_number(parsed, 'en')

            # Carrier
            results['carrier'] = carrier.name_for_number(parsed, 'en')

            # Number type
            num_type = phonenumbers.number_type(parsed)
            results['type'] = self._type_to_string(num_type)

            # Search social media
            results['social_profiles'] = self._search_social(results['formatted'])

        except Exception as e:
            logger.error(f"Phone analysis error: {e}")

        return results

    def _type_to_string(self, num_type) -> str:
        """Convert number type to string."""
        types = {
            0: 'fixed_line',
            1: 'mobile',
            2: 'fixed_line_or_mobile',
            3: 'toll_free',
            4: 'premium_rate',
            5: 'shared_cost',
            6: 'voip',
            7: 'personal_number',
            8: 'pager',
            9: 'uan',
            10: 'voicemail',
            -1: 'unknown'
        }
        return types.get(num_type, 'unknown')
```

---

## 🤖 Feature 4: AI-Powered OSINT Assistant

### Concept

LLM-gesteuerter OSINT-Assistant der:
1. Queries intelligent interpretiert
2. Beste Suchstrategie vorschlägt
3. Ergebnisse analysiert und korreliert
4. Zusammenhänge erkennt
5. Visualisierungen erstellt

### Implementation

```python
# core/osint/ai_assistant.py

from core.langgraph_agent import MultiHopReasoningAgent
from typing import Dict, List

class OSINTAssistant:
    """AI-powered OSINT research assistant."""

    def __init__(self, config: Dict):
        self.agent = MultiHopReasoningAgent(config, max_hops=5)
        self.query_parser = OSINTQueryParser()
        self.email_intel = EmailIntelligence()
        self.phone_intel = PhoneIntelligence()

    def research(self, objective: str) -> Dict:
        """
        Conduct AI-guided OSINT research.

        Args:
            objective: Research objective

        Example:
            "Find information about john.doe@example.com"
            "Research phone number +49 123 456789"
            "Investigate domain example.com"
        """
        # Step 1: Analyze objective
        research_plan = self._create_research_plan(objective)

        # Step 2: Execute searches
        results = self._execute_research_plan(research_plan)

        # Step 3: Analyze and correlate
        analysis = self._analyze_results(results)

        # Step 4: Generate report
        report = self._generate_report(objective, results, analysis)

        return report

    def _create_research_plan(self, objective: str) -> Dict:
        """Create step-by-step research plan."""
        prompt = f"""Erstelle einen OSINT-Recherche-Plan für:
"{objective}"

Welche Informationen sollen gesucht werden?
Welche Quellen sind relevant?
Welche Suchoperatoren helfen?

Antworte strukturiert:
1. Ziel: ...
2. Zu suchende Informationen: ...
3. Quellen: ...
4. Suchstrategie: ...
"""

        plan_text = self.agent.llm.generate(prompt)

        # Parse plan (simplified)
        return {
            'objective': objective,
            'plan': plan_text,
            'searches': self._extract_searches(plan_text)
        }
```

---

## 🎨 Feature 5: Relationship Mapping & Visualization

### Concept

Visualisierung von Zusammenhängen zwischen:
- Personen
- Emails
- Domains
- Telefonnummern
- Social Media Accounts

### Tools

- **NetworkX** für Graph-Analyse
- **Graphviz** für Visualisierung
- **D3.js** für interaktive Web-Visualisierung

---

## 📋 Implementation Roadmap

### Phase 5.1: Foundation (v1.2.0)
**Dauer:** 2-3 Wochen

- [ ] Query Parser Implementation
- [ ] Basic Search Operators (site:, inurl:, intext:)
- [ ] Email Intelligence Module
- [ ] Phone Intelligence Module
- [ ] Rate Limiting & Compliance
- [ ] Documentation & Terms of Use

### Phase 5.2: AI Integration (v1.2.1)
**Dauer:** 2 Wochen

- [ ] AI Query Enhancement
- [ ] OSINT Assistant
- [ ] Multi-Source Aggregation
- [ ] Result Correlation
- [ ] Confidence Scoring

### Phase 5.3: Advanced Features (v1.2.2)
**Dauer:** 3 Wochen

- [ ] Relationship Mapping
- [ ] Graph Visualization
- [ ] Social Media Intelligence
- [ ] Breach Database Integration
- [ ] Advanced Analytics

### Phase 5.4: Production (v1.2.3)
**Dauer:** 1 Woche

- [ ] Performance Optimization
- [ ] API Rate Limiting
- [ ] Audit Logging
- [ ] Compliance Checks
- [ ] User Management

---

## 🛡️ Security & Compliance

### Privacy Protection

```python
# core/osint/compliance.py

class OSINTCompliance:
    """Ensure OSINT operations comply with laws."""

    def check_query(self, query: str, user_id: str) -> bool:
        """
        Check if query is compliant.

        Logs all OSINT queries for audit.
        """
        # Log query
        self._log_query(query, user_id)

        # Check against blacklist
        if self._is_blacklisted(query):
            logger.warning(f"Blacklisted query from {user_id}")
            return False

        # Rate limit per user
        if self._exceeds_rate_limit(user_id):
            logger.warning(f"Rate limit exceeded: {user_id}")
            return False

        return True
```

### Terms of Use

```markdown
# OSINT Terms of Use

1. Only for legitimate purposes
2. Respect privacy laws (GDPR, CCPA, etc.)
3. No harassment or stalking
4. Rate limits enforced
5. All actions logged
6. Violations result in ban
```

---

## 📊 Success Metrics

### KPIs für OSINT-Features

- **Search Precision:** >80% relevante Ergebnisse
- **Response Time:** <5s für einfache Queries
- **API Rate Limit:** 100 req/hour/user
- **User Satisfaction:** >4.5/5 stars

---

## 🔮 Long-Term Vision (v2.0+)

- 🌐 **Dark Web Monitoring** (Tor integration)
- 🤖 **Automated Threat Intelligence**
- 📊 **Real-time Alerts**
- 🔗 **Blockchain Analysis**
- 🎯 **Predictive Analytics**
- 🗺️ **Geospatial Intelligence**

---

**Status:** Draft - Feedback Welcome!
**Contact:** GitHub Issues oder Discussions
