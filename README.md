# CrawlLama 🦙

**Production-Ready AI Research Agent mit Multi-Hop Reasoning**

Ein vollständig lokales, produktionsreifes KI-System mit erweiterten Intelligence-Features:
- 🧠 **Multi-Hop-Reasoning** mit LangGraph für komplexe Fragen
- 🚀 **REST API** mit FastAPI für Integration
- 🔌 **Plugin-System** für einfache Erweiterbarkeit
- 🐳 **Docker-Ready** für schnelles Deployment
- 📊 **Multi-User-Support** mit Session-Management
- ⚡ **Performance-Optimierungen** (Async, Parallelisierung, RAM-Monitoring)

## ✨ Features

### 🎯 Core Features
- 🔒 **100% Lokal** - Keine Cloud-Abhängigkeit, volle Datenkontrolle
- 🌐 **Multi-Source Web-Suche** - DuckDuckGo, Brave Search, Serper API mit Fallback
- 📚 **Wikipedia Integration** - Dedizierte Wikipedia-Suche (Deutsch/Englisch)
- 🧠 **Advanced RAG-System** - Batch-Processing, Multi-Query, Hybrid-Search
- 💾 **Intelligentes Caching** - TTL-basiert mit Hash-Keys
- 🎯 **Tool-Orchestrierung** - Automatische Tool-Auswahl per LLM

### 🚀 Phase 3: Intelligence (NEW in v1.1)
- 🔄 **Multi-Hop-Reasoning** - LangGraph-basierter Agent mit 6-Node-Workflow
  - Router → Initial Search → Analyze → Follow-Up → Synthesize → Critique
  - Konfigurierbarer Confidence-Threshold & Max-Hops
  - Self-Critique Loop für Qualitätssicherung
- ⚡ **Parallelisierung** - Multi-Aspect-Searches mit ThreadPoolExecutor
- 🔌 **Lazy-Loading** - On-Demand-Loading für Tools und Plugins
- 🌐 **Async Operations** - Parallele HTTP-Requests mit aiohttp
- 📊 **Resource Monitoring** - RAM-Usage, Performance-Tracking, Auto-GC

### 🏗️ Phase 4: Production (NEW in v1.1)
- 🌐 **FastAPI REST API** - 8+ Endpunkte mit Auto-Dokumentation
  - `/query` - Query-Processing (Standard & Multi-Hop)
  - `/plugins` - Plugin-Management
  - `/stats` - System-Statistiken
  - `/health` - Health-Check
- 👥 **Multi-User-Support** - SQLite-basiertes Session-Management
- 🔌 **Plugin-System** - Dynamisches Laden/Entladen von Plugins
- 🎨 **Enhanced CLI** - Rich-Formatting, Tabellen, Trees, Markdown
- 🐳 **Docker-Deployment** - Dockerfile + docker-compose.yml
- 🔧 **Setup-Scripts** - setup.bat, setup.sh mit Auto-Configuration
- 📖 **Comprehensive Docs** - LangGraph-Guide, Plugin-Tutorial

### 🔒 Security & Robustness
- ✅ **Domain Blacklist** - Schutz vor unerwünschten Domains
- ⏱️ **Rate Limiting** - 1 Request/Sekunde + robots.txt-Checks
- 🔄 **Retry Logic** - Exponential Backoff mit tenacity
- 🛡️ **Fallback-System** - Automatische Fallbacks bei API-Ausfällen
- 🔐 **Secure Config** - Verschlüsselte API-Key-Speicherung
- 🔍 **Output Validation** - Sanitization von LLM-Ausgaben

## 🚀 Schnellstart

### Option 1: Setup-Scripts (Empfohlen)

**Windows:**
```cmd
setup.bat
```

**Linux/macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

Das Setup-Script:
- ✅ Prüft Python-Version (3.10+)
- ✅ Erstellt virtuelles Environment
- ✅ Installiert alle Dependencies
- ✅ Erstellt notwendige Verzeichnisse
- ✅ Kopiert .env.example → .env
- ✅ Prüft Ollama-Status

### Option 2: Docker (Production)

```bash
# Mit Ollama im Container
docker-compose up -d

# API verfügbar auf http://localhost:8000
# Ollama verfügbar auf http://localhost:11434
```

