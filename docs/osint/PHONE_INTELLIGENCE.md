# Phone Intelligence System - Developer Documentation

**Version:** 1.4.5
**Module:** `core/osint/phone_intel.py`
**Last Updated:** 2025-10-30

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Phone Number Parsing](#phone-number-parsing)
4. [Auto-Region Detection](#auto-region-detection)
5. [Normalization & Storage](#normalization--storage)
6. [Query Processing](#query-processing)
7. [AI-Powered Suggestions](#ai-powered-suggestions)
8. [Format Variations](#format-variations)
9. [API Reference](#api-reference)
10. [Testing](#testing)

---

## Overview

The Phone Intelligence system provides comprehensive phone number analysis with support for **11 countries** and automatic region detection. It handles various input formats and normalizes numbers for consistent storage and duplicate prevention.

### Key Features

- ✅ **International Support:** 11 countries (DE, GB, US, PL, FR, IT, ES, AT, CH, NL, BE)
- ✅ **Auto-Detection:** Automatically detects country from national format numbers
- ✅ **Smart Parsing:** Handles formats with/without quotes, spaces, slashes, dashes
- ✅ **Duplicate Prevention:** E.164 normalization prevents storing the same number multiple times
- ✅ **AI Suggestions:** Context-aware alternative queries based on phone analysis
- ✅ **Type Detection:** Identifies landline, mobile, VoIP, toll-free, etc.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Query                           │
│             phone:04167/21 60 111                       │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│              Query Parser (query_parser.py)             │
│  • Extracts phone from query using flexible regex       │
│  • Supports: phone:xxx, phone:"xxx", phonenumber:xxx    │
│  • Handles spaces, slashes, dashes in number            │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│          Phone Intelligence (phone_intel.py)            │
│  1. Normalize input (remove non-digits except +)        │
│  2. Auto-detect region if not provided                  │
│  3. Parse with phonenumbers library                     │
│  4. Validate & extract metadata                         │
│  5. Generate format variations                          │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│              Agent (agent.py)                           │
│  • Format results for display                           │
│  • Generate AI-powered alternative queries              │
│  • Execute web searches with variations                 │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│          Memory Store (memory_store.py)                 │
│  • Normalize to E.164 format (+4941672160111)           │
│  • Check for duplicates using normalized value          │
│  • Store with original format preserved                 │
└─────────────────────────────────────────────────────────┘
```

---

## Phone Number Parsing

### Query Parser Pattern

**File:** `core/osint/query_parser.py:86`

```python
'phone': r'(?:phone|phonenumber):(?:"([^"]+)"|([^\s]+(?:[\s/\-][^\s]+)*))'
```

**Supports:**
- `phone:12345678` - Without quotes
- `phone:"123 456 78"` - With quotes
- `phone:04167/21 60 111` - With slashes
- `phone:555-123-4567` - With dashes
- `phonenumber:xxx` - Alternative keyword

**Extraction Logic:**

```python
# Extract phone operator
phone_match = re.search(self.OPERATORS['phone'], remaining)
if phone_match:
    # Handle both quoted and unquoted phone
    phone_string = phone_match.group(1) if phone_match.group(1) else phone_match.group(2)

    # Split by common separators for multiple phones
    phones = [p.strip() for p in re.split(r'[,;]', phone_string) if p.strip()]

    if phones:
        parsed.phone = phones[0]  # Primary phone
        parsed.phones = phones     # All phones
```

---

## Auto-Region Detection

**File:** `core/osint/phone_intel.py:220-271`

### Algorithm

When no region is provided, the system attempts to detect it automatically:

```python
def _detect_region(self, normalized: str) -> Optional[str]:
    """Auto-detect country from national format number."""

    # Numbers starting with 0 (European national format)
    if normalized.startswith('0') and not normalized.startswith('00'):
        regions_to_try = [
            'DE',  # Germany
            'GB',  # UK
            'PL',  # Poland
            'FR',  # France
            'IT',  # Italy
            'ES',  # Spain
            'AT',  # Austria
            'CH',  # Switzerland
            'NL',  # Netherlands
            'BE',  # Belgium
        ]

        for region in regions_to_try:
            try:
                parsed = phonenumbers.parse(normalized, region)
                if phonenumbers.is_valid_number(parsed):
                    return region
            except:
                continue

    # Numbers without leading 0 (US/CA 10-digit format)
    elif normalized.isdigit() and len(normalized) == 10:
        try:
            parsed = phonenumbers.parse(normalized, 'US')
            if phonenumbers.is_valid_number(parsed):
                return 'US'
        except:
            pass

    return None
```

### Priority Order

The system tries regions in priority order based on usage patterns:

1. **Germany (DE)** - Most common in European queries
2. **UK (GB)** - Second most common European
3. **Poland (PL)** - Growing usage
4. **France, Italy, Spain, Austria, Switzerland, Netherlands, Belgium**

### Examples

| Input | Auto-Detected Region | Reasoning |
|-------|---------------------|-----------|
| `030 12345678` | DE | German area code (Berlin) |
| `020 7946 0958` | GB | UK area code (London) |
| `5551234567` | US | 10-digit without leading 0 |
| `022 123 4567` | PL | Polish area code (Warsaw) |
| `04167/21 60 111` | DE | German area code (4167) |

---

## Normalization & Storage

**File:** `core/memory_store.py:269-350`

### E.164 Format

All phone numbers are normalized to **E.164 format** for storage:
- **Format:** `+[country code][subscriber number]`
- **Example:** `+4941672160111`
- **No spaces, dashes, or other separators**

### Normalization Process

```python
def _normalize_phone(self, phone: str) -> str:
    """Normalize phone to E.164 format."""
    try:
        import phonenumbers

        # Remove all non-digit characters except +
        cleaned = re.sub(r'[^\d+]', '', phone)

        # Try to parse with auto-detection
        try:
            parsed = phonenumbers.parse(cleaned, None)
        except:
            # Try common regions
            for region in ['DE', 'US', 'GB']:
                try:
                    parsed = phonenumbers.parse(cleaned, region)
                    if phonenumbers.is_valid_number(parsed):
                        break
                except:
                    continue
            else:
                # Fallback: just digits
                return re.sub(r'\D', '', phone)

        # Format to E164
        return phonenumbers.format_number(
            parsed,
            phonenumbers.PhoneNumberFormat.E164
        )
    except ImportError:
        # Fallback: remove all non-digits
        return re.sub(r'\D', '', phone)
```

### Duplicate Detection

```python
def remember_phone(self, phone: str, metadata: Optional[Dict] = None) -> bool:
    # Normalize phone
    normalized_phone = self._normalize_phone(phone)

    entry = {
        'value': normalized_phone,      # E.164 format for comparison
        'original': phone.strip(),      # Original format preserved
        'added_at': datetime.now().isoformat(),
        'metadata': metadata or {}
    }

    # Check if already exists (compare normalized values)
    if any(self._normalize_phone(p['value']) == normalized_phone
           for p in self.data['phones']):
        logger.info(f"Phone already in memory")
        return False  # Duplicate detected

    # Store new phone
    self.data['phones'].append(entry)
    return True
```

### Example

```python
# All these variations are recognized as the SAME number:
remember_phone("04167/21 60 111")    # → +4941672160111
remember_phone("041672160111")       # → +4941672160111 (duplicate!)
remember_phone("+4941672160111")     # → +4941672160111 (duplicate!)
remember_phone("+49 4167 2160111")   # → +4941672160111 (duplicate!)

# Result: Only 1 phone stored
```

---

## Query Processing

**File:** `core/agent.py:1592-1594, 1901-1925`

### Processing Flow

```python
# 1. Parse query
parsed = parser.parse(query)  # phone:04167/21 60 111

# 2. Check if phone intelligence enabled
if parsed.phone and phone_intel:
    phone_parts = self._process_phone_intelligence(
        parsed.phone,
        phone_intel
    )

# 3. Analyze phone
def _process_phone_intelligence(self, phone: str, phone_intel) -> list:
    # Analyze with PhoneIntelligence
    phone_result = phone_intel.analyze_phone(phone)

    # Format results
    response_parts = ["\n═══ Phone Intelligence ═══\n"]
    response_parts.append(f"**Phone:** {phone_result['input']}")
    response_parts.append(f"**Valid:** {'✓' if phone_result['valid'] else '✗'}")

    if phone_result['valid']:
        # Add analysis results
        response_parts.extend(self._format_phone_results(phone_result))

        # Generate AI suggestions
        ai_queries = self._generate_phone_ai_suggestions(phone_result)
        if ai_queries:
            response_parts.append("\n═══ AI Analysis ═══\n")
            response_parts.append("**Alternative Queries:**")
            for query in ai_queries:
                response_parts.append(f"  • {query}")

        # Search online
        online_parts = self._search_phone_online(phone_result)
        response_parts.extend(online_parts)

    return response_parts
```

---

## AI-Powered Suggestions

**File:** `core/agent.py:1927-1965`

### Generation Logic

AI suggestions are generated based on phone analysis metadata:

```python
def _generate_phone_ai_suggestions(self, phone_result: dict) -> list:
    """Generate context-aware alternative queries."""
    queries = []

    country = phone_result.get('country', '')
    phone_type = phone_result.get('type', 'unknown')
    carrier = phone_result.get('carrier', '')
    formatted = phone_result.get('formatted', '')

    # Map phone types to readable text
    type_map = {
        'fixed_line': 'landline',
        'mobile': 'mobile',
        'fixed_line_or_mobile': 'phone',
        'toll_free': 'toll-free number',
        'voip': 'VoIP number'
    }
    type_text = type_map.get(phone_type, 'phone number')

    # Generate queries
    if country and formatted:
        # Query 1: Country + Type + Number
        queries.append(f"{country} {type_text} {formatted}")

    if carrier and formatted:
        # Query 2: Carrier + Number
        queries.append(f"{carrier} {formatted}")

    # Query 3: Alternative format
    if phone_result.get('variations'):
        for var in phone_result['variations'][:2]:
            if var != phone_result['input'] and var != formatted:
                queries.append(f'"{var}" contact')
                break

    # Deduplicate and limit to 3
    queries = list(dict.fromkeys(queries))[:3]
    return queries
```

### Example Output

**Input:** `phone:04167/21 60 111`

**Analysis:**
- Country: Apensen (Germany)
- Type: fixed_line → "landline"
- Formatted: +49 4167 2160111

**Generated Queries:**
1. `Apensen landline +49 4167 2160111`
2. `"041672160111" contact`

---

## Format Variations

**File:** `core/osint/phone_intel.py:318-411`

### Generation Algorithm

```python
def generate_variations(self, phone: str) -> List[str]:
    """Generate format variations for search."""
    normalized = self._normalize_phone(phone)
    variations = [phone, normalized]

    # Country-specific formats
    if normalized.startswith('+49'):
        # German formats
        national = '0' + normalized[3:]
        variations.append(national)
        variations.append(f"+49 {normalized[3:6]} {normalized[6:]}")
        variations.append(f"0{normalized[3:6]} {normalized[6:]}")

    elif normalized.startswith('+44'):
        # UK formats
        national = '0' + normalized[3:]
        variations.append(national)
        variations.append(f"+44 {normalized[3:5]} {normalized[5:9]} {normalized[9:]}")

    elif normalized.startswith('+1'):
        # US/Canada formats
        area = normalized[2:5]
        exchange = normalized[5:8]
        number = normalized[8:]
        variations.append(f"({area}) {exchange}-{number}")
        variations.append(f"{area}-{exchange}-{number}")
        variations.append(f"{area}.{exchange}.{number}")

    # ... (more countries)

    # Remove duplicates
    variations = list(set(variations))
    return variations
```

### Supported Formats by Country

| Country | Formats Generated |
|---------|------------------|
| **Germany (DE)** | `+49 151 12345678`, `0151 12345678`, `015112345678` |
| **UK (GB)** | `+44 20 7946 0958`, `020 7946 0958` |
| **USA/CA** | `+1 555 123 4567`, `(555) 123-4567`, `555-123-4567`, `555.123.4567` |
| **Poland (PL)** | `+48 22 123 4567`, `22 123 4567` |
| **France (FR)** | `+33 1 42 86 82 00`, `01 42 86 82 00` |

---

## API Reference

### PhoneIntelligence Class

```python
class PhoneIntelligence:
    """Phone number OSINT capabilities."""

    def __init__(self):
        """Initialize with phonenumbers library if available."""

    def analyze_phone(self, phone: str, region: str = None) -> Dict:
        """
        Comprehensive phone number analysis.

        Args:
            phone: Phone number in any format
            region: Optional country code (e.g., 'DE', 'US')

        Returns:
            {
                'input': str,           # Original input
                'valid': bool,          # Is valid phone number
                'formatted': str,       # International format
                'country': str,         # Country/location name
                'region': str,          # Region code (e.g., 'DE')
                'carrier': str,         # Carrier name (if available)
                'type': str,           # mobile/fixed_line/voip/etc.
                'variations': List[str], # Format variations
                'confidence': float     # 0.0 - 1.0
            }
        """
```

### Memory Store Methods

```python
class MemoryStore:

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone to E.164 format."""

    def remember_phone(self, phone: str,
                      metadata: Optional[Dict] = None,
                      user_id: str = "anonymous") -> bool:
        """
        Store phone number (with duplicate detection).

        Args:
            phone: Phone number in any format
            metadata: Optional metadata (country, type, etc.)
            user_id: User identifier

        Returns:
            True if added, False if duplicate
        """
```

---

## Testing

### Unit Tests

**File:** `tests/unit/test_cloud_llm_client.py`

OpenAI tests are automatically skipped if the package is not installed:

```python
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

@pytest.mark.skipif(not HAS_OPENAI, reason="openai package not installed")
class TestOpenAIClient:
    # Tests only run if openai is installed
    pass
```

### Manual Testing

```bash
# Test various formats
phone:04167/21 60 111          # German with slash
phone:"555 123 4567"           # US with quotes
phone:+44 20 7946 0958         # UK international
phonenumber:022 123 4567       # Poland alternative keyword

# Test memory storage
phone:04167/21 60 111
<merke dir die phone number
status                         # Should show Phones: 1

# Test duplicate detection
phone:041672160111
<merke phone
status                         # Should still show Phones: 1 (duplicate!)
```

### Expected Behavior

1. **Parsing:** All formats should be recognized
2. **Auto-Detection:** Country should be auto-detected for national formats
3. **Normalization:** Same number in different formats → 1 stored entry
4. **AI Suggestions:** Context-aware queries should be generated
5. **Variations:** Multiple search formats should be created

---

## Error Handling

### Invalid Phone Numbers

```python
# Input: phone:123
# Output: Valid: ✗ False
# Reason: Too short, doesn't match any pattern
```

### Region Detection Failure

```python
# Input: phone:99999999
# Output: Uses basic validation (7-15 digits)
# Type: unknown
# Country: None
```

### phonenumbers Library Not Available

```python
# Falls back to basic validation
# Pattern: ^\+?\d{7,15}$
# No carrier/type detection
# Simple country detection based on prefix
```

---

## Performance Considerations

### Caching

Phone analysis results are cached in the session:
- **Key:** Normalized phone number
- **TTL:** Session duration
- **Benefits:** Avoid re-parsing same number

### Rate Limiting

Web searches for phone variations respect rate limits:
- **Max:** 3 variations searched
- **Throttle:** 1 request per second
- **Configured in:** `config.yaml`

### Memory Usage

Normalization prevents memory bloat:
- **Without normalization:** 4 entries for same number
- **With normalization:** 1 entry (75% reduction)

---

## Future Enhancements

- [ ] Add more countries (Asia, South America, Africa)
- [ ] Implement phone number reputation checking
- [ ] Add SIM card type detection (prepaid/postpaid)
- [ ] Support for number portability detection
- [ ] Integration with phone lookup APIs
- [ ] Batch phone validation endpoint

---

## References

- **phonenumbers library:** https://github.com/daviddrysdale/python-phonenumbers
- **E.164 Format:** https://en.wikipedia.org/wiki/E.164
- **libphonenumber:** https://github.com/google/libphonenumber

---

**Last Updated:** 2025-10-30
**Maintainer:** Development Team
**Version:** 1.4.5
