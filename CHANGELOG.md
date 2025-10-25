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
  - [docs/development/RELEASE_PROCESS.md](docs/development/RELEASE_PROCESS.md) (Versionierung, Workflow, Checklists)
  - [docs/development/SECRET_LEAK_RESPONSE.md](docs/development/SECRET_LEAK_RESPONSE.md) (Notfallplan für Secret-Leaks)
  - [docs/development/PRE_RELEASE_CHECK.md](docs/development/PRE_RELEASE_CHECK.md) (Umfassende Release-Checkliste)
- **Projekt-Struktur Überarbeitung**
  - [docs/README.md](docs/README.md) (Zentrale Dokumentations-Übersicht)
  - [docs/development/PROJECT_STRUCTURE.md](docs/development/PROJECT_STRUCTURE.md) (Detaillierte Verzeichnis-Struktur)
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
  - Local LLM Support (qwen2.5:3b, deepseek-r1:8b, llama3, mistral)
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