### Option 3: Manuelle Installation

```bash
# 1. Klonen
git clone https://github.com/arn-c0de/Crawllama.git
cd Crawllama

# 2. Virtual Environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# 3. Dependencies
pip install -r requirements.txt

# 4. Directories
mkdir -p data/cache data/embeddings data/history logs plugins

# 5. Config
cp .env.example .env
```

### Ollama Setup

```bash
# Ollama installieren
curl -fsSL https://ollama.ai/install.sh | sh  # Linux/macOS
# oder von https://ollama.ai/download           # Windows

# Ollama starten
ollama serve

# Modell laden
ollama pull qwen2.5:3b
# Alternative: deepseek-r1:8b, llama3:7b, mistral
```

## 💡 Verwendung

### 1. CLI - Interaktiver Modus

```bash
python main.py --interactive

# Oder mit Setup-Script
run.bat           # Windows
./run.sh          # Linux/macOS
```

```
╭────────────────────────────────────────────╮
│ CrawlLama v1.1 - AI Research Agent        │
│ Befehle: exit, clear, stats, help         │
╰────────────────────────────────────────────╯

❯ Was ist Machine Learning?
```

### 2. CLI - Direkte Fragen

```bash
# Standard-Query
python main.py "Was ist Python?"

# Multi-Hop-Reasoning (für komplexe Fragen)
python main.py --multihop "Vergleiche Python und JavaScript für Web-Entwicklung"

# Offline-Modus
python main.py --no-web "Erkläre Photosynthese"

# Mit spezifischem Modell
python main.py --model llama3:7b "Wer hat Einstein entdeckt?"
```

### 3. FastAPI Server

```bash
# Server starten
python app.py

# Oder
uvicorn app:app --host 0.0.0.0 --port 8000
```

**API-Dokumentation:** http://localhost:8000/docs

**Beispiel-Requests:**

```bash
# Standard Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Was ist Machine Learning?",
    "use_multihop": false
  }'

# Multi-Hop Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare Python and JavaScript",
    "use_multihop": true,
    "max_hops": 3
  }'

# Statistiken abrufen
curl http://localhost:8000/stats

# Plugins auflisten
curl http://localhost:8000/plugins

# Plugin laden
curl -X POST http://localhost:8000/plugins/example_plugin/load
```

### 4. Docker Deployment

```bash
# Mit docker-compose (inkl. Ollama)
docker-compose up -d

# Logs anzeigen
docker-compose logs -f

# Stoppen
docker-compose down

# Nur Dockerfile
docker build -t crawllama .
docker run -p 8000:8000 -v $(pwd)/data:/app/data crawllama
```

## 📋 CLI Befehle & Optionen

### Grundlegende Optionen
| Option | Beschreibung |
|--------|--------------|
| `--interactive` | Interaktiver Modus |
| `--debug` | Debug-Logging aktivieren |
| `--no-web` | Offline-Modus (keine Web-Suche) |
| `--model MODEL` | Ollama-Modell wählen |
| `--stats` | System-Statistiken anzeigen |
| `--clear-cache` | Cache leeren |

### Erweiterte Optionen (v1.1)
| Option | Beschreibung |
|--------|--------------|
| `--multihop` | Multi-Hop-Reasoning aktivieren |
| `--max-hops N` | Max. Reasoning-Schritte (1-5) |
| `--api` | API-Server starten |
| `--plugins` | Verfügbare Plugins auflisten |
| `--load-plugin NAME` | Plugin laden |
| `--help-extended` | Erweiterte Hilfe anzeigen |
| `--examples` | Verwendungsbeispiele anzeigen |
| `--setup-keys` | API-Keys sicher einrichten |

### Interaktive Befehle
| Befehl | Beschreibung |
|--------|--------------|
| `exit`, `quit` | Programm beenden |
| `clear` | Bildschirm leeren |
| `stats` | Statistiken anzeigen |
| `help` | Hilfe anzeigen |

## 🏗️ Projektstruktur

