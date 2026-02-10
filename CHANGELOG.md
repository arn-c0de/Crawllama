📚 **Navigation:** [README](README.md) | [Contributing](CONTRIBUTING.md) | [Security](SECURITY.md) | [Docs](docs/README.md)

---

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- GUI with Streamlit/Gradio
- GraphQL API
- Redis cache for production
- Voice interface

## [1.4.7-part2] - 2026-02-10

### Refactored
- **Modular memory store**: Split monolithic `core/memory_store.py` (1,094 lines) into `core/memory/` package with 9 modules (constants, persistence, quotas, sanitization, operations, breach, export, store). Follows existing `core/health/` and `core/osint/` patterns. Backward-compatible shim keeps all existing imports working.
- **Async web fetching hardening**: `AsyncFetcher` now defaults to `SafeFetcher` to inherit SSRF protection, blacklist/robots checks, rate limiting, and size limits. Redirects are disabled by default.

### Fixed
- **`export_memory_snapshot` crash**: Called non-existent `self.get_stats()` — fixed to `self.get_summary()`
- **`memory_store.get_all()` missing**: Added `get_all()` method returning full data dict (used by API endpoints)
- **`memory.remember_note()` missing**: Fixed call in `core/agent.py` to use existing `add_note()`, added `metadata` parameter
- **Redact sensitive info from logs**: Sanitize PII in log output (CodeQL findings)
- **Proxy credential logging**: Redact credentials from proxy URL logs
- **Safe fetch response handling**: Ensure responses are closed reliably and handle missing responses defensively
- **Text extractor limits**: Add size/page limits to PDF/DOCX extraction to prevent memory spikes

