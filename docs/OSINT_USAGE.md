# OSINT Features - Quick Guide

**Version:** 1.2.0 | **Last Updated:** 2025-01-24

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Optional: Install phonenumbers for phone intelligence
pip install phonenumbers

# 3. Run CrawlLama
python main.py

# 4. Accept OSINT Terms (first time only)
# Type "accept" when prompted
```

### Ready to Use!

```bash
# Search email (validates + web search)
email:john.doe@company.com

# Search phone (validates + web search)
phone:"+49 151 12345678"

# Use search operators
site:github.com python machine learning
```

---

## 🔎 Search Operators Reference

| Operator | Purpose | Example |
|----------|---------|---------|
| `site:` | Search specific domain | `site:github.com python` |
| `inurl:` | Text in URL | `inurl:profile "software engineer"` |
| `intext:` | Text in page content | `intext:"contact email"` |
| `intitle:` | Text in page title | `intitle:"about us"` |
| `filetype:` | Specific file type | `filetype:pdf "annual report"` |
| `-` | Exclude term | `python -java` |
| `OR` | Either term | `site:linkedin.com OR site:xing.de` |

### Quick Examples

```bash
# Find LinkedIn profile
site:linkedin.com "John Doe" inurl:profile

# Find PDFs on company site
site:example.com filetype:pdf

# Complex search
site:github.com intext:"machine learning" -tensorflow

# Multiple domains
"developer" site:linkedin.com OR site:github.com
```

---

## 📧 Email Intelligence

### What It Does

✅ **Validates** email syntax, domain, MX records
✅ **Detects** disposable emails
✅ **Searches** LinkedIn, GitHub, Twitter, Facebook
✅ **Generates** email variations
✅ **Shows** up to 10 unique results

### Usage

```bash
# Simple email search (validates + web search)
email:john.doe@company.com

# Combine with operators
email:developer@example.com site:github.com
```

### Example Output

```
Email Intelligence for: john.doe@company.com

✓ Valid: True
  Domain: company.com
  Username: john.doe
  MX Records: mail.company.com (DNS verified)
  Disposable: False
  Confidence: 0.95

Variations:
  • john.doe@company.com
  • j.doe@company.com
  • johndoe@company.com

Web Search Results (10 found):
  1. [LinkedIn] John Doe - Software Engineer at Company
  2. [GitHub] johndoe - 42 repositories
  3. [Twitter] @johndoe - Developer profile
  ...
```

### Python API

```python
from core.osint import EmailIntelligence

intel = EmailIntelligence()
result = intel.analyze_email('test@example.com')

print(f"Valid: {result['valid']}")
print(f"Domain: {result['domain']}")
print(f"Disposable: {result['disposable']}")
print(f"Confidence: {result['confidence']}")
print(f"Variations: {result['variations']}")
```

---

## 📱 Phone Intelligence

### What It Does

✅ **Validates** phone number format
✅ **Identifies** country, region, carrier
✅ **Searches** web with format variations
✅ **Detects** mobile vs landline
✅ **Shows** up to 10 unique results

**Note:** Install `phonenumbers` for full features: `pip install phonenumbers`

### Usage

```bash
# International format
phone:"+49 151 12345678"

# Local format
phone:"0151 12345678"

# US number
phone:"+1 555 123 4567"
```

### Example Output

```
Phone Intelligence for: +49 151 12345678

✓ Valid: True
  Formatted: +49 151 12345678
  Country: Germany (DE)
  Type: mobile
  Carrier: Vodafone Germany
  Confidence: 1.00

Format Variations:
  • +49 151 12345678
  • 0151 12345678
  • +4915112345678

Web Search Results (5 found):
  1. Business listing for +49 151 12345678
  2. Contact page with 0151 12345678
  ...
```

### Python API

```python
from core.osint import PhoneIntelligence

intel = PhoneIntelligence()
result = intel.analyze_phone('+49 151 12345678', region='DE')

print(f"Valid: {result['valid']}")
print(f"Formatted: {result['formatted']}")
print(f"Country: {result['country']}")
print(f"Type: {result['type']}")
print(f"Carrier: {result['carrier']}")
print(f"Variations: {result['variations']}")
```

---

## 🤖 AI Query Enhancement

**Requires:** Ollama running (`ollama serve`)

### Features

| Feature | Description | Example |
|---------|-------------|---------|
| **Query Variations** | Generate alternative queries | "security researcher" → "cybersecurity expert", "infosec specialist" |
| **Operator Suggestions** | AI suggests best operators | "find LinkedIn profile" → `site:linkedin.com inurl:profile` |
| **Entity Detection** | Identify query type | "test@example.com" → email |
| **Source Suggestions** | Suggest relevant platforms | "developer" → github.com, stackoverflow.com |

### Python API

```python
from core.osint import QueryEnhancer
from core.llm_client import OllamaClient

