# CodeQL Security Alerts - False Positives Guide

## Overview
This document explains CodeQL security alerts that are **false positives** and can be safely dismissed.

## Clear-text Logging of Sensitive Information

### Context
CodeQL flags any logging of variables named `url`, `query`, `domain`, etc. as potential security issues because these names could contain sensitive data like API keys or passwords in URL parameters.

### Our Implementation
**All URLs are already sanitized before logging** using `sanitize_url_for_logging()` function which:
- Removes sensitive query parameters (api_key, token, password, etc.)
- Replaces sensitive values with `***REDACTED***`
- Returns safe URLs for logging

### Files Affected
- `tools/page_reader.py` - Lines 90, 116, 124, 151, 155, 163, 169, 219, 223, 226
- `core/agent.py` - Lines 520, 555, 764, 765, 870, 876, 877, 898, 899, 1215, 1248, 1516, 1600, 2045, 2051
- `utils/domain_blacklist.py` - Lines 238, 245
- `core/osint/domain_intel.py` - Line 370
- `utils/safe_fetch.py` - Lines 168, 173, 178, 192, 196, 204, 216, 221, 230, 242, 246
- `core/memory_store.py` - Lines 416, 421
- `app.py` - Line 263

### Why These Are False Positives

1. **User queries** are search terms, not credentials
   - Example: "Python tutorial", "Berlin weather"
   - These are intentionally logged for debugging and analytics

2. **URLs** are sanitized before logging
   - `sanitize_url_for_logging()` removes all sensitive parameters
   - Example: `https://api.com?key=secret` → `https://api.com?key=***REDACTED***`

3. **Domain names** are public information
   - Examples: "example.com", "google.com"
   - Not sensitive data

### Recommendation
**Mark these alerts as "Dismissed" with reason: "False positive - data is already sanitized"**

## Incomplete URL Substring Sanitization

### Context
CodeQL flags code that checks if one URL is a substring of another, which could potentially be bypassed with specially crafted URLs.

### Files Affected
- `tests/integration/test_web_search.py` - Line 38
- `tests/osint/test_domain_intel.py` - Lines 276, 277
- `tests/unit/test_domain_blacklist.py` - Lines 94, 95

### Why These Are False Positives

These are **test assertions**, not security checks:
```python
# Checking if URL appears in formatted output
assert "https://test.example.com" in formatted
```

This is not validating URLs or checking substrings for security - it's simply verifying that a test URL appears in the output string.

### Recommendation
**Mark these alerts as "Dismissed" with reason: "False positive - test assertion, not URL validation"**

## Summary

All flagged issues are either:
1. Already sanitized (URLs with sensitive params removed)
2. Non-sensitive data (user queries, public domain names)
3. Test code (assertions checking output)

**Action Required:**
- Review alerts manually in GitHub Security tab
- Dismiss each alert with appropriate reason
- Configure CodeQL to ignore test files in future scans

## Future Prevention

To prevent these false positives:
1. Test files are now excluded in `.github/codeql/codeql-config.yml`
2. All URL logging uses `sanitize_url_for_logging()`
3. API keys and sensitive data are never logged directly
