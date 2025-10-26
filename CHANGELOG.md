# Changelog

---

📚 **Navigation:** [README](README.md) | [Contributing](CONTRIBUTING.md) | [Security](SECURITY.md) | [Docs](docs/README.md)

---

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/),
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## [Unreleased]

### Geplant
- GUI mit Streamlit/Gradio
- GraphQL API
- Redis-Cache für Production
- Multi-Language Support (English)
- Voice-Interface

## [1.4.2] - 2025-10-26

### �️ Security Hardening & DoS Protection (Production-Ready)

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
  - **Per-user tracking** with API key hashing (SHA256)
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
  - SHA256 hashing for API keys in logs (prevents exposure)
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
  - German language support: "vergesse email:test@test.de"
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
  - Natural language support: "Merke dir alle E-Mails aus Quelle [1]"

#### Fixed
- **OSINT Query Parser Priority**
  - Memory operators (forget, remember, recall) now parsed FIRST
  - Prevents conflicts with email:/phone:/ip: operators
  - Fixed: `forget email:test@test.de` no longer misinterpreted as email lookup
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
- **Vollständige Compliance-Dokumentation**
  - LICENSE (MIT)
  - CONTRIBUTING.md (PR-Workflow, Coding Standards, Testing)
  - CODE_OF_CONDUCT.md (Contributor Covenant 2.1)
  - SECURITY.md (Vulnerability Reporting via GitHub)
  - CHANGELOG.md (Vollständige Release History)
- **GitHub Templates**
  - Issue Templates (Bug Report, Feature Request, Documentation)
  - Pull Request Template
  - CODEOWNERS File
- **Release-Prozess Dokumentation**
  - docs/RELEASE_PROCESS.md (Versionierung, Workflow, Checklists)
  - docs/SECRET_LEAK_RESPONSE.md (Notfallplan für Secret-Leaks)
  - docs/PRE_RELEASE_CHECK.md (Umfassende Release-Checkliste)
- **Projekt-Struktur Überarbeitung**
  - docs/README.md (Zentrale Dokumentations-Übersicht)
  - docs/PROJECT_STRUCTURE.md (Detaillierte Verzeichnis-Struktur)
  - docs/STRUCTURE_CLEANUP_SUMMARY.md (Cleanup-Dokumentation)
- **Navigation System**: Alle Markdown-Dateien mit Navigation-Links versehen

#### Changed
- **Root-Verzeichnis aufgeräumt**: Nur noch 8 essenzielle Dateien (README, LICENSE, CONTRIBUTING, etc.)
- **docs/ organisiert**: 19 Dokumentationsdateien logisch gruppiert
- **README optimiert**: Release-Highlights statt vollständiger Versionshistorie (→ CHANGELOG.md)
- **.env.example verifiziert**: Nur Platzhalter, keine echten Secrets
- **.gitignore erweitert**: Alle sensitiven Dateien ausgeschlossen

#### Security
- **Security Audit abgeschlossen**
  - Dependency Security Check (pip-audit)
  - Secret Scanning (lokal + GitHub)
  - Static Code Analysis dokumentiert
  - Branch Protection empfohlen
- **95 von 97 Tests bestanden** (2 skipped - Integration Tests)

### Removed
- INSTALLATION.md, PRE_RELEASE_CHECK.md aus Root (→ docs/)

## [1.3.0] - 2025-01-24

### 🔧 Code Quality & Performance (Major Release)

#### Added
- **tiktoken Integration**: Akkurate Token-Zählung statt chars/4 Approximation
- **Retry Logic**: LLM-Client mit tenacity (3x Retries, exponential backoff 1-10s)
- **Smart Cache Management**: Konfigurierbare max_size_mb (500MB default) mit LRU-Eviction
- **Configurable Startup**: `cache.clear_on_startup` Option (default: false, nur expired)
- **9 New Tests**: Comprehensive tiktoken integration tests (100% passing)

#### Changed
- **Major Refactoring**: `_query_with_tools()` von 246 → 37 Zeilen (aufgeteilt in 11 fokussierte Methoden)
  - `_should_use_web_search()`
  - `_execute_web_search()`
  - `_should_use_rag()`
  - `_execute_rag_search()`
  - `_build_context()`
  - `_estimate_tokens()`
  - `_generate_response()`
  - `_handle_search_error()`
  - `_log_query_stats()`
- **Better Maintainability**: Kleinere, fokussierte Methoden für einfachere Wartung
- **Token Counting**: `estimate_tokens()` nutzt jetzt tiktoken statt chars/4

