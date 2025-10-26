# OSINT Features - Quick Guide

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🚀 Quickstart](../getting-started/QUICKSTART.md) | [🧠 LangGraph](../guides/LANGGRAPH_GUIDE.md) | [🏥 Health](../health/HEALTH_MONITORING.md)

---

**Version:** 1.4.1 | **Last Updated:** 2025-10-26

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Optional: Install additional packages for full features
pip install phonenumbers aiohttp beautifulsoup4

# 3. Run CrawlLama
python main.py

# 4. Accept OSINT Terms (first time only)
# Type "accept" when prompted
```

### Ready to Use! (5 Intelligence Types)

```bash
# Email Intelligence - validates + web search
email:john.doe@company.com

# Phone Intelligence - validates + web search  
phone:"+49 151 12345678"

# IP Intelligence (NEW!) - comprehensive IP analysis
ip:8.8.8.8
192.168.1.1  # Auto-detects as IP

# Social Intelligence (NEW!) - 12 platforms
username:elonmusk
@microsoft
github  # Auto-detects as username

# Advanced search operators
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
| `email:` | Email intelligence | `email:test@example.com` |
| `phone:` | Phone intelligence | `phone:"+49151234567"` |
| `ip:` | IP intelligence | `ip:8.8.8.8` |
| `username:` | Social intelligence | `username:elonmusk` |
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

## 🌐 IP Intelligence (NEW!)

### What It Does

✅ **Validates** IPv4/IPv6 addresses and determines type (public/private/reserved)
✅ **Geolocation** using multiple free services (no API keys required)
✅ **ISP & Organization** identification from multiple sources
✅ **Security Analysis** including reputation scoring and VPN/proxy detection
✅ **Network Info** including reverse DNS, WHOIS, and routing information
✅ **Privacy-Compliant** - no external API dependencies

### Usage

```bash
# Direct IP analysis
ip:8.8.8.8

# Auto-detection (no operator needed)
192.168.1.1
2001:4860:4860::8888

# IPv6 addresses
ip:2001:4860:4860::8888

# Combine with search operators
ip:1.1.1.1 site:cloudflare.com
```

### Example Output

```
🔍 IP Intelligence Report: 8.8.8.8
==================================================
IP Type: IPv4_Public
Confidence: 95.2%

📍 Geolocation:
  Country: United States (US)
  Region: California
  City: Mountain View
  Coordinates: 37.4056, -122.0775
  Timezone: America/Los_Angeles

🌐 Network Information:
  ISP: Google LLC
  Organization: Google Public DNS
  AS Number: AS15169

🔄 Reverse DNS: dns.google

🛡️ Security Analysis:
  Classifications: cloud_hosting
  Reputation: ✅ Good (85/100)

📊 Data Sources: 3/4 services responded successfully
⏰ Analysis completed at: 2025-10-26 14:30:15
```

### Python API

```python
from core.osint.ip_intel import IPIntelligence
import asyncio

async def analyze_ip():
    async with IPIntelligence() as intel:
        result = await intel.lookup_ip('8.8.8.8')
        
        print(f"Valid: {result['valid']}")
        print(f"Type: {result['type']}")
        print(f"Country: {result['geolocation'].get('country')}")
        print(f"ISP: {result['geolocation'].get('isp')}")
        print(f"Security: {result['security_info']}")
        
        # Formatted output
        formatted = intel.format_results(result)
        print(formatted)

# Run analysis
asyncio.run(analyze_ip())
```

---

## 👤 Social Intelligence (Enhanced!)

### What It Does

✅ **12 Social Platforms**: GitHub, LinkedIn, Twitter, Instagram, Facebook, YouTube, Reddit, Pinterest, TikTok, Snapchat, Discord, Steam
✅ **Username Enumeration** across all platforms simultaneously
✅ **Profile Discovery** with enhanced data extraction
✅ **Cross-Platform Correlation** to link accounts
✅ **Free Data Extraction** - no API keys or registration required
✅ **Ethical Scraping** with robots.txt compliance and rate limiting

### Usage

```bash
# Username search across all platforms
username:elonmusk

# Auto-detection (no operator needed)
github
microsoft
@openai

# Email-based discovery
email:example@company.com  # Also searches for social profiles

# Platform-specific hints
username:github site:github.com
```

### Example Output

```
═══ Social Intelligence ═══
Username: elonmusk
Platforms Found: 8 / 12

Profiles Found:
  ✓ Twitter - @elonmusk (54M followers)
  ✓ GitHub - elonmusk (Verified)
  ✓ Instagram - elonmusk (2.1M followers)  
  ✓ LinkedIn - Elon Musk (CEO at Tesla, SpaceX)
  ✓ YouTube - Elon Musk (Channel verified)
  ✓ Reddit - u/elonmusk (Reddit Gold)
  ✓ Discord - elonmusk#1234
  ✓ Steam - elonmusk (Gaming profile)

Summary: Searched 12 platforms in 3.2 seconds
```