```
crawllama/
│
├── main.py                       # CLI Entry Point
├── app.py                        # FastAPI Server (NEW)
├── config.json                   # Konfiguration
├── requirements.txt              # Dependencies
├── setup.bat / setup.sh          # Setup-Scripts (NEW)
├── Dockerfile                    # Docker Image (NEW)
├── docker-compose.yml            # Docker Compose (NEW)
├── crawllama.service             # Systemd Service (NEW)
│
├── core/                         # Kernlogik
│   ├── agent.py                  # Standard-Agent
│   ├── langgraph_agent.py        # Multi-Hop-Agent (NEW)
│   ├── llm_client.py             # Ollama-Client
│   ├── context_manager.py        # Token-Management
│   ├── cache.py                  # Cache-System
│   ├── fallback_manager.py       # Fallback-System (NEW)
│   ├── lazy_loader.py            # Lazy-Loading (NEW)
│   ├── plugin_manager.py         # Plugin-System (NEW)
│   └── session_manager.py        # Multi-User (NEW)
│
├── tools/                        # Modulare Tools
│   ├── web_search.py             # Multi-Source Web-Suche
│   ├── page_reader.py            # HTML-Parser + Kontaktsuche
│   ├── wiki_lookup.py            # Wikipedia
│   ├── rag.py                    # Advanced RAG (NEW)
│   └── tool_registry.py          # Tool-Verwaltung
│
├── utils/                        # Hilfsfunktionen
│   ├── logger.py                 # Strukturiertes Logging
│   ├── retry.py                  # Retry-Logik
│   ├── validators.py             # Validierung
│   ├── safe_fetch.py             # Sicheres HTTP (NEW)
│   ├── rate_limiter.py           # Rate-Limiting (NEW)
│   ├── domain_blacklist.py       # Domain-Filter (NEW)
│   ├── proxy_validator.py        # Proxy-Validierung (NEW)
│   ├── parallel_search.py        # Parallelisierung (NEW)
│   ├── async_utils.py            # Async-Operations (NEW)
│   ├── resource_monitor.py       # RAM/Performance (NEW)
│   ├── cli_helper.py             # Enhanced CLI (NEW)
│   └── secure_config.py          # Verschlüsselte Config (NEW)
│
├── plugins/                      # Plugin-System (NEW)
│   ├── __init__.py
│   └── example_plugin.py
│
├── data/                         # Daten & Cache
│   ├── cache/                    # Web-Cache
│   ├── embeddings/               # ChromaDB
│   └── history/                  # Sessions & History (NEW)
│
├── logs/                         # Log-Dateien
│   └── app.log
│
├── tests/                        # Umfassende Tests (NEW)
│   ├── test_web_search.py
│   ├── test_fallback_manager.py  # NEW
│   ├── test_rate_limiter.py      # NEW
│   ├── test_domain_blacklist.py  # NEW
│   ├── test_safe_fetch.py        # NEW
│   ├── test_error_simulation.py  # NEW
│   └── test_multihop_reasoning.py # NEW
│
└── docs/                         # Dokumentation
    ├── setup.md
    ├── IMPLEMENTATION_GUIDE.md
    ├── checklist.txt
    ├── NEW_FEATURES.md           # NEW
    ├── LANGGRAPH_GUIDE.md        # NEW
    └── PLUGIN_TUTORIAL.md        # NEW
```

## ⚙️ Konfiguration

### config.json

```json
{
  "llm": {
    "base_url": "http://127.0.0.1:11434",
    "model": "qwen2.5:3b",
    "temperature": 0.7,
    "max_tokens": 4096,
    "stream": true
  },
  "search": {
    "provider": "duckduckgo",
    "max_results": 5,
    "timeout": 10
  },
  "rag": {
    "enabled": true,
    "batch_size": 100,
    "max_workers": 4
  },
  "cache": {
    "enabled": true,
    "ttl_hours": 24
  },
  "multihop": {
    "enabled": true,
    "max_hops": 3,
    "confidence_threshold": 0.7,
    "enable_critique": true
  },
  "plugins": {
    "example_plugin": {
      "enabled": true
    }
  },
  "security": {
    "rate_limit": 1.0,
    "max_context_length": 8000,
    "check_robots_txt": true
  }
}
```

### .env (Optional)

```bash
# API Keys (optional)
BRAVE_API_KEY=your_brave_api_key
SERPER_API_KEY=your_serper_api_key

# Proxy (optional)
HTTP_PROXY=http://proxy:port
HTTPS_PROXY=https://proxy:port
```

