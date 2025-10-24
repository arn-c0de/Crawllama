# OSINT Module for CrawlLama

**Version:** 1.2.0
**Status:** Production Ready
**Last Updated:** 2025-01-24

---

## 🎯 Overview

The OSINT (Open Source Intelligence) module provides advanced search capabilities, email/phone intelligence, and AI-powered query enhancement for investigative research.

## ⚖️ Legal & Ethical Use Only

**IMPORTANT:** OSINT features are provided exclusively for legitimate purposes:

✅ **Permitted Use:**
- Security research and threat intelligence
- Investigative journalism
- Compliance and due diligence
- Academic research
- Legal investigations with proper authorization

❌ **Prohibited Use:**
- Stalking or harassment
- Identity theft or fraud
- Unauthorized surveillance
- Privacy violations
- Any illegal activities

**All OSINT queries are logged for compliance and audit purposes.**

---

## 🔍 Features

### 1. Advanced Search Operators

Parse and execute advanced search queries:

```python
from core.osint import OSINTQueryParser

parser = OSINTQueryParser()
query = parser.parse('site:github.com inurl:python filetype:md')

print(query.site)      # 'github.com'
print(query.inurl)     # 'python'
print(query.filetype)  # 'md'
```

**Supported Operators:**
- `site:` - Search specific domain
- `inurl:` - Text in URL
- `intext:` - Text in page content
- `intitle:` - Text in page title
- `filetype:` - File type (pdf, doc, etc.)
- `email:` - Search for email address
- `phone:` - Search for phone number
- `-` - Exclude term

### 2. Email Intelligence

Comprehensive email analysis:

```python
from core.osint import EmailIntelligence

email_intel = EmailIntelligence()
result = email_intel.analyze_email('test@example.com')

print(result['valid'])          # True/False
print(result['domain'])         # 'example.com'
print(result['mx_records'])     # List of MX records
print(result['disposable'])     # True if disposable email
print(result['variations'])     # Email variations
print(result['confidence'])     # Confidence score (0.0-1.0)
```

**Capabilities:**
- Syntax validation
- Domain verification
- MX record lookup
- Disposable email detection
- Email variations generation
- Pattern analysis

### 3. Phone Intelligence

Phone number analysis and validation:

```python
from core.osint import PhoneIntelligence

phone_intel = PhoneIntelligence()
result = phone_intel.analyze_phone('+49 151 12345678', region='DE')

print(result['valid'])         # True/False
print(result['formatted'])     # '+49 151 12345678'
print(result['country'])       # 'Germany'
print(result['carrier'])       # Carrier name (if available)
print(result['type'])          # 'mobile', 'fixed_line', etc.
print(result['variations'])    # Format variations
```

**Capabilities:**
- Number validation
- International formatting
- Country/region detection
- Carrier lookup (with phonenumbers library)
- Number type identification (mobile, fixed, VoIP)
- Format variations

**Note:** Full phone intelligence requires `phonenumbers` library:
```bash
pip install phonenumbers
```

### 4. AI Query Enhancement

LLM-powered query optimization:

```python
from core.osint import QueryEnhancer
from core.llm_client import OllamaClient

llm = OllamaClient()
enhancer = QueryEnhancer(llm)

# Generate query variations
variations = enhancer.generate_variations("John Doe security researcher")
# Output: ["John Doe cybersecurity", "John Doe infosec", ...]

# Suggest operators
operators = enhancer.suggest_operators("find John Doe LinkedIn")
# Output: {'site': 'linkedin.com', 'inurl': 'profile'}

# Identify entity type
entity_type = enhancer.identify_entity_type("test@example.com")
# Output: 'email'

# Suggest sources
sources = enhancer.suggest_sources("Max Mustermann developer", "person")
# Output: ['linkedin.com', 'github.com', 'xing.de', ...]
```

### 5. Social Media Intelligence

Comprehensive social media profile analysis and discovery:

```python
from core.osint import SocialIntelligence

social = SocialIntelligence()

# Analyze username across platforms
result = await social.analyze_username("john_doe")

print(f"Found on {result['summary']['platforms_with_presence']} platforms")
print(f"Confidence: {result['summary']['confidence_score']:.1f}%")

# Generate detailed report
report = social.generate_social_report(result)
print(report)

# Discover profiles by email
email_result = await social.discover_profiles_by_email("john@example.com")
print(f"Email-based matches: {len(email_result['username_matches'])}")
```

