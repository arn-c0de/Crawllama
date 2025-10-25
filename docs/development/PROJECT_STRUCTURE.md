# 📁 Projekt-Struktur

## Root-Verzeichnis (Aufgeräumt)

```
Crawllama/
├── 📄 README.md                    # Hauptdokumentation - START HIER!
├── 📜 LICENSE                      # MIT License
├── 🤝 CONTRIBUTING.md              # Contribution Guidelines
├── 👥 CODE_OF_CONDUCT.md           # Community Verhaltenskodex
├── 🔒 SECURITY.md                  # Security Policy
├── 📝 CHANGELOG.md                 # Release History
│
├── ⚙️ config.json                   # Hauptkonfiguration
├── 📦 requirements.txt             # Python Dependencies
├── 🔐 .env.example                 # Environment-Variablen Beispiel
├── 🚫 .gitignore                   # Git Ignore Rules
├── 🧪 pytest.ini                   # Test Configuration
│
├── 🐍 main.py                      # CLI Entry Point
├── 🌐 app.py                       # FastAPI Server
├── 🏥 health-dashboard.py          # Health Monitoring Dashboard
│
├── 📂 docs/                        # ALLE Dokumentation (siehe unten)
├── 📂 core/                        # Core-Logik (Agent, LLM, Cache, etc.)
├── 📂 tools/                       # Tools (Search, RAG, OSINT, etc.)
├── 📂 utils/                       # Utilities (Logger, Validators, etc.)
├── 📂 plugins/                     # Plugin-System
├── 📂 tests/                       # Test-Suite
├── 📂 data/                        # Daten & Cache
├── 📂 logs/                        # Log-Dateien
├── 📂 scripts/                     # Utility Scripts
├── 📂 config/                      # Zusätzliche Configs
└── 📂 .github/                     # GitHub Templates & Workflows
```

## 📚 docs/ - Dokumentations-Verzeichnis

```
docs/
├── 📖 README.md                    # Dokumentations-Übersicht (Navigation)
│
├── 🚀 Schnellstart & Installation
│   ├── QUICKSTART.md               # 5-Minuten Schnellstart
│   └── INSTALLATION.md             # Detaillierte Installation
│
├── 📘 Feature-Guides
│   ├── LANGGRAPH_GUIDE.md          # Multi-Hop-Reasoning
│   ├── OSINT_USAGE.md              # OSINT Features
│   ├── OSINT_CONTEXT_USAGE.md      # OSINT Context Usage
│   ├── SOCIAL_INTELLIGENCE.md      # Social Intelligence
│   ├── PLUGIN_TUTORIAL.md          # Plugin-Entwicklung
│   ├── HALLUCINATION_DETECTION.md  # Hallucination Detection
│   └── SEARCH_LIMITATIONS.md       # Search Limitierungen
│
├── 🏥 Health Monitoring
│   ├── HEALTH_MONITORING.md        # Health System
│   ├── HEALTH_DASHBOARD.md         # Dashboard Usage
│   ├── HEALTH_FEATURES.md          # Verfügbare Features
│   └── DASHBOARD_STARTER.md        # Dashboard Starter
│
└── 🔧 Maintainer-Docs
    ├── RELEASE_PROCESS.md          # Release-Workflow
    ├── SECRET_LEAK_RESPONSE.md     # Secret-Leak Notfallplan
    ├── PRE_RELEASE_CHECK.md        # Pre-Release Checklist
    └── preuploadchecklist.txt      # Upload-Checklist
```

## 🏗️ Code-Struktur

### core/ - Kern-Module

```
core/
├── agent.py                        # Standard-Agent
├── langgraph_agent.py              # Multi-Hop-Agent
├── llm_client.py                   # Ollama-Client
├── context_manager.py              # Token-Management
├── cache.py                        # Smart-Cache
├── session_manager.py              # Multi-User Sessions
├── plugin_manager.py               # Plugin-System
├── fallback_manager.py             # Fallback-Logic
├── registry.py                     # Tool-Registry
├── robustness.py                   # Robustness-Features
├── hallu_detect.py                 # Hallucination Detection
├── lazy_loader.py                  # Lazy-Loading
├── unified_loader.py               # Unified Loader
│
├── health/                         # Health Monitoring
│   ├── system_monitor.py           # System-Metriken
│   ├── component_checker.py        # Component Health
│   ├── performance_tracker.py      # Performance Tracking
│   ├── alert_system.py             # Alert System
│   ├── dashboard.py                # Dashboard Logic
│   ├── rich_dashboard.py           # Rich Terminal UI
│   └── ...
│
└── osint/                          # OSINT Module
    ├── query_parser.py             # Advanced Search Operators
    ├── email_intel.py              # Email Intelligence
    ├── phone_intel.py              # Phone Intelligence
    ├── query_enhancer.py           # AI Query Enhancement
    └── compliance.py               # Compliance & Rate Limiting
```