## 🧪 Testing

```bash
# Alle Tests
pytest tests/ -v

# Mit Coverage
pytest --cov=core --cov=tools --cov=utils tests/

# Spezifische Tests
pytest tests/test_multihop_reasoning.py -v
pytest tests/test_error_simulation.py -v

# Mit Debug-Output
pytest tests/ -v --log-cli-level=INFO
```

## 🔌 Plugin-Entwicklung

### Einfaches Plugin erstellen

```python
# plugins/my_plugin.py

from core.plugin_manager import Plugin, PluginMetadata

class MyPlugin(Plugin):
    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="MyPlugin",
            version="1.0.0",
            description="My custom plugin",
            author="Your Name",
            dependencies=[]
        )

    def get_tools(self):
        return [self.my_tool]

    def my_tool(self, input: str) -> str:
        return f"Processed: {input}"
```

**Siehe:** [Plugin-Tutorial](docs/PLUGIN_TUTORIAL.md) für Details

## 🛠️ Technologie-Stack

### Core
- **LLM**: Ollama (qwen2.5:3b, deepseek-r1:8b, llama3, mistral)
- **Orchestration**: LangGraph (Multi-Hop-Reasoning)
- **Web-Suche**: duckduckgo-search, Brave API, Serper API
- **RAG**: ChromaDB + Sentence Transformers

### Backend
- **API**: FastAPI + Uvicorn
- **Database**: SQLite (Sessions)
- **Async**: aiohttp, asyncio
- **Monitoring**: psutil

### Utils
- **HTML-Parsing**: BeautifulSoup4
- **CLI**: Rich (Formatierung)
- **Retry**: Tenacity
- **Security**: cryptography

### Development
- **Tests**: pytest, pytest-mock, pytest-cov
- **Deployment**: Docker, docker-compose
- **CI/CD**: GitHub Actions (geplant)

## 📚 Dokumentation

### Benutzer-Guides
- 📖 [Setup Guide](docs/setup.md) - Detaillierte Installation
- 🧠 [LangGraph Guide](docs/LANGGRAPH_GUIDE.md) - Multi-Hop-Reasoning
- 🔌 [Plugin Tutorial](docs/PLUGIN_TUTORIAL.md) - Plugin-Entwicklung
- ✨ [New Features](docs/NEW_FEATURES.md) - v1.1 Features

### Entwickler-Docs
- 🏗️ [Implementation Guide](docs/IMPLEMENTATION_GUIDE.md)
- ✅ [Checklist](docs/checklist.txt) - Entwicklungs-Roadmap
- 🧪 Tests - Siehe `tests/` für Beispiele

### API-Dokumentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🌟 Roadmap

### Phase 1: Core ✅ (Completed)
- ✅ Ollama-Integration
- ✅ Web-Suche (DuckDuckGo)
- ✅ Tool-Orchestrierung
- ✅ Basic RAG & Caching
- ✅ CLI mit Rich

### Phase 2: Robustheit ✅ (Completed)
- ✅ Fallback-System
- ✅ Retry-Logik mit tenacity
- ✅ Rate-Limiting & robots.txt
- ✅ Domain-Blacklist
- ✅ Safe-Fetch mit Proxy-Support
- ✅ Multi-Source Web-Search
- ✅ Comprehensive Tests (80%+ Coverage)

### Phase 3: Intelligence ✅ (Completed - v1.1)
- ✅ Multi-Hop-Reasoning mit LangGraph
- ✅ RAG-Optimierungen (Batch, Multi-Query, Hybrid)
- ✅ Parallelisierung (ThreadPoolExecutor)
- ✅ Lazy-Loading für Tools/Plugins
- ✅ Async HTTP-Operations
- ✅ RAM & Performance-Monitoring

### Phase 4: Production ✅ (Completed - v1.1)
- ✅ FastAPI REST API
- ✅ Multi-User-Support (SQLite)
- ✅ Plugin-System
- ✅ Enhanced CLI
- ✅ Docker-Deployment
- ✅ Setup-Scripts (Windows/Linux)
- ✅ Systemd-Service
- ✅ Comprehensive Documentation