### Security
- **Websearch escalation fix**: Prevent unauthorized escalation in web search module
- **Modular breach detection architecture** (#22): Restructured breach detection into composable modules
- **Robots.txt fetch hardening**: Add SSRF validation and timeouts when fetching `robots.txt`
- **Redirect control**: Allow redirect handling to be explicitly disabled in `SafeFetcher` and `AsyncFetcher`
- **Allowlist boundary check**: Harden hostname allowlist matching to prevent suffix bypass
- **DNS resolution timeout**: Prevent hangs during SSRF hostname validation
- **Blacklist regex safety**: Skip potentially unsafe user-supplied blacklist patterns
- **Search input validation**: Validate/sanitize parallel search queries to reduce injection and abuse risks

## [1.4.7] - 2026-02-07

### Dependency updates
- **Remove heavy embedding dependency**: Removed `sentence-transformers` from core `requirements.txt` to avoid pulling PyTorch and ~12 NVIDIA/CUDA packages — saves approximately **3–4 GB** of downloads and disk space. ChromaDB supplies an ONNX-based embedding model (~17 MB via `onnxruntime`) which is sufficient for RAG workflows (see `tools/rag.py`). Leftover `sentence-transformers` entries were also removed from `requirements_temp.txt` where present.

- **Move langchain & langgraph to CORE**: `langchain`, `langchain-core`, `langchain-community`, and `langgraph` were moved into the CORE section of `requirements.txt` because these packages are required by `tools/tool_registry.py` and `core/langgraph_agent.py` at startup regardless of LLM provider. This prevents crashes when only the OpenAI provider is selected and makes the setup process consistent across providers. If you've already run `./setup.sh`, re-run it to install the moved packages; otherwise the next setup will include them. This change should make the setup experience faster and more robust for all users.

### Security Issue Fixes
- **Pinned protobuf**: Added `protobuf>=6.33.5` to the security overrides section. This pins the transitive dependency (pulled in by `chromadb`) to the patched version that fixes the ParseDict() recursion depth bypass (CVE-2026-0994, Dependabot alert #37).

### Optional LinkedIn API Integration (#19)
- **LinkedIn API as Optional Dependency**: Added `linkedin-api` as a truly optional package that enriches LinkedIn OSINT lookups without breaking core dependencies (ddgs, etc.)
- **Graceful Fallback**: Web scraping remains the default for LinkedIn profile detection; LinkedIn API is only used when `linkedin-api` is installed and credentials are configured
- **New Module**: `core/osint/linkedin_api_intel.py` with try/except import pattern (follows existing ChromaDB pattern in `tools/rag.py`)
- **Setup Scripts Updated**: `setup.sh` and `setup.bat` now offer interactive prompt for optional LinkedIn API installation
- **Requirements Updated**: New `OSINT_LINKEDIN_API` commented section in `requirements.txt` with `linkedin-api==2.3.1` and `lxml==5.3.0`
- **Documentation**: Updated `SOCIAL_INTELLIGENCE.md` with LinkedIn API setup, security warnings, and ToS implications
- **Tests**: Added `tests/osint/test_linkedin_optional.py` covering availability checks, graceful degradation, mocked API integration, and social_intel.py integration

## [1.4.6] - 2025-11-03
### Prevent Prompt-Injection / Tests
- **Fixed Working Prompt Injects** 
- Implemented **Blacklist** in agent.py




## [1.4.5] - 2025-10-29
### ☁️ Cloud LLM Integration & Provider-Based Configuration
- **Cloud LLM Support:** Full integration of OpenAI (GPT-4, GPT-4o-mini), Anthropic (Claude 3), and Groq alongside local Ollama models
- **Smart Token Limit Adjustment:** Automatically adjusts limits based on LLM provider
  - **Local Models (Ollama):** High limits (16,000 tokens, NO truncation, full context)
  - **Cloud APIs (OpenAI/Anthropic/Groq):** Ultra-conservative limits optimized for gpt-4o-mini
    - Output: 2,048 tokens (max_tokens)
    - Input: ~6,000 chars context (~1,500 tokens)
    - Total: Fits within gpt-4o-mini's 8,192 token limit
  - Context limits automatically scaled: Local (4k-12k) vs Cloud (1.5k-5k)
  - MultiHop agent intelligently truncates collected web content for cloud APIs (both analyze and synthesize steps)
  - No manual configuration needed - just change the provider setting
  - Prevents "context_length_exceeded" and "rate_limit_exceeded" errors
  - Config file is now auto-generated from config.json.example during setup.
  - **Enhanced Startup Behavior**: Application now continues when Ollama is unavailable instead of closing
  - **Interactive Provider Setup**: Direct LLM provider configuration dialog on startup when Ollama is not
  accessible
  - **Improved Error Handling**: Reduced retry spam and cleaner error messages for connection failures
  - **Streamlined Configuration**: Quick provider and model selection (OpenAI, Anthropic, Groq) without full
  settings menu
  - **Localization**: Translated remaining German UI text to English
  - **Better User Guidance**: Clear instructions for switching between local and cloud providers with API key 
  - **Setup**: Added selectable feature installation; core packages always installed, optional features can be chosen during setup
- **Improved phone intelligence**: Auto-detection for 11 countries (DE, GB, US, PL,
  FR, IT, ES, AT, CH, NL, BE), flexible phone: operator (with/without quotes),
  intelligent AI-powered query suggestions based on phone analysis, normalized
  phone storage to prevent duplicates.

## [1.4.4] - 2025-10-28

### 🤖 Adaptive Agent Hopping System

#### New Features
- **🎯 Automatic Complexity Detection** - Multi-factor query analysis
  - LLM-based semantic classification (LOW/MID/HIGH)
  - Query length heuristics (< 50 / 50-150 / > 150 chars)
  - Multi-part question detection ("compare", "versus", "and")
  - Temporal/sequential indicators ("then", "first", "steps")
  - Fallback to heuristics when LLM fails
- **🔄 Intelligent Agent Selection** - Optimal agent routing
  - LOW: SearchAgent without tools (context-only, fastest)
  - MID: SearchAgent with web search tools (standard queries)
  - HIGH: MultiHopReasoningAgent with 1-5 hops (complex analysis)
- **📈 Confidence-Based Escalation** - Automatic quality improvement
  - Escalates LOW → MID → HIGH when confidence < 0.5
  - Maximum 2 escalation attempts per query
  - Detailed escalation history in response metadata
  - Configurable confidence thresholds (default: 0.5/0.7/0.85)
- **⚡ Resource-Based Adaptation** - Dynamic performance tuning
  - CPU monitoring with 80% threshold
  - Memory monitoring with 85% threshold
  - Automatic complexity downgrade under high load
  - Degraded mode: max_hops reduced from 5 to 2
- **🔧 Force Complexity Override** - Manual control for edge cases
  - API parameter: `force_complexity` ("low"/"mid"/"high")
  - Bypasses automatic detection when needed
  - Useful for testing and specific use cases
- **📊 Comprehensive Metrics** - Full transparency
  - Strategy reasoning (why agent was selected)
  - Complexity analysis metadata
  - Resource constraint status
  - Escalation history with confidence scores
  - Elapsed time tracking

#### Bug Fixes & Improvements

**🌐 Cloud LLM Provider Support:**
  - Full integration of cloud LLM providers (OpenAI, Anthropic, Groq) alongside local Ollama models
  - Added `get_llm_client()` factory function for unified client creation
  - Smart provider detection in startup checks (validates API keys for cloud providers instead of Ollama connection)
  - Updated LLM client initialization in both main and reload sequences to support cloud providers
  - Added GPT-4o-mini to OpenAI model suggestions in settings
  - Comprehensive unit tests with conditional skipping for optional packages

**🌍 Complete English Localization:**
  - Translated all UI text from German to English
  - Settings dialog, prompts, and error messages now fully in English
  - Command-line help and arguments translated
  - Improved consistency across all user-facing text

**Available Clear Commands:**

Users now have these options:
- `clear` - Reset session (history + cache, optionally memory if configured)
- `clear-cache` - Clear cache only
- `clear-memory` - Clear memory store only
- `clear-all` - Clear everything (session + cache + memory) **NEW**

The `clear-all` command is useful for completely resetting the application state, regardless of the `auto_clear_on_clear` configuration setting.

- **Console Output Compatibility (Windows):**
  - Replaced all Unicode symbols (✓, ✗, etc.) in CLI output with ASCII alternatives for full Windows compatibility.
  - Forced UTF-8 encoding for stdout and stderr on Windows to prevent encoding errors.

- **Agent System Refactoring:**
  - All CLI queries now routed through `AdaptiveQueryProcessor` for consistent agent selection and escalation.
  - Legacy direct `agent.query()` calls removed from CLI; retained only for internal use by adaptive system.

- **MultiHopReasoningAgent Tool Parameter Bug:**
  - Fixed error in `MultiHopReasoningAgent` where `ToolRegistry._web_search_wrapper()` was called with an invalid `max_results` parameter.
  - Updated tool invocation logic to match expected interface.


**Memory Store Logging:**
  Reduced excessive logging by changing memory load/save log level from INFO to DEBUG.
  Improved log clarity and reduced console spam.

**UI Settings for Adaptive Intelligence Report:**
  - Added a settings menu option to toggle the Adaptive Intelligence Report display in both interactive and direct query modes.
  - New `ui` category in the settings editor allows users to enable/disable the report via the config file (`config.json`).
  - The settings viewer now shows the current state of "Show Adaptive Report".
  - Report display is conditionally wrapped based on the config setting, including both detailed and brief metadata outputs.
  - Users can toggle the report by editing settings in interactive mode, selecting the `ui` category, and saving changes.
  - Requires agent restart to apply changes.

**Testing & Validation:**
  Verified correct agent selection and complexity detection for both simple and complex queries.
  Confirmed robust output and no encoding errors across platforms.

#### Testing
**tests/unit/test_adaptive_hops.py** (600+ lines)
  30 unit test cases
  Tests for complexity analysis
  Resource constraint handling
  Strategy decisions
  Escalation logic
  Edge cases
**tests/integration/test_adaptive_integration.py** (500+ lines)
  Integration test suite
  End-to-end scenarios
  Mock agent testing
  Escalation flow validation

#### Technical Details
Zero dependencies added (uses existing infrastructure)
Fully backward compatible (opt-in via new endpoint)
Integrates with existing SystemMonitor and PerformanceTracker
Supports both SearchAgent and MultiHopReasoningAgent
Comprehensive logging at all decision points
Thread-safe and production-ready

#### Performance Impact
LOW complexity: ~0.5-1s (no tools)
MID complexity: ~2-3s (web search)
HIGH complexity: ~10-15s (multi-hop reasoning)
Escalation overhead: +0.2s per attempt

#### Configuration Options
```python
AdaptiveConfig(
    enable_resource_monitoring=True,
    enable_confidence_escalation=True,
    cpu_threshold_high=80.0,
    memory_threshold_high=85.0,
    confidence_low=0.5,
    max_hops_low=0,
    max_hops_mid=1,
    max_hops_high=5,
    fallback_on_resource_constraint=True,
    degraded_mode_max_hops=2
)
```
  - Commented integration steps
  - Configuration examples

#### Testing
- **tests/unit/test_adaptive_hops.py** (600+ lines)
  - 30 unit test cases
  - Tests for complexity analysis
  - Resource constraint handling
  - Strategy decisions
  - Escalation logic
  - Edge cases
- **tests/integration/test_adaptive_integration.py** (500+ lines)
  - Integration test suite
  - End-to-end scenarios
  - Mock agent testing
  - Escalation flow validation

#### Technical Details
- Zero dependencies added (uses existing infrastructure)
- Fully backward compatible (opt-in via new endpoint)
- Integrates with existing SystemMonitor and PerformanceTracker
- Supports both SearchAgent and MultiHopReasoningAgent
- Comprehensive logging at all decision points
- Thread-safe and production-ready

#### Performance Impact
- LOW complexity: ~0.5-1s (no tools)
- MID complexity: ~2-3s (web search)
- HIGH complexity: ~10-15s (multi-hop reasoning)
- Escalation overhead: +0.2s per attempt

#### Configuration Options
```python
AdaptiveConfig(
    enable_resource_monitoring=True,
    enable_confidence_escalation=True,
    cpu_threshold_high=80.0,
    memory_threshold_high=85.0,
    confidence_low=0.5,
    max_hops_low=0,
    max_hops_mid=1,
    max_hops_high=5,
    fallback_on_resource_constraint=True,
    degraded_mode_max_hops=2
)
```

## [1.4.3] - 2025-10-27

### 🌍 Internationalization & Translation

#### Complete English Translation
- **🔤 System Prompts** - All AI system prompts translated to English
  - Agent reasoning and critique prompts
  - Query enhancement and context expansion
  - Multi-hop reasoning workflow prompts
  - OSINT intelligence gathering prompts
- **📝 User-Facing Messages** - All UI messages and feedback translated
  - Error messages and warnings
  - Help text and command descriptions
  - Settings menu and configuration options
  - Status messages and confirmations
- **📄 GitHub Templates** - Complete translation of repository templates
  - Bug report template (bug_report.yml)
  - Feature request template (feature_request.yml)
  - Documentation issue template (documentation.yml)
  - Pull request template (pull_request_template.md)
  - CODEOWNERS file
- **🔧 Code Documentation** - Docstrings and comments translated
  - Function and class docstrings
  - Inline code comments
  - Script descriptions and usage instructions
- **✅ Preserved Functionality** - Maintained German text where necessary
  - German name detection regex patterns
  - Multilingual test data
  - Locale-specific formatting

#### Technical Details
- 26 files changed with comprehensive translation updates
- All core modules updated (agent.py, main.py, langgraph_agent.py)
- OSINT module fully translated (query_enhancer.py, all intelligence modules)
- Utility scripts and health monitoring translated
- GitHub workflow and issue templates standardized in English

## [1.4.2] - 2025-10-26

### 🛡️ Security Hardening & DoS Protection (Production-Ready)

#### Security Features (NEW!)
- **🔒 Prompt Injection Protection**
  - Unicode normalization (NFKC) to prevent bypass attacks
  - Dangerous pattern detection (SQL injection, XSS, command injection)
  - Length limits (5000 characters) with validation
  - External content marking for context separation
  - 9 comprehensive tests covering attack vectors
- **🌐 Enhanced SSRF Protection**
  - DNS rebinding detection with dual-check validation
  - AWS metadata endpoint blocking (169.254.169.254)
  - Localhost and private IP range blocking (RFC 1918)
  - IPv6 protection (link-local, unique-local)
  - Hostname resolution validation before requests
  - URL scheme validation (blocks file://, ftp://, gopher://)
  - 44 comprehensive tests across all attack vectors
- **🔗 HTTP Redirect Validation**
  - Manual redirect following with SSRF validation per hop
  - Maximum 5 redirect chain length (prevents infinite loops)
  - Validates every redirect target against SSRF rules
  - Blocks redirects to localhost, private IPs, AWS metadata
  - HTTP 303 special handling (converts POST to GET)
  - 16 tests for safe redirects, malicious targets, chain limits
- **🚫 XSS Protection**
  - HTML entity escaping (<, >, &, ", ')
  - Script tag removal with comprehensive patterns
  - Event handler filtering (onclick, onerror, etc.)
  - Dangerous URL protocol blocking (javascript:, data:, vbscript:)
  - 31 tests covering XSS attack vectors
- **📂 Path Traversal Protection**
  - Plugin name validation with Unicode normalization
  - Whitelist-based character validation (alphanumeric, -, _)
  - Forbidden names blacklist (., .., config, secret, etc.)
  - Path verification (ensures files stay in plugins/ directory)
  - Windows reserved name blocking (con, prn, aux, nul, etc.)
  - 51 tests for traversal attacks and edge cases
- **🚦 Redis Rate Limiting (DoS Protection)**
  - **Token Bucket algorithm** with burst support
  - **Distributed rate limiting** across multiple API servers
  - **Per-endpoint limits**: /query (10/min), /osint/query (5/min), default (60/min)
  - **Per-user tracking** with API key hashing (HMAC-SHA256, keyed with an application secret)
  - **Connection pooling** for efficient Redis usage
  - **Graceful degradation**: Falls back to in-memory if Redis unavailable
  - **Rate limit headers**: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
  - **Retry-After header** on 429 responses
  - **Redis key injection prevention** with input sanitization
  - 41 comprehensive tests (22 unit + 19 integration)
- **🔐 Security Headers**
  - Content-Security-Policy (CSP) prevents XSS
  - X-Frame-Options: DENY (prevents clickjacking)
  - X-Content-Type-Options: nosniff (prevents MIME sniffing)
  - X-XSS-Protection: 1; mode=block
  - Referrer-Policy: strict-origin-when-cross-origin
  - Permissions-Policy (disables geolocation, camera, etc.)
  - HSTS (Strict-Transport-Security) for HTTPS
  - 7 tests for header validation
- **🔑 API Key Hashing**
  - HMAC-SHA256 hashing for API keys in logs (keyed to prevent reversal and exposure)
  - 16-character truncated hash for uniqueness
  - IP address and special value preservation
  - 4 tests for hashing consistency and security
- **📊 Memory Store User Limits**
  - Per-user quotas (100 entries per category)
  - Global limits (1000 total entries)
  - User ID tracking for all stored data
  - Quota status reporting and enforcement
  - 22 tests for isolation and security

#### Testing & Quality
- **225+ Security Tests** (all passing ✅)
  - Comprehensive coverage across all security features
  - Unit tests for individual components
  - Integration tests for FastAPI middleware
  - Edge case and attack vector validation
- **Test Organization**
  - Organized into `tests/security/` directory
  - Automated discovery in health dashboard
  - CI/CD ready test suite

#### Dependencies
- **redis>=5.0.0** - Distributed rate limiting backend
- **fakeredis>=2.20.0** - Redis mocking for tests
- **urllib3>=2.5.0** - Security fixes (CVE-2025-50181, CVE-2025-50182)

#### Configuration
- **Redis Rate Limiting**
  - `REDIS_URL` environment variable (default: redis://localhost:6379/0)
  - Per-endpoint rate limits in `utils/redis_rate_limiter.py`
  - Connection pool configuration (max 50 connections)
  - Auto-retry on timeout
- **Security Settings**
  - `ALLOWED_HOSTS` - Trusted host middleware
  - `ALLOWED_ORIGINS` - CORS configuration
  - `CRAWLLAMA_DEV_MODE` - Development mode bypass

#### Performance
- **Rate Limiting**: O(1) Redis operations with connection pooling
- **Token Bucket**: Efficient sliding window calculation
- **Distributed**: Scales across multiple API servers
- **Graceful Fallback**: In-memory rate limiting if Redis unavailable

#### Security Compliance
- **OWASP Top 10 2021** Compliance
  - A03:2021 – Injection (Prompt Injection, SQL, XSS)
  - A10:2021 – Server-Side Request Forgery (SSRF)
  - A04:2021 – Insecure Design (Rate Limiting, DoS Protection)
  - A05:2021 – Security Misconfiguration (Headers, CSP)
- **GDPR Compliance**: User data isolation and quotas
- **Ethical Standards**: Rate limiting for respectful API usage

#### Migration Notes
- **Existing Deployments**: Redis optional - falls back to in-memory
- **No Breaking Changes**: All existing functionality preserved
- **Recommended**: Deploy Redis for production environments
- **Environment Variables**: See `.env.example` for Redis configuration

#### Documentation
- **Security Tests**: `tests/security/` directory with comprehensive examples
- **Rate Limiting**: `utils/redis_rate_limiter.py` with detailed docstrings
- **Integration**: `app.py` middleware implementation examples

---

### 🔓 Email Vulnerability Intelligence & Breach Storage

#### Email Vulnerability Scanner (NEW!)
- **EmailVulnerabilityIntel** - Breach/Leak detection without API keys
  - Local breach database scan (unlimited, free)
  - LeakCheck.io FREE API integration (3 queries/day)
  - DeHashed free search (limited web search)
  - GitHub leak detection (with GITHUB_TOKEN, 5000/hour free)
  - Email hash generation (MD5, SHA1, SHA256) for anonymous lookups
  - Severity level calculation (none, low, medium, high, critical)
  - Supports TXT/CSV combo lists (email:password, email|password)

#### Memory Breach Storage (NEW!)
- **Automatic Storage** of breach data during email scans
  - Persistent storage in `data/memory.json`
  - HIBP breach data (pwned status, breach count, paste count)
  - Vulnerability/leak data (leak count, sources, severity)
  - Timestamps (last_checked, last_updated)
  - Status indicators: SAFE ✅, EXPOSED 🔓, COMPROMISED 🚨
- **New Memory Store Functions**
  - `update_email_breach_info()` - Store/update breach data
  - `get_email_with_breach_info()` - Retrieve email with breach summary
  - `format_email_breach_report()` - Formatted report generator
  - Automatic metadata update for existing emails

#### Free APIs & Tools
- **LeakCheck.io** - 3 free queries/day, no registration
- **DeHashed** - Free web search, details with login
- **GitHub API** - 5000 queries/hour with Personal Access Token
- **Local Lists** - Efficient line-by-line scanning of large files

#### Documentation
- `VULNERABILITY_INTEL.md` - Setup guide for all options (free & paid)
- `MEMORY_BREACH_STORAGE.md` - API documentation, examples, best practices
- `test_vuln_intel.py` - Test script for vulnerability intelligence
- `test_memory_breach.py` - Test script for memory breach storage

---

### 🗑️ Memory Store Complete Implementation & OSINT Fixes (from earlier in v1.4.2)

#### Added (Memory Store & OSINT)
- **Persistent Memory Store** (`core/memory_store.py`) - NEW in v1.4.2!
  - Survives session `clear` command - data persists across sessions
  - Store emails, phones, IPs, usernames, domains, and notes
  - Automatic JSON serialization with timestamps and metadata
  - Full CRUD operations: remember, recall, forget, clear
  - Search across all categories with keyword matching
  - Export/Import functionality for data portability
  - Summary statistics and usage tracking
  - **No data loss** - configurable auto-clear behavior
- **Memory Commands** - Complete set
  - `remember email:test@example.com` - Store email address
  - `remember phone:+491234567890` - Store phone number
  - `remember ip:192.168.1.1` - Store IP address
  - `remember username:johndoe` - Store username
  - `remember domain:example.com` - Store domain
  - `remember note:"Important finding"` - Add note
  - `recall` - Show all stored data
  - `recall emails` - Show only emails
  - `recall search:keyword` - Search all categories
  - `forget email:test@example.com` - Remove specific entry (NEW!)
  - `forget category:emails` - Clear entire category (NEW!)
  - `forget all:true` - Clear all memory (NEW!)
- **Memory Store Forget Command** (`forget` operator)
  - Delete specific entries: `forget email:test@example.com`
  - Clear entire categories: `forget category:emails`, `forget category:phones`
  - Clear all memory: `forget all:true`
  - Support for all data types: email, phone, ip, username, domain
  - English language support: "forget email:test@test.com"
  - Real-time feedback with success/error messages
  - Integration with OSINT query parser
  - Help text in main UI with usage examples
- **Health Dashboard Integration**
  - New **Memory Store Panel** in live dashboard
  - Real-time metrics: total entries, file size, category breakdown
  - Color-coded status: green (<100 entries), yellow (100-500), red (>500)
  - Category-specific counts: emails, phones, IPs, usernames, domains, notes
  - Live updates with forced reload every cycle
- **Memory Settings**
  - `config.json`: `memory.enabled`, `memory.auto_clear_on_clear`
  - `memory.max_entries` - Warning threshold
  - `memory.max_file_size_mb` - Size limit
  - Settings command: `settings memory` - Configure memory behavior
  - Status command shows memory usage and statistics
- **OSINT Tool Memory Integration** (`tools/osint_tool.py`)
  - Memory operation handlers: `_handle_remember()`, `_handle_recall()`, `_handle_forget()`
  - Integration with query parser for memory operators
  - Natural language support: "Store all emails from source [1]"

#### Fixed
- **OSINT Query Parser Priority**
  - Memory operators (forget, remember, recall) now parsed FIRST
  - Prevents conflicts with email:/phone:/ip: operators
  - Fixed: `forget email:test@test.com` no longer misinterpreted as email lookup
  - Improved regex pattern: `\S+` to match emails, IPs with special characters
- **Phone Number Exclude Pattern**
  - Fixed: "040 822268-0" no longer parsed as "040 822268" with exclude=[0]
  - Exclude pattern now requires space before `-` to avoid matching phone extensions
  - Pattern changed from `r'-(\w+)'` to `r'\s-(\w+)(?=\s|$)'`
- **Health Dashboard Updates**
  - Memory Store panel now force-reloads data every update cycle
  - Added `memory._load()` call in SystemMonitor for live updates
  - Fixed stale data display issue

#### Changed
- **OSINT Operator Parsing Order**
  - Priority: Memory operators → Standard operators → Text extraction
  - Ensures forget/remember/recall commands take precedence
  - Prevents operator keyword conflicts (e.g., "email:" in forget context)
- **Test Organization**
  - Tests reorganized into category subdirectories (unit/, integration/, osint/, quality/, robustness/, multihop/, other/)
  - Updated test_collector.py to discover tests in subdirectories
  - Maintains backward compatibility with pytest discovery

#### Technical
- Modified `core/osint/query_parser.py`: Reorganized operator parsing sequence
- Modified `core/agent.py`: Added `_process_forget_command()`, `_auto_store_intel()`, `_get_memory_store_context()` methods
- Modified `main.py`: Added Memory Store help section with examples and settings UI
- Modified `core/health/system_monitor.py`: Force memory reload for live updates
- Modified `core/health/test_collector.py`: Support for test subdirectories
- Added `core/memory_store.py`: Complete Memory Store implementation
- Test suite: `test_forget.py` validates parsing and memory operations
- Test suite: `tests/unit/test_memory_store.py` with 44 comprehensive tests

## [1.4.1] - 2025-10-26

### 🚀 Enhanced OSINT System & Batch Processing

#### Added
- **IP Intelligence Module** (`core/osint/ip_intel.py`)
  - Comprehensive IPv4/IPv6 address analysis
  - Multi-service geolocation (ipinfo.io, ip-api.com, ipwhois.app, freegeoip.app)
  - ISP and organization identification
  - Security reputation analysis and VPN/proxy detection
  - Reverse DNS lookup and WHOIS information
  - Network range analysis
  - **No API keys required** - completely free data extraction
- **Enhanced Social Intelligence**
  - Expanded to **12 social media platforms**: GitHub, LinkedIn, Twitter, Instagram, Facebook, YouTube, Reddit, Pinterest, TikTok, Snapchat, Discord, Steam
  - Multiple check URLs per platform for improved detection rates
  - Enhanced data extraction with BeautifulSoup parsing
  - Robots.txt compliance checking for ethical scraping
  - User-agent rotation and rate limiting
- **Batch Processing for Intelligence**
  - **Email Batch Analysis**: `email:test@example.com user@domain.com admin@site.com`
  - **Phone Batch Analysis**: `phone:+491234567890 +441234567890 +331234567890`
  - Summary statistics: valid/invalid counts, disposable emails, phone types, countries
  - Compliance checking for each target
  - Formatted output with status icons (✅❌🗑️📱📞)
- **Auto-Query Type Detection**
  - Automatic IP address detection in queries
  - Smart username pattern recognition
  - `ip:` operator support in query parser
  - Seamless integration with existing OSINT operators
- **Documentation Reorganization**
  - **6 organized categories**: getting-started/, guides/, health/, osint/, development/, security/
  - **22 documentation files** properly categorized and cross-linked
  - Improved navigation system across all documentation
  - Centralized documentation index in `docs/README.md`

#### Enhanced
- **Query Parser** (`core/osint/query_parser.py`)
  - Enhanced operator support and parsing logic
  - Improved pattern matching for OSINT queries
- **System Monitor** (`core/health/system_monitor.py`)
  - Enhanced metrics collection
  - Real-time performance tracking
- **CLI Helper** (`utils/cli_helper.py`)
  - Updated examples with batch processing commands

#### Changed
- **OSINT Output**: Enhanced formatting for batch results with summaries
- **Settings Menu**: Reorganized configuration sections
- **Status Command**: Shows comprehensive system statistics
- **Health Dashboard**: Improved layout and metrics display

#### Fixed
- Memory data persistence across sessions
- Batch processing for multiple OSINT targets
- Summary statistics calculation for batch operations

#### Security & Privacy
- **Memory Store File** (`data/memory.json`) added to `.gitignore`
- **Audit Logging**: All memory operations logged
- **Data Export**: JSON export for backup and analysis
- **Configurable Behavior**: Auto-clear option for sensitive data

#### Testing
- **Comprehensive Test Suite** (`tests/test_memory_store.py`)
  - 50+ unit tests covering all operations
  - CRUD operations: remember, recall, forget, clear
  - Search functionality across categories
  - Export/Import operations
  - Persistence verification
  - Edge cases and error handling
  - Singleton pattern validation

## [1.4.0] - 2025-10-25

#### Enhanced
- **OSINT Tool Integration** (`tools/osint_tool.py`)
  - `analyze_ip()` method for direct IP analysis
  - Auto-detection of IP queries without explicit operators
  - Enhanced social media analysis with `analyze_social_username()`
  - Improved error handling for all intelligence types
  - Comprehensive result formatting for agent consumption
- **Social Media Capabilities**
  - Platform-specific data extraction patterns
  - Cross-platform username correlation
  - Enhanced profile validation methods
  - Improved confidence scoring system
- **Agent Integration**
  - All 5 intelligence types available to agent: Email, Phone, Domain, Social, IP
  - Simple interface: `osint_search('ip:8.8.8.8')` or `osint_search('192.168.1.1')`
  - Auto-detection removes need for explicit operators
  - Formatted output optimized for LLM consumption

#### Changed
- **Documentation Structure**: Reorganized from flat structure to categorized folders
- **OSINT Capabilities**: Extended from 3 to 5 intelligence types
- **Social Platform Coverage**: Expanded from 8 to 12 platforms
- **Data Extraction**: Enhanced from basic checks to comprehensive profile analysis

#### Fixed
- **Link Navigation**: Updated all cross-references after documentation reorganization
- **Social Intelligence**: Improved detection accuracy with multiple URL patterns
- **Query Parsing**: Better handling of mixed query types and auto-detection

#### Security & Privacy
- **Ethical Data Collection**: Robots.txt compliance for all web scraping
- **Rate Limiting**: Respectful scraping with configurable delays
- **No API Dependencies**: Privacy-friendly approach without external API requirements
- **Audit Logging**: All OSINT operations logged for compliance

## [1.4.0] - 2025-10-25

### 📚 Documentation & Project Structure

#### Added
- **Comprehensive Compliance Documentation**
  - LICENSE (MIT)
  - CONTRIBUTING.md (PR workflow, coding standards, testing)
  - CODE_OF_CONDUCT.md (Contributor Covenant 2.1)
  - SECURITY.md (Vulnerability reporting via GitHub)
  - CHANGELOG.md (Complete release history)
- **GitHub Templates**
  - Issue templates (Bug Report, Feature Request, Documentation)
  - Pull Request template
  - CODEOWNERS file
- **Release Process Documentation**
  - docs/RELEASE_PROCESS.md (Versioning, workflow, checklists)
  - docs/SECRET_LEAK_RESPONSE.md (Emergency plan for secret leaks)
  - docs/PRE_RELEASE_CHECK.md (Comprehensive release checklist)
- **Project Structure Overhaul**
  - docs/README.md (Central documentation overview)
  - docs/PROJECT_STRUCTURE.md (Detailed directory structure)
  - docs/STRUCTURE_CLEANUP_SUMMARY.md (Cleanup documentation)
- **Navigation System**: All Markdown files equipped with navigation links

#### Changed
- **Root Directory Cleaned Up**: Only 8 essential files (README, LICENSE, CONTRIBUTING, etc.)
- **docs/ Organized**: 19 documentation files logically grouped
- **README Optimized**: Release highlights instead of full version history (→ CHANGELOG.md)
- **.env.example Verified**: Only placeholders, no real secrets
- **.gitignore Extended**: All sensitive files excluded

#### Security
- **Security Audit Completed**
  - Dependency security check (pip-audit)
  - Secret scanning (local + GitHub)
  - Static code analysis documented
  - Branch protection recommended
- **95 of 97 Tests Passed** (2 skipped - integration tests)

### Removed
- INSTALLATION.md, PRE_RELEASE_CHECK.md from root (→ docs/)

## [1.3.0] - 2025-01-24

### 🔧 Code Quality & Performance (Major Release)

#### Added
- **tiktoken Integration**: Accurate token counting instead of chars/4 approximation
- **Retry Logic**: LLM client with tenacity (3x retries, exponential backoff 1-10s)
- **Smart Cache Management**: Configurable max_size_mb (500MB default) with LRU eviction
- **Configurable Startup**: `cache.clear_on_startup` option (default: false, only expired)
- **9 New Tests**: Comprehensive tiktoken integration tests (100% passing)

#### Changed
- **Major Refactoring**: `_query_with_tools()` from 246 → 37 lines (split into 11 focused methods)
  - `_should_use_web_search()`
  - `_execute_web_search()`
  - `_should_use_rag()`
  - `_execute_rag_search()`
  - `_build_context()`
  - `_estimate_tokens()`
  - `_generate_response()`
  - `_handle_search_error()`
  - `_log_query_stats()`
- **Better Maintainability**: Smaller, focused methods for easier maintenance
- **Token Counting**: `estimate_tokens()` now uses tiktoken instead of chars/4

#### Fixed
- Cache overflow with large embeddings due to LRU eviction
- LLM client timeout without retry logic
- Inaccurate token estimation causing context overflow

#### Performance
- **Token Estimation**: 10x more precise than chars/4 method
- **Cache Management**: Automatic cleanup on max_size_mb exceedance
- **Retry Logic**: More robust LLM communication

## [1.2.0] - 2025-01-24

### 🔍 OSINT Features & Health Monitoring

#### Added
- **OSINT Module** (`core/osint/`)
  - Advanced search operators (site:, inurl:, intext:, filetype:, email:, phone:)
  - Email intelligence (validation, MX records, disposable detection, variations)
  - Phone intelligence (validation, carrier lookup, country detection, formatting)
  - AI query enhancement (query variations, operator suggestions, entity detection)
  - Compliance module (rate limiting, terms of use, audit logging)
- **Health Monitoring Dashboard** (`core/health/`)
  - Live system monitor (CPU, RAM, disk, network)
  - Component health checks (LLM, cache, RAG, tools)
  - Performance tracking (response times, throughput, percentiles)
  - Alert system (threshold-based warnings)
  - Rich terminal UI with live updates
- **Interactive Settings Menu**: Category-based configuration (llm, search, rag, cache, osint)
- **Restart Command**: Restart agent without exiting
- **Context Usage Tracker**: Real-time token usage monitoring

#### Changed
- **Max Tokens Increased**: 10,000 → 16,000 for RTX 3080+ GPUs
- **OSINT Configuration**: Configurable max_results, rate_limits for Email/Phone/General
- **Safesearch Quality Filter**: off/moderate/strict for OSINT results

#### Fixed
- OSINT cache reference issue (quelle/source commands)
- Session persistence with OSINT queries
- Email/Phone intelligence errors with empty results

#### Changed
- **Max Tokens**: 10,000 (optimized for RTX 3080+)
- **CLI UX**: Improved user guidance with visual elements

## [1.1.0] - 2025-01-23

### 🚀 Phase 3 & 4: Intelligence + Production

#### Added

##### Multi-Hop Reasoning (LangGraph)
- **LangGraph Agent** (`core/langgraph_agent.py`)
  - 6-node workflow: Router → Initial Search → Analyze → Follow-Up → Synthesize → Critique
  - Configurable confidence threshold & max hops
  - Self-critique loop for quality assurance
- **Parallel Search** (`utils/parallel_search.py`)
  - Multi-aspect searches with ThreadPoolExecutor
  - Entity comparison for complex queries
- **Lazy Loading** (`core/lazy_loader.py`)
  - On-demand loading for tools and plugins
  - Performance optimization

##### Production Features
- **FastAPI REST API** (`app.py`)
  - 8+ endpoints: `/query`, `/plugins`, `/stats`, `/health`, etc.
  - Auto-documentation: Swagger UI + ReDoc
  - Multi-user support with SQLite session management
- **Plugin System** (`core/plugin_manager.py`)
  - Dynamic loading/unloading
  - Metadata support
  - Plugin discovery
- **Enhanced CLI** (`utils/cli_helper.py`)
  - Rich formatting (tables, trees, Markdown)
  - Interactive commands
  - Progress tracking

##### Performance Optimizations
- **Async Operations** (`utils/async_utils.py`)
  - Parallel HTTP requests with aiohttp
  - Batch processing for RAG
- **Resource Monitoring** (`utils/resource_monitor.py`)
  - RAM usage tracking
  - Auto garbage collection
  - Performance metrics
- **RAG Optimizations** (`tools/rag.py`)
  - Batch processing
  - Multi-query search
  - Hybrid search
  - Relevance filtering

#### Changed
- **Setup Scripts**: `setup.bat` / `setup.sh` for automated installation
- **Run Scripts**: `run.bat` / `run.sh` for easy startup
- **Systemd Service**: `crawllama.service` for Linux deployment

#### Documentation
- **Comprehensive Guides**:
  - `docs/LANGGRAPH_GUIDE.md` - Multi-Hop Reasoning
  - `docs/PLUGIN_TUTORIAL.md` - Plugin Development
  - `docs/OSINT_USAGE.md` - OSINT Features
  - `docs/HEALTH_MONITORING.md` - Health Dashboard

## [1.0.0] - 2025-01-22

### 🎉 Initial Production Release

#### Added

##### Core Features
- **Ollama Integration** (`core/llm_client.py`)
  - Local LLM support (qwen3:4b, deepseek-r1:8b, llama3, mistral)
  - Streaming support
  - Retry logic with tenacity
- **Multi-Source Web Search** (`tools/web_search.py`)
  - DuckDuckGo (primary)
  - Brave Search API (fallback)
  - Serper API (fallback)
- **Wikipedia Integration** (`tools/wiki_lookup.py`)
  - German/English support
  - Summary + full-text
- **RAG System** (`tools/rag.py`)
  - ChromaDB + Sentence Transformers
  - Semantic search
  - Document chunking
- **Tool Orchestration** (`core/agent.py`)
  - Automatic tool selection via LLM
  - Context management
  - Session persistence

##### Robustness Features
- **Fallback System** (`core/fallback_manager.py`)
  - Multi-tier fallbacks
  - Automatic provider switching
  - Cache fallback
- **Rate Limiting** (`utils/rate_limiter.py`)
  - Configurable limits
  - robots.txt checks
- **Domain Blacklist** (`utils/domain_blacklist.py`)
  - Malware/spam/tracking filtering
  - Pattern matching
- **Safe Fetch** (`utils/safe_fetch.py`)
  - Timeout handling
  - Proxy support
  - SSL verification
- **Smart Caching** (`core/cache.py`)
  - TTL-based
  - Hash keys
  - Expiry management

##### CLI Features
- **Interactive Mode**
  - Rich formatting
  - History management
  - Session persistence
- **Commands**
  - `clear` - Reset session
  - `stats` - Display statistics
  - `save`/`load` - Save/load session
  - `exit`/`quit` - Exit

#### Testing
- **Comprehensive Test Suite** (`tests/`)
  - Unit tests
  - Integration tests
  - Mocking with pytest-mock
  - 80%+ coverage
- **Test Files**:
  - `test_web_search.py`
  - `test_fallback_manager.py`
  - `test_cache.py`
  - `test_domain_blacklist.py`
  - `test_llm_client.py`
  - `test_integration.py`

#### Configuration
- **config.json**: Central configuration
- **.env Support**: API keys & secrets
- **Flexible Settings**: LLM, Search, RAG, Cache, Security

#### Documentation
- **README.md**: Main documentation
- **INSTALLATION.md**: Installation guide
- **docs/setup.md**: Setup guide
- **docs/QUICKSTART.md**: Quickstart

## [0.1.0] - 2025-01-20

### 🌱 Initial Beta Release

#### Added
- Basic Ollama LLM integration
- Simple web search (DuckDuckGo)
- Basic CLI
- Simple caching
- Project structure setup

---

## Release Type Definitions

- **Major (X.0.0)**: Breaking changes, major new features
- **Minor (x.X.0)**: New features (backward-compatible)
- **Patch (x.x.X)**: Bug fixes, minor improvements

## Changelog Categories

- **Added**: New features
- **Changed**: Changes to existing features
- **Deprecated**: Features to be removed soon
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security fixes

[Unreleased]: https://github.com/arn-c0de/Crawllama/compare/v1.4.2...HEAD
[1.4.2]: https://github.com/arn-c0de/Crawllama/compare/v1.4.1...v1.4.2
[1.4.1]: https://github.com/arn-c0de/Crawllama/compare/v1.4.0...v1.4.1
[1.4.0]: https://github.com/arn-c0de/Crawllama/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/arn-c0de/Crawllama/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/arn-c0de/Crawllama/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/arn-c0de/Crawllama/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/arn-c0de/Crawllama/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/arn-c0de/Crawllama/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/arn-c0de/Crawllama/releases/tag/v0.1.0