### tools/ - Modulare Tools

```
tools/
├── web_search.py                   # Multi-Source Web-Suche
├── wiki_lookup.py                  # Wikipedia Integration
├── page_reader.py                  # HTML-Parser
├── rag.py                          # RAG-System (ChromaDB)
├── osint_tool.py                   # OSINT Tool Integration
└── tool_registry.py                # Tool-Verwaltung
```

### utils/ - Hilfsfunktionen

```
utils/
├── logger.py                       # Strukturiertes Logging
├── validators.py                   # Input-Validation
├── retry.py                        # Retry-Logic (tenacity)
├── safe_fetch.py                   # Sicheres HTTP
├── rate_limiter.py                 # Rate-Limiting
├── domain_blacklist.py             # Domain-Filter
├── async_utils.py                  # Async-Operations
├── parallel_search.py              # Parallelisierung
├── resource_monitor.py             # RAM/Performance
├── cli_helper.py                   # Enhanced CLI
├── text_cleaner.py                 # Text Cleaning
└── secure_config.py                # Verschlüsselte Config
```

### tests/ - Test-Suite

```
tests/
├── test_cache.py                   # Cache Tests
├── test_llm_client.py              # LLM-Client Tests
├── test_web_search.py              # Web-Search Tests
├── test_osint.py                   # OSINT Tests
├── test_multihop_reasoning.py      # Multi-Hop Tests
├── test_health_monitoring.py       # Health Tests
├── test_integration.py             # Integration Tests
└── ...                             # 15+ Test-Dateien
```

## 📦 data/ - Daten-Verzeichnis

```
data/
├── blacklist.txt                   # Domain-Blacklist
├── cache/                          # Web-Cache (TTL-basiert)
├── embeddings/                     # ChromaDB Embeddings
├── test_embeddings/                # Test Embeddings
├── history/                        # Session History
├── models/                         # Modell-Dateien
└── osint_logs/                     # OSINT Audit Logs
```

## 🔧 .github/ - GitHub Configuration

```
.github/
├── ISSUE_TEMPLATE/                 # Issue Templates
│   ├── bug_report.yml              # Bug Report
│   ├── feature_request.yml         # Feature Request
│   └── documentation.yml           # Documentation Issue
├── pull_request_template.md        # PR Template
└── CODEOWNERS                      # Code Ownership
```

## 🚀 Scripts - Setup & Ausführung

```
├── setup.bat / setup.sh            # Automatische Installation
├── run.bat / run.sh                # Agent starten
├── health-dashboard.bat/.sh        # Health Dashboard starten
└── scripts/
    ├── debug_ddgs.py               # DuckDuckGo Debug
    ├── extract_all_functions.py    # Function Extractor
    └── ...
```

## 📊 Metrics

| Kategorie | Anzahl | Beschreibung |
|-----------|--------|--------------|
| **Core-Module** | 15+ | Kern-Funktionalität |
| **Tools** | 6+ | Modulare Tools |
| **Utils** | 12+ | Hilfsfunktionen |
| **Tests** | 97 | Test-Cases |
| **Docs** | 18+ | Dokumentations-Dateien |
| **LOC** | ~15,000+ | Lines of Code |

## 🗺️ Navigation

- **Für Benutzer**: Start bei [README.md](../README.md) → [QUICKSTART.md](QUICKSTART.md)
- **Für Entwickler**: [CONTRIBUTING.md](../CONTRIBUTING.md) → [docs/README.md](README.md)
- **Für Maintainer**: [RELEASE_PROCESS.md](RELEASE_PROCESS.md) → [PRE_RELEASE_CHECK.md](PRE_RELEASE_CHECK.md)

---

**Zurück zur [Hauptseite](../README.md)** | **[Dokumentations-Übersicht](README.md)**