### Phase 5: Future 📅 (Geplant)
- [ ] GUI (Streamlit/Gradio)
- [ ] GraphQL API
- [ ] Redis-Cache für Production
- [ ] Kubernetes-Deployment
- [ ] Monitoring-Dashboard
- [ ] Multi-Language-Support
- [ ] Voice-Interface

## 🤝 Contributing

Contributions sind willkommen!

**Entwicklungs-Workflow:**
1. Fork das Repository
2. Erstelle Feature-Branch (`git checkout -b feature/amazing-feature`)
3. Commit deine Änderungen (`git commit -m 'Add amazing feature'`)
4. Push zum Branch (`git push origin feature/amazing-feature`)
5. Erstelle Pull Request

**Coding-Standards:**
- PEP8-konform
- Type Hints verwenden
- Docstrings für alle Funktionen
- Tests für neue Features

## 📊 Performance

### Benchmarks (auf i7-8700K, 32GB RAM)

| Operation | Durchschnitt | Hinweise |
|-----------|--------------|----------|
| Standard Query | 2-5s | Ohne Web-Suche |
| Query mit Web-Search | 5-10s | 3-5 Results |
| Multi-Hop (3 Hops) | 15-30s | Komplex |
| RAG-Search | <1s | 5 Results |
| API Request | <100ms | Ohne Tools |

### Ressourcen

- **RAM**: 200-500 MB (Standard), 500-800 MB (mit RAG)
- **CPU**: 10-30% (Idle), 50-80% (Active)
- **Disk**: ~100 MB (Code), variabel (Cache/Embeddings)

## ⚠️ Rechtliche Hinweise

### Web-Scraping
- ✅ Respektiert `robots.txt`
- ✅ Rate-Limiting (1 req/s default)
- ✅ Identifizierbarer User-Agent
- ⚠️ Benutzer sind für Einhaltung lokaler Gesetze verantwortlich

### Datenschutz
- ✅ Alle Daten lokal verarbeitet
- ✅ Keine Cloud-Services
- ✅ Volle Kontrolle über Logs/Cache
- ✅ Session-Daten verschlüsselt (optional)

### API-Keys
- Brave Search API: [brave.com/search/api](https://brave.com/search/api)
- Serper API: [serper.dev](https://serper.dev)

## 🆘 Troubleshooting

### Ollama nicht erreichbar
```bash
# Prüfe Status
curl http://127.0.0.1:11434/api/tags

# Starte Ollama
ollama serve
```

### Import-Fehler
```bash
# Reinstall Dependencies
pip install -r requirements.txt

# Oder Setup neu ausführen
./setup.sh  # oder setup.bat
```

### ChromaDB-Fehler
```bash
# Lösche Embeddings
rm -rf data/embeddings/

# Neustart
python main.py
```

### Docker-Probleme
```bash
# Logs prüfen
docker-compose logs -f crawllama

# Container neu bauen
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### API-Rate-Limits
```bash
# In config.json anpassen
"security": {
  "rate_limit": 2.0  # 2 req/s
}
```

## 💬 Support & Community

- 🐛 **Issues**: [GitHub Issues](https://github.com/arn-c0de/Crawllama/issues)
- 💡 **Diskussionen**: [GitHub Discussions](https://github.com/arn-c0de/Crawllama/discussions)
- 📧 **Email**: support@example.com

## 📝 Lizenz

MIT License - siehe [LICENSE](LICENSE) für Details.

## 🙏 Credits

Erstellt mit:
- [Ollama](https://ollama.ai) - Lokale LLMs
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent-Orchestrierung
- [FastAPI](https://fastapi.tiangolo.com) - REST API
- [ChromaDB](https://www.trychroma.com) - Vector Database
- [Rich](https://github.com/Textualize/rich) - Terminal-Formatting

## 🔖 Versionen

- **v1.1** (2025-01-23) - Phase 3 & 4 Complete: Multi-Hop, API, Plugins, Docker
- **v1.0** (2025-01-22) - Phase 1 & 2 Complete: Core + Robustness
- **v0.1** (2025-01-20) - Initial Release

---

**Erstellt mit ❤️ für lokale KI-Entwicklung**

*Letzte Aktualisierung: 2025-01-23*

**Status: Production Ready ✅**