#### Fixed
- Cache-Overflow bei großen Embeddings durch LRU-Eviction
- LLM-Client Timeout ohne Retry-Logic
- Ungenaue Token-Schätzung führte zu Context-Overflow

#### Performance
- **Token Estimation**: 10x präziser als chars/4 Methode
- **Cache Management**: Automatisches Cleanup bei max_size_mb Überschreitung
- **Retry Logic**: Robustere LLM-Kommunikation

## [1.2.0] - 2025-01-24

### 🔍 OSINT Features & Health Monitoring

#### Added
- **OSINT Module** (`core/osint/`)
  - Advanced Search Operators (site:, inurl:, intext:, filetype:, email:, phone:)
  - Email Intelligence (Validation, MX Records, Disposable Detection, Variations)
  - Phone Intelligence (Validation, Carrier Lookup, Country Detection, Formatting)
  - AI Query Enhancement (Query Variations, Operator Suggestions, Entity Detection)
  - Compliance Module (Rate Limiting, Terms of Use, Audit Logging)
- **Health Monitoring Dashboard** (`core/health/`)
  - Live System Monitor (CPU, RAM, Disk, Network)
  - Component Health Checks (LLM, Cache, RAG, Tools)
  - Performance Tracking (Response Times, Throughput, Percentiles)
  - Alert System (Threshold-based Warnings)
  - Rich Terminal UI mit Live-Updates
- **Interactive Settings Menu**: Kategorie-basierte Konfiguration (llm, search, rag, cache, osint)
- **Restart Command**: Agent neu starten ohne Exit
- **Context Usage Tracker**: Echtzeit-Token-Verbrauchsüberwachung

#### Changed
- **Max Tokens erhöht**: 10,000 → 16,000 für RTX 3080+ GPUs
- **OSINT Configuration**: Konfigurierbare max_results, rate_limits für Email/Phone/General
- **Safesearch Quality Filter**: off/moderate/strict für OSINT-Ergebnisse

#### Fixed
- OSINT Cache-Referenz-Problem (quelle/source commands)
- Session-Persistence bei OSINT-Queries
- Email/Phone Intelligence-Fehler bei leeren Ergebnissen

#### Changed
- **Max Tokens**: 10,000 (optimiert für RTX 3080+)
- **CLI UX**: Verbesserte Benutzerführung mit visuellen Elementen

## [1.1.0] - 2025-01-23

### 🚀 Phase 3 & 4: Intelligence + Production

#### Added

##### Multi-Hop-Reasoning (LangGraph)
- **LangGraph Agent** (`core/langgraph_agent.py`)
  - 6-Node-Workflow: Router → Initial Search → Analyze → Follow-Up → Synthesize → Critique
  - Konfigurierbarer Confidence-Threshold & Max-Hops
  - Self-Critique Loop für Qualitätssicherung
- **Parallel Search** (`utils/parallel_search.py`)
  - Multi-Aspect-Searches mit ThreadPoolExecutor
  - Entity-Comparison für komplexe Queries
- **Lazy Loading** (`core/lazy_loader.py`)
  - On-Demand-Loading für Tools und Plugins
  - Performance-Optimierung

##### Production Features
- **FastAPI REST API** (`app.py`)
  - 8+ Endpunkte: `/query`, `/plugins`, `/stats`, `/health`, etc.
  - Auto-Dokumentation: Swagger UI + ReDoc
  - Multi-User-Support mit SQLite Session-Management
- **Plugin-System** (`core/plugin_manager.py`)
  - Dynamisches Laden/Entladen
  - Metadata-Support
  - Plugin-Discovery
- **Enhanced CLI** (`utils/cli_helper.py`)
  - Rich-Formatting (Tabellen, Trees, Markdown)
  - Interaktive Befehle
  - Progress-Tracking

##### Performance Optimizations
- **Async Operations** (`utils/async_utils.py`)
  - Parallele HTTP-Requests mit aiohttp
  - Batch-Processing für RAG
- **Resource Monitoring** (`utils/resource_monitor.py`)
  - RAM-Usage Tracking
  - Auto-Garbage-Collection
  - Performance-Metriken
- **RAG Optimizations** (`tools/rag.py`)
  - Batch-Processing
  - Multi-Query-Search
  - Hybrid-Search
  - Relevance-Filtering