**Supported Platforms:**
- Twitter, Instagram, LinkedIn, Facebook
- GitHub, Reddit, YouTube, TikTok

**Features:**
- Multi-platform username validation
- Profile existence verification
- Username variation detection
- Risk assessment and reporting
- Email-to-profile correlation

### 6. Compliance & Rate Limiting

Built-in compliance checks and rate limiting:

```python
from core.osint import OSINTCompliance

compliance = OSINTCompliance()

# Check if user accepted terms
if not compliance.check_terms_accepted("user123"):
    print(compliance.display_terms())

# Accept terms
compliance.accept_terms("user123")

# Check query compliance
allowed, reason = compliance.check_query(
    query="email:test@example.com",
    user_id="user123",
    query_type="email_search"
)

if not allowed:
    print(f"Query blocked: {reason}")

# Get usage stats
stats = compliance.get_usage_stats("user123")
print(f"Requests this hour: {stats['total_requests_last_hour']}")
print(f"Remaining limits: {stats['remaining_limits']}")
```

**Rate Limits (per hour):**
- Email searches: 50
- Phone searches: 50
- Social Intelligence: 30
- General OSINT: 100

---

## 🚀 Quick Start

### Using OSINT Tool (Unified Interface)

```python
from tools.osint_tool import OSINTTool
from core.llm_client import OllamaClient

# Initialize
llm = OllamaClient()
osint = OSINTTool(llm, config)

# Accept terms (first time)
if not osint.check_terms():
    osint.accept_terms()

# Process OSINT query
result = osint.process_query("email:test@example.com site:linkedin.com")

print(result['query_type'])         # 'email_intelligence'
print(result['intelligence'])       # Email analysis results
print(result['suggestions'])        # AI suggestions
```

### Using in CrawlLama Main

```python
# In main.py or interactive mode
query = "email:max.mustermann@example.com"

# The agent will automatically detect OSINT operators
response = agent.query(query)
```

**Example Queries:**

```bash
# Email intelligence
email:test@example.com

# Phone intelligence
phone:"+49 151 12345678"

# Social media username search
social:john_doe

# Advanced search
site:github.com inurl:python "machine learning"

# Combined searches
email:john@example.com site:linkedin.com inurl:profile
social:john_doe platforms:twitter,github,instagram
```

---

## 📁 Module Structure

```
core/osint/
├── __init__.py              # Module exports
├── query_parser.py          # Advanced operator parsing
├── email_intel.py           # Email intelligence
├── phone_intel.py           # Phone intelligence
├── social_intel.py          # Social media intelligence
├── query_enhancer.py        # AI query enhancement
├── compliance.py            # Compliance & rate limiting
└── README.md                # This file

tools/
└── osint_tool.py            # Unified OSINT tool for agent

data/osint_logs/             # Audit logs (auto-created)
├── osint_queries_YYYY-MM.jsonl
├── violations.jsonl
└── terms_accepted.json
```

---

## 🔧 Configuration

Add to `config.json`:

```json
{
  "osint": {
    "enabled": true,
    "log_queries": true,
    "rate_limits": {
      "email_search": 50,
      "phone_search": 50,
      "general_osint": 100
    }
  }
}
```

---

## 📝 Examples

### Example 1: Email OSINT

```python
from core.osint import EmailIntelligence

intel = EmailIntelligence()

# Analyze email
result = intel.analyze_email("john.doe@company.com")

if result['valid']:
    print(f"Domain: {result['domain']}")
    print(f"Disposable: {result['disposable']}")
    print(f"MX Records: {result['mx_records']}")

    # Generate variations
    print("Possible variations:")
    for var in result['variations']:
        print(f"  • {var}")
```

### Example 2: Phone OSINT

```python
from core.osint import PhoneIntelligence

intel = PhoneIntelligence()

# Analyze German phone number
result = intel.analyze_phone("+49 151 12345678", region="DE")

if result['valid']:
    print(f"Formatted: {result['formatted']}")
    print(f"Country: {result['country']}")
    print(f"Type: {result['type']}")
    print(f"Carrier: {result['carrier']}")
```

### Example 3: Social Media Intelligence

