# Validators Refactoring Guide

## Problem Solved

**Issue:** Function name collision - two different functions named `is_safe_url()`:
- `utils/validators.py::is_safe_url(url, allowed_domains)` - Full URL validation (schema, private IPs, whitelist)
- `utils/domain_blacklist.py::is_safe_url(url)` - Blacklist pattern check only

This caused confusion and made it unclear which function to use.

## Solution

Renamed the blacklist-specific function for clarity:
- `domain_blacklist.is_safe_url()` → `domain_blacklist.is_url_not_blacklisted()`
- Old function kept as deprecated wrapper with DeprecationWarning

## Changes Made

### 1. Core Changes

#### `utils/domain_blacklist.py`
```python
# NEW: Clearer function name
def is_url_not_blacklisted(url: str) -> bool:
    """Check if URL is NOT blacklisted (blacklist perspective only)."""
    return not blacklist.is_blacklisted(url)

# DEPRECATED: Old function with warning
def is_safe_url(url: str) -> bool:
    """DEPRECATED: Use is_url_not_blacklisted() or validators.is_safe_url()."""
    warnings.warn(
        "domain_blacklist.is_safe_url() is deprecated. "
        "Use is_url_not_blacklisted() for blacklist checks or "
        "validators.is_safe_url() for full URL validation.",
        DeprecationWarning,
        stacklevel=2
    )
    return is_url_not_blacklisted(url)
```

### 2. Import Updates

#### `utils/safe_fetch.py`
```python
# OLD
from utils.domain_blacklist import is_safe_url

# NEW
from utils.domain_blacklist import is_url_not_blacklisted
```

#### `tools/page_reader.py`
```python
# OLD
from utils.domain_blacklist import is_safe_url

# NEW
from utils.domain_blacklist import is_url_not_blacklisted
```

#### `tests/test_domain_blacklist.py`
```python
# OLD
from utils.domain_blacklist import DomainBlacklist, is_safe_url, filter_safe_urls

# NEW
from utils.domain_blacklist import DomainBlacklist, is_url_not_blacklisted, filter_safe_urls
```

### 3. Usage Updates

#### `utils/safe_fetch.py`
```python
# OLD
if self.use_blacklist and not is_safe_url(url):
    logger.warning(f"URL blocked by blacklist: {url}")

# NEW
if self.use_blacklist and not is_url_not_blacklisted(url):
    logger.warning(f"URL blocked by blacklist: {url}")
```

#### `tools/page_reader.py`
```python
# OLD
if not is_safe_url(url):
    logger.warning(f"Unsafe URL rejected: {url}")

# NEW
if not is_url_not_blacklisted(url):
    logger.warning(f"URL blocked by blacklist: {url}")
```

#### `tests/test_domain_blacklist.py`
```python
# OLD
def test_is_safe_url(self):
    assert is_safe_url("https://www.google.com")

# NEW
def test_is_url_not_blacklisted(self):
    assert is_url_not_blacklisted("https://www.google.com")
```

## Migration Guide

### For Existing Code

If your code uses `domain_blacklist.is_safe_url()`:

```python
# ❌ OLD (still works but shows deprecation warning)
from utils.domain_blacklist import is_safe_url
if is_safe_url(url):
    fetch(url)

# ✅ NEW (blacklist check only)
from utils.domain_blacklist import is_url_not_blacklisted
if is_url_not_blacklisted(url):
    fetch(url)

# ✅ BETTER (full validation: schema + private IPs + blacklist)
from utils.validators import is_safe_url
if is_safe_url(url):
    fetch(url)
```

### Decision Tree

**When to use which function?**

1. **`validators.is_safe_url(url, allowed_domains=None)`**
   - ✅ Full URL validation
   - ✅ Checks schema (http/https only)
   - ✅ Blocks localhost/private IPs
   - ✅ Optional domain whitelist
   - Use: **Primary URL validation for user input**

2. **`domain_blacklist.is_url_not_blacklisted(url)`**
   - ✅ Blacklist pattern check only
   - ✅ Fast regex matching
   - ✅ Custom pattern support
   - Use: **Additional filtering after basic validation**

3. **`DomainBlacklist.is_blacklisted(url)`**
   - ✅ Instance method for custom blacklist
   - ✅ More control over patterns
   - Use: **When you need custom blacklist logic**

### Example: Comprehensive URL Validation

```python
from utils.validators import is_safe_url
from utils.domain_blacklist import is_url_not_blacklisted

def validate_url_comprehensive(url: str, allowed_domains: List[str] = None) -> bool:
    """
    Full URL validation combining multiple checks.
    
    Args:
        url: URL to validate
        allowed_domains: Optional domain whitelist
        
    Returns:
        True if URL passes all checks
    """
    # Step 1: Basic URL validation (schema, private IPs, whitelist)
    if not is_safe_url(url, allowed_domains):
        logger.warning(f"URL failed basic validation: {url}")
        return False
    
    # Step 2: Blacklist check (malware, spam patterns)
    if not is_url_not_blacklisted(url):
        logger.warning(f"URL blocked by blacklist: {url}")
        return False
    
    return True
```

## Benefits

1. **Clearer API**: Function names match their purpose
2. **No Confusion**: Different functions for different validation types
3. **Backwards Compatible**: Old function still works with deprecation warning
4. **Better Documentation**: Comments explain which function to use when
5. **Type Safety**: Explicit function names reduce mistakes

## Testing

All tests pass with new naming:
```bash
✅ domain_blacklist import works
✅ is_url_not_blacklisted('https://google.com') → True
✅ page_reader.py syntax valid
✅ safe_fetch.py syntax valid
```

## Files Modified

- ✅ `utils/domain_blacklist.py` - Renamed function + deprecation wrapper
- ✅ `utils/safe_fetch.py` - Updated import + usage
- ✅ `tools/page_reader.py` - Updated import + usage
- ✅ `tests/test_domain_blacklist.py` - Updated import + test name

## Next Steps

1. Monitor deprecation warnings in logs
2. Update any external plugins/tools using old function
3. After 2-3 releases, remove deprecated `is_safe_url()` from domain_blacklist.py
4. Continue with text-cleaning consolidation (Points 16-17)
