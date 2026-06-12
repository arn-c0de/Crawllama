# Using OSINT Results as Context

---

 **Navigation:** [Home](../../README.md) | [Docs](../README.md) | [OSINT Guide](OSINT_USAGE.md) | [Social Intel](SOCIAL_INTELLIGENCE.md) | [LangGraph](../guides/LANGGRAPH_GUIDE.md)

---

## Overview
After an OSINT search, you can use the results as a **context source** for further analysis.

## Workflow

### 1. Perform OSINT Search
```
: site:example.com
```

**Output:**
```
[1] Example - Homepage
 https://example.com
 This is the homepage...

[2] Example - Contact
 https://example.com/contact
 Contact us...

[3] Example - Imprint
 https://example.com/imprint
 Imprint and legal information...
```

### 2. Use Results as Context

#### Option A: With LLM Analysis
```
: quelle 1 2 3
```

The agent will:
1. Load the URLs of results 1, 2, and 3
2. Extract the content
3. Perform **AI analysis**
4. Summarize the information

**Example:**
```
: summarize sources 1 2 3

 Result #1 loaded
 Result #2 loaded
 Result #3 loaded

Summary of sources:

The website example.com offers the following main sections:
- Homepage [1]: Main information and overview
- Contact [2]: Contact form and email: info@example.com
- Imprint [3]: Legal information, company headquarters in...
```

#### Option B: URLs Only (Context-Only Mode)
```
: <quelle 1 2 3
```

**Output (without LLM call):**
```
[1] Example - Homepage - https://example.com
[2] Example - Contact - https://example.com/contact
[3] Example - Imprint - https://example.com/imprint
```

## Advanced Usage

### Specific Analysis Commands

#### Extract Contact Information
```
: find contact information in sources 1-5
```

#### Comparison
```
: compare sources 2 and 5
```

#### Search in Sources
```
: search for "opening hours" in sources 1-10
```

#### Email/Phone Extraction
```
: extract emails from sources 1 2 3
```

### Combined OSINT Operators

#### Site + Email Search
```
: site:example.com email:@example.com
```

Then:
```
: analyze sources with emails
```

#### Site + Intext Search
```
: site:example.com intext:"imprint"
```

Then:
```
: summarize imprint information from sources
```

## Tips & Best Practices

### 1. Selective Source Selection
Choose only relevant results:
```
: quelle 2 5 7 # Only specific results
```

Instead of all results:
```
: quelle 1-10 # All results (slower!)
```

### 2. Context-Only Mode for Overview
Use `<quelle` for quick URL overview:
```
: <quelle 1-5 # Quick list without analysis
```

### 3. Targeted Follow-up Questions
After the initial analysis, you can ask specific questions:
```
: site:example.com
: quelle 3
: what contact information does this page contain?
```

### 4. Multiple Source Usage
You can use the same sources multiple times:
```
: site:example.com
: quelle 1 2 3 # First analysis
: find opening hours # Follow-up
: quelle 4 5 # Additional sources
```

## Cache Behavior

### Result-References are NOT Cached
```
: quelle 1 2 3
→ Always current results from session
```

### Web Pages are Cached
```
: quelle 1
→ Loads https://example.com (cached for 24h)

: quelle 1
→ Uses cached content (faster!)
```

### Session is Automatically Saved
After each OSINT search, the session is saved:
```
INFO: Session saved to data\session.json
```

**Security Note:** The `session.json` file is already listed in `.gitignore` and will not be committed to the repository. If you store sensitive data in sessions, you should additionally encrypt the file or disable session storage.

## Troubleshooting

### Problem: "No previous search results"
**Cause:** No OSINT/web search performed
**Solution:** First perform a search:
```
: site:example.com
: quelle 1
```

### Problem: "Result X does not exist"
**Cause:** Invalid result number
**Solution:** Check available results:
```
: <quelle 1-20 # Shows available results
```

### Problem: Cache shows old results
**Cause:** Cache issue (should no longer occur)
**Solution:** Use Context-Only Mode:
```
: <quelle 1 2 3
```

Or clear the cache:
```
: /cache clear
```

## Example Workflows

### Workflow 1: Company Research
```
# 1. Domain search
: site:company-example.com

# 2. Load imprint and contact
: quelle 2 3

# 3. Specific analysis
: extract company data and contact information

# 4. Additional details
: find CEO and company headquarters
```

### Workflow 2: Email OSINT
```
# 1. Email search
: email:info@example.com

# 2. Analyze results
: quelle 1-5

# 3. Extract context
: in what contexts is this email mentioned?
```

### Workflow 3: Competitor Analysis
```
# 1. Search Company A
: site:company-a.com
: quelle 1 2 3

# 2. Search Company B
: site:company-b.com
: quelle 1 2 3

# 3. Comparison
: compare the two companies based on the sources
```

## Performance Tips

### Faster
- Use Context-Only Mode: `<quelle 1-5`
- Select only relevant results: `quelle 2 5 7`
- Use cached content

### Slower
- Load all results: `quelle 1-20`
- Multiple redundant analyses
- Cache disabled

---

**Further Documentation:**
- [OSINT_USAGE.md](OSINT_USAGE.md) - OSINT operators
- [QUICKSTART.md](../getting-started/QUICKSTART.md) - Getting started

**Last Updated:** October 25, 2025