#### Changed
- **Setup-Scripts**: `setup.bat` / `setup.sh` für automatische Installation
- **Run-Scripts**: `run.bat` / `run.sh` für einfachen Start
- **Systemd-Service**: `crawllama.service` für Linux-Deployment

#### Documentation
- **Comprehensive Guides**:
  - `docs/LANGGRAPH_GUIDE.md` - Multi-Hop-Reasoning
  - `docs/PLUGIN_TUTORIAL.md` - Plugin-Entwicklung
  - `docs/OSINT_USAGE.md` - OSINT-Features
  - `docs/HEALTH_MONITORING.md` - Health-Dashboard

## [1.0.0] - 2025-01-22

### 🎉 Initial Production Release

#### Added

##### Core Features
- **Ollama Integration** (`core/llm_client.py`)
  - Local LLM Support (qwen3:4b, deepseek-r1:8b, llama3, mistral)
  - Streaming-Support
  - Retry-Logic mit tenacity
- **Multi-Source Web Search** (`tools/web_search.py`)
  - DuckDuckGo (primary)
  - Brave Search API (fallback)
  - Serper API (fallback)
- **Wikipedia Integration** (`tools/wiki_lookup.py`)
  - Deutsch/Englisch Support
  - Summary + Full-Text
- **RAG System** (`tools/rag.py`)
  - ChromaDB + Sentence Transformers
  - Semantic Search
  - Document Chunking
- **Tool Orchestration** (`core/agent.py`)
  - Automatische Tool-Auswahl per LLM
  - Context-Management
  - Session-Persistence

##### Robustness Features
- **Fallback System** (`core/fallback_manager.py`)
  - Multi-Tier Fallbacks
  - Automatic Provider-Switching
  - Cache-Fallback
- **Rate Limiting** (`utils/rate_limiter.py`)
  - Configurable Limits
  - robots.txt Checks
- **Domain Blacklist** (`utils/domain_blacklist.py`)
  - Malware/Spam/Tracking Filtering
  - Pattern-Matching
- **Safe Fetch** (`utils/safe_fetch.py`)
  - Timeout-Handling
  - Proxy-Support
  - SSL-Verification
- **Smart Caching** (`core/cache.py`)
  - TTL-basiert
  - Hash-Keys
  - Expiry-Management

##### CLI Features
- **Interactive Mode**
  - Rich-Formatierung
  - History-Management
  - Session-Persistence
- **Commands**
  - `clear` - Session zurücksetzen
  - `stats` - Statistiken anzeigen
  - `save`/`load` - Session speichern/laden
  - `exit`/`quit` - Beenden

#### Testing
- **Comprehensive Test Suite** (`tests/`)
  - Unit Tests
  - Integration Tests
  - Mocking mit pytest-mock
  - 80%+ Coverage
- **Test Files**:
  - `test_web_search.py`
  - `test_fallback_manager.py`
  - `test_cache.py`
  - `test_domain_blacklist.py`
  - `test_llm_client.py`
  - `test_integration.py`

#### Configuration
- **config.json**: Zentrale Konfiguration
- **.env Support**: API-Keys & Secrets
- **Flexible Settings**: LLM, Search, RAG, Cache, Security

#### Documentation
- **README.md**: Hauptdokumentation
- **INSTALLATION.md**: Installationsanleitung
- **docs/setup.md**: Setup-Guide
- **docs/QUICKSTART.md**: Schnellstart

## [0.1.0] - 2025-01-20

### 🌱 Initial Beta Release

#### Added
- Basic Ollama LLM Integration
- Simple Web Search (DuckDuckGo)
- Basic CLI
- Simple Caching
- Project Structure Setup

---

## Release-Typ-Definitionen

- **Major (X.0.0)**: Breaking Changes, große neue Features
- **Minor (x.X.0)**: Neue Features (backward-compatible)
- **Patch (x.x.X)**: Bug-Fixes, kleine Verbesserungen

## Changelog-Kategorien

- **Added**: Neue Features
- **Changed**: Änderungen an existierenden Features
- **Deprecated**: Features, die bald entfernt werden
- **Removed**: Entfernte Features
- **Fixed**: Bug-Fixes
- **Security**: Sicherheits-Fixes

[Unreleased]: https://github.com/arn-c0de/Crawllama/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/arn-c0de/Crawllama/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/arn-c0de/Crawllama/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/arn-c0de/Crawllama/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/arn-c0de/Crawllama/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/arn-c0de/Crawllama/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/arn-c0de/Crawllama/releases/tag/v0.1.0
