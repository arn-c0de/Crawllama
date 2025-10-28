# 📁 Project Structure

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🔄 Release Process](RELEASE_PROCESS.md) | [✅ Pre-Release Check](PRE_RELEASE_CHECK.md) | [🤝 Contributing](../../CONTRIBUTING.md)

---

## Root Directory (Organized)

```
Crawllama/
├── 📄 README.md                    # Main documentation - START HERE!
├── 📜 LICENSE                      # MIT License
├── 🤝 CONTRIBUTING.md              # Contribution guidelines
├── 👥 CODE_OF_CONDUCT.md           # Community code of conduct
├── 🔒 SECURITY.md                  # Security policy
├── 📝 CHANGELOG.md                 # Release history
│
├── ⚙️ config.json                   # Main configuration
├── 📦 requirements.txt             # Python dependencies
├── 🔐 .env.example                 # Environment variables example
├── 🚫 .gitignore                   # Git ignore rules
├── 🧪 pytest.ini                   # Test configuration
│
├── 🐍 main.py                      # CLI entry point
├── 🌐 app.py                       # FastAPI server
├── 🏥 health-dashboard.py          # Health monitoring dashboard
│
├── 📂 docs/                        # ALL documentation (see below)
├── 📂 core/                        # Core logic (Agent, LLM, Cache, etc.)
├── 📂 tools/                       # Tools (Search, RAG, OSINT, etc.)
├── 📂 utils/                       # Utilities (Logger, Validators, etc.)
├── 📂 plugins/                     # Plugin system
├── 📂 tests/                       # Test suite
├── 📂 data/                        # Data & cache
├── 📂 logs/                        # Log files
├── 📂 scripts/                     # Utility scripts
├── 📂 config/                      # Additional configs
└── 📂 .github/                     # GitHub templates & workflows
```

## 📚 docs/ - Documentation Directory

```
docs/
├── 📖 README.md                    # Documentation overview (Navigation)
│
├── 🚀 Quick Start & Installation
│   ├── QUICKSTART.md               # 5-minute quick start
│   └── INSTALLATION.md             # Detailed installation
│
├── 🤖 Adaptive Agent System (NEW v1.4.4)
│   ├── ADAPTIVE_HOPS.md            # 🆕 Complete adaptive system documentation
│   └── ADAPTIVE_HOPS_QUICKSTART.md # 🆕 3-step integration guide
│
├── 📘 Feature Guides
│   ├── API_USAGE.md                # REST API documentation
│   ├── LANGGRAPH_GUIDE.md          # Multi-hop reasoning
│   ├── OSINT_USAGE.md              # OSINT features
│   ├── OSINT_CONTEXT_USAGE.md      # OSINT context usage
│   ├── SOCIAL_INTELLIGENCE.md      # Social intelligence
│   ├── PLUGIN_TUTORIAL.md          # Plugin development
│   ├── HALLUCINATION_DETECTION.md  # Hallucination detection
│   └── SEARCH_LIMITATIONS.md       # Search limitations
│
├── 🏥 Health Monitoring
│   ├── HEALTH_MONITORING.md        # Health system
│   ├── HEALTH_DASHBOARD.md         # Dashboard usage
│   ├── HEALTH_FEATURES.md          # Available features
│   └── DASHBOARD_STARTER.md        # Dashboard starter
│
└── 🔧 Development & Security
    ├── development/
    │   └── PROJECT_STRUCTURE.md    # This document
    └── security/
        ├── SECRET_LEAK_RESPONSE.md # Secret leak emergency plan
        └── CODEQL_SECURITY_ANALYSIS.md # Security analysis
```

## 🏗️ Code Structure

### core/ - Core Modules

```
core/
├── agent.py                        # Standard agent
├── adaptive_hops.py                # 🆕 v1.4.4: Adaptive complexity detection & agent selection
├── adaptive_integration.py         # 🆕 v1.4.4: AdaptiveQueryProcessor integration layer
├── langgraph_agent.py              # Multi-hop agent
├── llm_client.py                   # Ollama client
├── context_manager.py              # Token management
├── cache.py                        # Smart cache
├── session_manager.py              # Multi-user sessions
├── plugin_manager.py               # Plugin system
├── fallback_manager.py             # Fallback logic
├── registry.py                     # Tool registry
├── robustness.py                   # Robustness features
├── hallu_detect.py                 # Hallucination detection
├── lazy_loader.py                  # Lazy loading
├── unified_loader.py               # Unified loader
│
├── health/                         # Health monitoring
│   ├── system_monitor.py           # System metrics
│   ├── component_checker.py        # Component health
│   ├── performance_tracker.py      # Performance tracking
│   ├── alert_system.py             # Alert system
│   ├── dashboard.py                # Dashboard logic
│   ├── rich_dashboard.py           # Rich terminal UI
│   └── ...
│
└── osint/                          # OSINT modules
    ├── query_parser.py             # Advanced search operators
    ├── email_intel.py              # Email intelligence
    ├── phone_intel.py              # Phone intelligence
    ├── query_enhancer.py           # AI query enhancement
    └── compliance.py               # Compliance & rate limiting
```