llm = OllamaClient()
enhancer = QueryEnhancer(llm)

# Generate query variations
variations = enhancer.generate_variations("security researcher")
# → ["cybersecurity expert", "infosec specialist", "security analyst"]

# Suggest operators
operators = enhancer.suggest_operators("find John Doe on LinkedIn")
# → {"site": "linkedin.com", "inurl": "profile", "intext": "John Doe"}

# Detect entity type
entity_type = enhancer.identify_entity_type("test@example.com")
# → "email"

# Suggest sources
sources = enhancer.suggest_sources("developer", "person")
# → ["github.com", "linkedin.com", "stackoverflow.com"]
```

---

## 💡 Practical Examples

### 🔍 Person Research

```bash
# Basic search
John Doe

# LinkedIn + GitHub
site:linkedin.com "John Doe" inurl:profile
site:github.com "John Doe"

# If you find email
email:john.doe@company.com
```

### 🏢 Company Research

```bash
# Company overview
site:example.com

# Find contacts and documents
site:example.com intext:"contact" OR inurl:contact
site:example.com filetype:pdf
site:linkedin.com "Example Corp"
```

### 📧 Email Investigation

```bash
# Validate and search (automatic web search)
email:suspect@example.com

# Platform-specific
email:suspect@example.com site:linkedin.com
email:suspect@example.com site:github.com
```

### 📱 Phone Investigation

```bash
# Validate and search (automatic web search)
phone:"+49 151 12345678"

# Additional searches
"+49 151 12345678"
"0151 12345678"
```

### 🌐 Domain Research

```bash
# Site overview and subdomains
site:example.com
site:*.example.com

# Find emails and documents
site:example.com intext:"@example.com"
site:example.com filetype:pdf OR filetype:doc
```

---

## ⚖️ Compliance & Limits

### Rate Limits (Per Hour)

| Query Type | Limit |
|------------|-------|
| Email searches | 50 |
| Phone searches | 50 |
| General OSINT | 100 |

**Increase limits:** Edit `config.json` → `osint.rate_limits`

### Prohibited Terms

Queries with these terms are blocked:
- `password`, `hack`, `crack`, `exploit`
- `stalk`, `spy`, `surveillance`

### Check Usage

```python
from core.osint import OSINTCompliance

compliance = OSINTCompliance()
stats = compliance.get_usage_stats("user_id")

print(f"Total requests: {stats['total_requests_last_hour']}")
print(f"Remaining: {stats['remaining_limits']}")
```

### Audit Logs

All queries logged in: `data/osint_logs/`

---

## 🔧 Troubleshooting

| Issue | Solution |
|-------|----------|
| **Terms not accepted** | Run `python main.py` and type `accept` |
| **Rate limit exceeded** | Wait 1 hour or increase limits in `config.json` |
| **Phone intelligence basic** | Run `pip install phonenumbers` |
| **Ollama not running** | Run `ollama serve` (for AI features) |
| **Prohibited content** | Remove blacklisted terms (hack, password, stalk, etc.) |

### Increase Rate Limits

Edit `config.json`:

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

---

## 📚 Resources

- **Test Suite:** `python test_osint.py`
- **Module Docs:** [core/osint/README.md](../core/osint/README.md)
- **Future Plans:** [FUTURE_PLANS.md](./FUTURE_PLANS.md)

---

## 🎯 All Features Summary

| Feature | Operator | Web Search | Validation | AI Enhancement |
|---------|----------|------------|------------|----------------|
| **Email Intelligence** | `email:` | ✅ LinkedIn, GitHub, Twitter, Facebook | ✅ Syntax, MX, Disposable | ✅ Variations |
| **Phone Intelligence** | `phone:` | ✅ Format variations | ✅ Country, Carrier, Type | ✅ Formats |
| **Search Operators** | `site:`, `inurl:`, etc. | ✅ DuckDuckGo | N/A | ✅ Suggestions |
| **Query Enhancement** | N/A | N/A | N/A | ✅ Variations, Entity Detection |

---

**Remember:** Use OSINT features responsibly and ethically! 🛡️