### Supported Platforms

| Platform | Check Methods | Data Extracted |
|----------|---------------|----------------|
| **GitHub** | Profile page, API endpoints | Name, bio, follower count, repos |
| **LinkedIn** | Profile URLs, search results | Name, title, company, connections |
| **Twitter** | Profile check, handle validation | Name, bio, follower count, verification |
| **Instagram** | Profile page, metadata | Name, bio, follower count, post count |
| **Facebook** | Public profile check | Name, basic info if public |
| **YouTube** | Channel check, handle lookup | Channel name, subscriber count |
| **Reddit** | User profile, karma check | Username, karma, account age |
| **Pinterest** | Profile page, board check | Name, follower count, board count |
| **TikTok** | Profile validation | Name, follower count, verification |
| **Snapchat** | Public profile check | Display name if available |
| **Discord** | Username patterns | Username format validation |
| **Steam** | Profile URL check | Display name, profile data |

### Python API

```python
from core.osint.social_intel import SocialIntelligence
import asyncio

async def search_username():
    async with SocialIntelligence() as intel:
        # Search across all platforms
        result = await intel.search_username('elonmusk')
        
        print(f"Platforms searched: {len(result['platforms'])}")
        
        for platform, data in result['platforms'].items():
            if data.get('exists'):
                profile = data.get('profile_data', {})
                print(f"✓ {platform}: {profile.get('display_name', 'Found')}")
                
        # Email-based discovery
        email_result = await intel.discover_profiles_by_email('test@company.com')
        print(f"Email discovery: {email_result}")

# Run search
asyncio.run(search_username())
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
# Multi-intelligence approach
username:johndoe              # Check all 12 social platforms
email:john.doe@company.com    # Email + social discovery
John Doe                      # General web search

# Platform-specific searches
site:linkedin.com "John Doe" inurl:profile
site:github.com "John Doe"
```

### 🌐 IP Address Investigation

```bash
# Comprehensive IP analysis
ip:192.168.1.100          # Full intelligence report
8.8.8.8                   # Auto-detects as IP

# Combine with context
ip:suspicious.ip.address site:security-blog.com
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

### � Social Media Investigation

```bash
# Username enumeration across all platforms
username:suspicioususer
@suspect_handle

# Cross-platform correlation
username:john_doe site:linkedin.com
username:john_doe site:github.com
```

### 📧 Email Investigation  

```bash
# Comprehensive email analysis (includes social discovery)
email:suspect@example.com

# Platform-specific searches
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
| **IP/Social features not working** | Run `pip install aiohttp beautifulsoup4` |
| **Ollama not running** | Run `ollama serve` (for AI features) |
| **Prohibited content** | Remove blacklisted terms (hack, password, stalk, etc.) |
| **Social platforms timeout** | Check internet connection, some platforms may be blocked |
| **IP services unavailable** | Normal - system uses multiple services, some may be down |

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

## 🎯 All Features Summary (5 Intelligence Types)

| Feature | Operator | Data Sources | Validation | AI Enhancement |
|---------|----------|--------------|------------|----------------|
| **Email Intelligence** | `email:` | ✅ LinkedIn, GitHub, Twitter, Facebook + Social Discovery | ✅ Syntax, MX, Disposable | ✅ Variations |
| **Phone Intelligence** | `phone:` | ✅ Format variations, Web search | ✅ Country, Carrier, Type | ✅ Formats |
| **IP Intelligence** 🆕 | `ip:` | ✅ 4 Geolocation services, WHOIS, Security | ✅ IPv4/IPv6, Type detection | ✅ Auto-detection |
| **Social Intelligence** 🆕 | `username:` | ✅ 12 Platforms simultaneously | ✅ Profile validation, Data extraction | ✅ Auto-detection |
| **Search Operators** | `site:`, `inurl:`, etc. | ✅ DuckDuckGo, Multiple engines | N/A | ✅ Suggestions |
| **Query Enhancement** | Auto-detect | N/A | ✅ Auto query-type detection | ✅ Variations, Entity Detection |

### 🆕 New in v1.4.1

- **IP Intelligence**: Complete IPv4/IPv6 analysis without API keys
- **Enhanced Social Intelligence**: 12 platforms with profile data extraction  
- **Auto-Detection**: Smart query type recognition
- **Privacy-First**: No external API dependencies
- **Ethical Scraping**: Robots.txt compliance and rate limiting

---

**Remember:** Use OSINT features responsibly and ethically! 🛡️