### tools/ - Modular Tools

```
tools/
├── web_search.py                   # Multi-source web search
├── wiki_lookup.py                  # Wikipedia integration
├── page_reader.py                  # HTML parser
├── rag.py                          # RAG system (ChromaDB)
├── osint_tool.py                   # OSINT tool integration
└── tool_registry.py                # Tool management
```

### utils/ - Utility Functions

```
utils/
├── logger.py                       # Structured logging
├── validators.py                   # Input validation
├── retry.py                        # Retry logic (tenacity)
├── safe_fetch.py                   # Safe HTTP
├── rate_limiter.py                 # Rate limiting
├── domain_blacklist.py             # Domain filter
├── async_utils.py                  # Async operations
├── parallel_search.py              # Parallelization
├── resource_monitor.py             # RAM/performance
├── cli_helper.py                   # Enhanced CLI
├── text_cleaner.py                 # Text cleaning
└── secure_config.py                # Encrypted config
```

### tests/ - Test Suite

```
tests/
├── unit/
│   ├── test_adaptive_hops.py       # 🆕 v1.4.4: Adaptive system unit tests (30 tests)
│   ├── test_cache.py               # Cache tests
│   ├── test_llm_client.py          # LLM client tests
│   └── test_memory_store.py        # Memory store tests
├── integration/
│   ├── test_adaptive_integration.py # 🆕 v1.4.4: End-to-end adaptive tests (16 tests)
│   └── test_integration.py         # General integration tests
├── osint/                          # OSINT-specific tests
├── security/                       # Security tests
├── multihop/                       # Multi-hop reasoning tests
├── robustness/                     # Robustness tests
├── quality/                        # Quality tests
└── other/                          # Other specialized tests
```

## 📦 data/ - Data Directory

```
data/
├── blacklist.txt                   # Domain blacklist
├── cache/                          # Web cache (TTL-based)
├── embeddings/                     # ChromaDB embeddings
├── test_embeddings/                # Test embeddings
├── history/                        # Session history
├── models/                         # Model files
└── osint_logs/                     # OSINT audit logs
```

## 🔧 .github/ - GitHub Configuration

```
.github/
├── ISSUE_TEMPLATE/                 # Issue templates
│   ├── bug_report.yml              # Bug report
│   ├── feature_request.yml         # Feature request
│   └── documentation.yml           # Documentation issue
├── pull_request_template.md        # PR template
└── CODEOWNERS                      # Code ownership
```

## 🚀 Scripts - Setup & Execution

```
├── setup.bat / setup.sh            # Automatic installation
├── run.bat / run.sh                # Start agent
├── health-dashboard.bat/.sh        # Start health dashboard
└── scripts/
    ├── debug_ddgs.py               # DuckDuckGo debug
    ├── extract_all_functions.py    # Function extractor
    └── ...
```

## 🆕 New in v1.4.4: Adaptive Agent Hopping System

### Key Additions:
- **`core/adaptive_hops.py`** (465 lines): Complexity detection, resource monitoring, escalation logic
- **`core/adaptive_integration.py`** (319 lines): Integration layer, confidence estimation, orchestration
- **`docs/ADAPTIVE_HOPS.md`** (1000+ lines): Complete system documentation with API reference
- **`docs/ADAPTIVE_HOPS_QUICKSTART.md`**: 3-step integration guide
- **46 new tests**: 30 unit + 16 integration tests covering all adaptive scenarios

### Features:
- 🎯 **Automatic Complexity Detection**: Multi-factor analysis (LLM + heuristics)
- 🔄 **Intelligent Agent Selection**: SearchAgent for simple, MultiHopAgent for complex queries
- 📈 **Confidence-Based Escalation**: Automatic upgrade when confidence < 0.5
- ⚡ **Resource Monitoring**: Dynamic adaptation under CPU/memory load
- 🌐 **REST API Integration**: New `/query-adaptive` endpoint with full metadata

## 📊 Metrics

| Category | Count | Description |
|-----------|--------|--------------|
| **Core Modules** | 17+ | Core functionality (incl. adaptive system) |
| **Tools** | 6+ | Modular tools |
| **Utils** | 12+ | Utility functions |
| **Tests** | 143+ | Test cases (97 existing + 46 adaptive) |
| **Docs** | 22+ | Documentation files (incl. adaptive docs) |
| **LOC** | ~16,000+ | Lines of code (incl. adaptive system) |

## 🗺️ Navigation

- **For Users**: Start at [README.md](../README.md) → [QUICKSTART.md](QUICKSTART.md)
- **For Developers**: [CONTRIBUTING.md](../CONTRIBUTING.md) → [docs/README.md](README.md)
- **For Maintainers**: [RELEASE_PROCESS.md](RELEASE_PROCESS.md) → [PRE_RELEASE_CHECK.md](PRE_RELEASE_CHECK.md)

---

**Back to [Main Page](../README.md)** | **[Documentation Overview](README.md)**
