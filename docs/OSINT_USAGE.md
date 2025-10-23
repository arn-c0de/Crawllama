# OSINT Features - Usage Guide

**Version:** 1.2.0
**Last Updated:** 2025-01-24

---

## 📖 Table of Contents

1. [Getting Started](#getting-started)
2. [Advanced Search Operators](#advanced-search-operators)
3. [Email Intelligence](#email-intelligence)
4. [Phone Intelligence](#phone-intelligence)
5. [AI Query Enhancement](#ai-query-enhancement)
6. [Practical Examples](#practical-examples)
7. [Compliance & Terms](#compliance--terms)
8. [Troubleshooting](#troubleshooting)

---

## 🚀 Getting Started

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Optional: Install phonenumbers for advanced phone intelligence
pip install phonenumbers

# Test OSINT features
python test_osint.py
```

### First Time Setup

When you use OSINT features for the first time, you'll need to accept the terms:

```bash
python main.py
```

You'll see the OSINT Terms of Use. Type `accept` to continue.

---

## 🔎 Advanced Search Operators

### Basic Operators

#### `site:` - Search Specific Domain

```bash
# Find Python projects on GitHub
site:github.com python

# Search LinkedIn profiles
site:linkedin.com "John Doe"

# Search company website
site:example.com contact
```

#### `inurl:` - Text in URL

```bash
# Find admin pages
site:example.com inurl:admin

# Find profile pages
inurl:profile "software engineer"

# Find documentation
inurl:docs api
```

#### `intext:` - Text in Page Content

```bash
# Find pages containing specific text
intext:"contact email"

# Find phone numbers in content
intext:"phone" site:example.com

# Find specific information
intext:"CEO" intext:"contact"
```

#### `intitle:` - Text in Page Title

```bash
# Find specific page titles
intitle:"about us"

# Find directory listings
intitle:"index of"

# Find specific documents
intitle:"resume" filetype:pdf
```

#### `filetype:` - File Type

```bash
# Find PDF documents
filetype:pdf "annual report"

# Find Word documents
site:company.com filetype:doc

# Find presentations
filetype:ppt "company overview"
```

#### `-` - Exclude Term

```bash
# Exclude specific term
python -java

# Exclude domain
"John Doe" -site:facebook.com

# Multiple exclusions
programming -java -php -ruby
```

### Combined Operators

```bash
# Complex search
site:linkedin.com inurl:profile intext:"software engineer" intext:"berlin"

# Document search
site:example.com filetype:pdf intext:"confidential" -intext:"public"

# Contact search
site:company.com intext:"contact" OR intext:"email" OR intext:"phone"
```

---

## 📧 Email Intelligence

### Basic Email Analysis

```bash
# In CrawlLama
email:test@example.com
```

**Output:**
```
Email Intelligence for: test@example.com

Valid: ✓ True
Domain: example.com
Username: test
MX Records: ['example.com (DNS verified)']
Disposable: False
Confidence: 0.90

Email Variations:
  • test@example.com
  • test_example.com
  • t.est@example.com
```

### Email + Search Combination

```bash
# Find LinkedIn profile
email:john.doe@company.com site:linkedin.com

# Find GitHub activity
email:developer@example.com site:github.com

# Find professional profiles
email:max.mustermann@firma.de site:xing.de OR site:linkedin.com
```

### Programmatic Usage

```python
from core.osint import EmailIntelligence

intel = EmailIntelligence()

# Analyze email
result = intel.analyze_email('test@example.com')

print(f"Valid: {result['valid']}")
print(f"Domain: {result['domain']}")
print(f"Disposable: {result['disposable']}")
print(f"Confidence: {result['confidence']}")

# Generate variations
print("Variations:")
for var in result['variations']:
    print(f"  • {var}")

# Check if domain accepts mail
if result['mx_records']:
    print("Domain has valid MX records")
```

### Email Pattern Analysis

```python
# Find company email pattern
emails = [
    'john.doe@company.com',
    'jane.smith@company.com',
    'bob.wilson@company.com'
]

pattern = intel.find_company_pattern(emails)
print(f"Pattern: {pattern}")
# Output: {first}.{last}@company.com
```

---

## 📱 Phone Intelligence

### Basic Phone Analysis

```bash
# International format
phone:"+49 151 12345678"

# Local format (with region hint)
phone:"0151 12345678"

# US number
phone:"+1 555 123 4567"
```

**Output:**
```
Phone Intelligence for: +49 151 12345678

Valid: ✓ True
Formatted: +49 151 12345678
Country: Germany
Region: DE
Carrier: Vodafone Germany (example)
Type: mobile
Confidence: 1.00

Format Variations:
  • +49 151 12345678
  • 0151 12345678
  • +49 15112345678
  • 0151 12345678
```

### Phone + Search Combination

```bash
# Find business listings
phone:"+49 30 12345678" site:google.com

# Find on social media
phone:"+1 555 123 4567" site:facebook.com OR site:linkedin.com
```

### Programmatic Usage

```python
from core.osint import PhoneIntelligence

intel = PhoneIntelligence()

# Analyze phone number
result = intel.analyze_phone('+49 151 12345678', region='DE')

print(f"Valid: {result['valid']}")
print(f"Formatted: {result['formatted']}")
print(f"Country: {result['country']}")
print(f"Type: {result['type']}")
print(f"Carrier: {result['carrier']}")

# Get format variations
print("Variations:")
for var in result['variations']:
    print(f"  • {var}")
```

**Note:** Full phone intelligence requires `phonenumbers` library:
```bash
pip install phonenumbers
```

---

## 🤖 AI Query Enhancement

### Query Variations

Generate alternative search queries:

```python
from core.osint import QueryEnhancer
from core.llm_client import OllamaClient

llm = OllamaClient()
enhancer = QueryEnhancer(llm)

# Generate variations
variations = enhancer.generate_variations("Max Mustermann security researcher")

print("Query Variations:")
for var in variations:
    print(f"  • {var}")
```

**Output:**
```
Query Variations:
  • Max Mustermann cybersecurity
  • Max Mustermann infosec
  • Max Mustermann penetration tester
  • Max Mustermann IT security
  • Mustermann security consultant
```

### Operator Suggestions

Get AI-suggested operators:

```python
# Suggest operators
operators = enhancer.suggest_operators("find John Doe LinkedIn profile")

print("Suggested Operators:")
for op, val in operators.items():
    print(f"  • {op}: {val}")
```

**Output:**
```
Suggested Operators:
  • site: linkedin.com
  • inurl: profile
  • intext: "John Doe"
```

### Entity Type Detection

```python
# Detect what type of entity
entity_type = enhancer.identify_entity_type("test@example.com")
print(f"Entity Type: {entity_type}")
# Output: email

entity_type = enhancer.identify_entity_type("Max Mustermann")
print(f"Entity Type: {entity_type}")
# Output: person
```

### Source Suggestions

```python
# Suggest relevant sources
sources = enhancer.suggest_sources("Max Mustermann developer", "person")

print("Suggested Sources:")
for source in sources:
    print(f"  • {source}")
```

**Output:**
```
Suggested Sources:
  • linkedin.com
  • github.com
  • xing.de
  • stackoverflow.com
  • twitter.com
```

---

## 💡 Practical Examples

### Example 1: Person Research

**Goal:** Find information about "John Doe"

```bash
# Step 1: Basic search
John Doe

# Step 2: LinkedIn profile
site:linkedin.com "John Doe" inurl:profile

# Step 3: GitHub activity
site:github.com "John Doe"

# Step 4: Find email
site:linkedin.com "John Doe" intext:"email"

# Step 5: If you found email, analyze it
email:john.doe@company.com
```

### Example 2: Company Research

**Goal:** Research "Example Corp"

```bash
# Step 1: Official website
site:example.com

# Step 2: Find contact page
site:example.com intext:"contact" OR inurl:contact

# Step 3: Find employees on LinkedIn
site:linkedin.com "Example Corp"

# Step 4: Find documents
site:example.com filetype:pdf

# Step 5: Find press releases
site:example.com inurl:press OR inurl:news
```

### Example 3: Email Investigation

**Goal:** Investigate "suspect@example.com"

```bash
# Step 1: Validate email
email:suspect@example.com

# Step 2: Search LinkedIn
email:suspect@example.com site:linkedin.com

# Step 3: Search GitHub
email:suspect@example.com site:github.com

# Step 4: General search
"suspect@example.com"

# Step 5: Find related domains
site:example.com -inurl:suspect
```

### Example 4: Phone Number Investigation

**Goal:** Investigate phone number

```bash
# Step 1: Validate and get info
phone:"+49 151 12345678"

# Step 2: Search online
"+49 151 12345678"

# Step 3: Search business directories
phone:"+49 151 12345678" site:gelbeseiten.de

# Step 4: Try variations
"0151 12345678"
```

### Example 5: Domain Research

**Goal:** Research domain "example.com"

```bash
# Step 1: Site overview
site:example.com

# Step 2: Find subdomains
site:*.example.com

# Step 3: Find emails
site:example.com intext:"@example.com"

# Step 4: Find documents
site:example.com filetype:pdf OR filetype:doc

# Step 5: Find contact info
site:example.com intext:"contact" intext:"phone" intext:"email"
```

---

## ⚖️ Compliance & Terms

### Rate Limits

**Per Hour Limits:**
- Email searches: 50
- Phone searches: 50
- General OSINT: 100

Check your current usage:

```python
from core.osint import OSINTCompliance

compliance = OSINTCompliance()
stats = compliance.get_usage_stats("your_user_id")

print(f"Total requests: {stats['total_requests_last_hour']}")
print(f"Remaining limits:")
for qtype, remaining in stats['remaining_limits'].items():
    print(f"  • {qtype}: {remaining}")
```

### Blacklisted Terms

Queries containing these terms are automatically blocked:
- `password`, `hack`, `crack`, `exploit`
- `stalk`, `spy`, `surveillance`

### Audit Logs

All OSINT queries are logged in: `data/osint_logs/`

```json
{
  "timestamp": "2025-01-24T10:30:00",
  "user_id": "user123",
  "query": "email:test@example.com",
  "query_type": "email_search",
  "status": "approved"
}
```

### Accepting Terms

First time usage:

```python
from core.osint import OSINTCompliance

compliance = OSINTCompliance()

# Check if terms accepted
if not compliance.check_terms_accepted("your_user_id"):
    print(compliance.display_terms())
    # User accepts
    compliance.accept_terms("your_user_id")
```

---

## 🔧 Troubleshooting

### Issue: "Terms not accepted"

**Solution:**
```python
from core.osint import OSINTCompliance
compliance = OSINTCompliance()
compliance.accept_terms("default")
```

### Issue: "Rate limit exceeded"

**Solution:**
- Wait 1 hour for limits to reset
- Or increase limits in `config.json`:

```json
{
  "osint": {
    "rate_limits": {
      "email_search": 100,
      "phone_search": 100,
      "general_osint": 200
    }
  }
}
```

### Issue: "Phone intelligence basic only"

**Solution:**
```bash
pip install phonenumbers
```

### Issue: "Ollama not running" (AI features)

**Solution:**
```bash
ollama serve
```

### Issue: "Query contains prohibited content"

**Solution:**
- Remove blacklisted terms (password, hack, stalk, etc.)
- Rephrase query to focus on legitimate research

---

## 📚 Additional Resources

- [OSINT Module README](../core/osint/README.md)
- [Future Plans](./FUTURE_PLANS.md)
- [Test Script](../test_osint.py)

---

**Remember:** Use OSINT features responsibly and ethically! 🛡️