```python
import asyncio
from core.osint import SocialIntelligence

async def social_analysis_example():
    social = SocialIntelligence()
    
    # Username analysis across platforms
    result = await social.analyze_username("john_doe", 
                                          platforms=["twitter", "github", "instagram"])
    
    print(f"Analysis Results:")
    print(f"├─ Platforms found: {result['summary']['platforms_with_presence']}")
    print(f"├─ Confidence: {result['summary']['confidence_score']:.1f}%")
    print(f"└─ Risk level: {'HIGH' if len(result['summary']['risk_indicators']) > 2 else 'LOW'}")
    
    # Show found profiles
    for profile in result['platforms_found']:
        verified = "✓" if profile['profile_data'].get('verified') else ""
        print(f"  🔗 {profile['platform']}: {profile['url']} {verified}")

# Run the analysis
asyncio.run(social_analysis_example())
```

### Example 4: AI-Enhanced Search

```python
from core.osint import QueryEnhancer, OSINTQueryParser
from core.llm_client import OllamaClient

llm = OllamaClient()
enhancer = QueryEnhancer(llm)
parser = OSINTQueryParser()

# Original query
query = "Max Mustermann security"

# Get AI suggestions
variations = enhancer.generate_variations(query)
operators = enhancer.suggest_operators(query)

# Build enhanced query
enhanced = f"{query} {' '.join([f'{op}:{val}' for op, val in operators.items()])}"
print(f"Enhanced: {enhanced}")

# Parse and execute
parsed = parser.parse(enhanced)
```

---

## 🛡️ Privacy & Security

### Data Protection

- **No Persistent Storage:** Search queries are logged for audit only
- **Encryption:** Sensitive data encrypted at rest
- **Rate Limiting:** Prevents abuse
- **Access Control:** Terms acceptance required
- **Audit Trail:** All operations logged with timestamps

### GDPR Compliance

The OSINT module is designed with privacy laws in mind:

1. **Purpose Limitation:** Only for legitimate purposes
2. **Data Minimization:** Minimal data collection
3. **Transparency:** Clear terms of use
4. **User Rights:** Audit logs accessible
5. **Security:** Encrypted storage and transmission

### Blacklisted Queries

Queries containing these terms are automatically blocked:
- `password`, `hack`, `crack`, `exploit`
- `stalk`, `spy`, `surveillance`
- Other privacy-invasive terms

---

## 📊 Audit Logs

All OSINT operations are logged:

```json
{
  "timestamp": "2025-01-24T10:30:00",
  "user_id": "user123",
  "query": "email:test@example.com",
  "query_type": "email_search",
  "status": "approved"
}
```

Logs are stored in: `data/osint_logs/osint_queries_YYYY-MM.jsonl`

---

## 🧪 Testing

```bash
# Run OSINT tests
pytest tests/test_osint.py -v

# Test specific module
pytest tests/test_email_intel.py -v
```

---

## 📦 Dependencies

```bash
# Core (required)
pip install requests beautifulsoup4

# Phone intelligence (optional but recommended)
pip install phonenumbers

# Full installation
pip install -r requirements.txt
```

---

## 🔮 Future Enhancements (v1.3+)

- [ ] HaveIBeenPwned API integration
- [x] Social media profile discovery (✅ Added in v1.2)
- [ ] Advanced social graph visualization
- [ ] Breach database search
- [ ] Darknet monitoring integration
- [ ] Real-time social media monitoring
- [ ] ML-based fake account detection
- [ ] Export to report formats (PDF, JSON)

---

## 📚 Resources

- [OSINT Framework](https://osintframework.com/)
- [OSINT Techniques](https://inteltechniques.com/)
- [GDPR Compliance](https://gdpr.eu/)
- [Ethical OSINT Guide](https://www.osintme.com/)

---

## ❓ FAQ

**Q: Do I need API keys?**
A: No API keys required for basic features. Optional integrations (HaveIBeenPwned, etc.) require keys.

**Q: Is phone intelligence library required?**
A: No, but `phonenumbers` library provides advanced features (carrier, type detection).

**Q: Are queries stored permanently?**
A: Only audit logs are stored (timestamp, user_id, query type). No sensitive data persisted.

**Q: What if I exceed rate limits?**
A: Wait 1 hour or increase limits in `config.json` (use responsibly).

**Q: Can I use this for commercial purposes?**
A: Yes, but ensure compliance with local laws and terms of service of searched platforms.

---

## 📧 Support

- GitHub Issues: [Report bugs or request features](https://github.com/your-repo/issues)
- Discussions: [Ask questions](https://github.com/your-repo/discussions)

---

**Remember:** With great power comes great responsibility. Use OSINT ethically! 🛡️
