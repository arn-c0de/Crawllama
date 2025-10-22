# CrawlLama 🦙

**Lokaler KI-Such- und Antwort-Agent mit Ollama**

Ein vollständig lokales KI-System, das im Terminal läuft und Benutzeranfragen intelligent beantwortet durch:
- **Ollama** (lokales LLM) für Textverstehen und Antwortgenerierung
- **Autonome Web-Recherche** mit strukturierten Tool-Calls
- **RAG (Retrieval-Augmented Generation)** für kontextbasierte Antworten
- **Modulare Architektur** für einfache Erweiterbarkeit

## ✨ Features

- 🔒 **100% Lokal** - Keine Cloud-Abhängigkeit, volle Datenkontrolle
- 🌐 **Web-Suche** - DuckDuckGo Integration ohne API-Keys
- 📚 **Wikipedia** - Dedizierte Wikipedia-Suche (Deutsch/Englisch)
- 🧠 **RAG-System** - Semantische Suche in lokalen Dokumenten
- 💾 **Intelligentes Caching** - Reduziert redundante Requests
- 🎯 **Tool-Orchestrierung** - Automatische Auswahl des besten Tools
- 📊 **Strukturiertes Logging** - JSON-Logs für einfache Analyse
- 🔄 **Retry-Logik** - Robuste Fehlerbehandlung

## 🚀 Schnellstart

### Voraussetzungen

- **Python 3.10+**
- **Ollama** installiert und laufend
- Internet-Verbindung (für Web-Suche)

### Installation

1. **Repository klonen:**
```bash
git clone https://github.com/yourusername/crawllama.git
cd crawllama
```

2. **Setup-Script ausführen (erstellt automatisch venv und installiert alles):**

**Windows:**
```cmd
setup.bat
```

**Linux/macOS:**
```bash
chmod +x setup.sh run.sh
./setup.sh
```

Das Setup-Script:
- Erstellt ein virtuelles Python-Environment (venv)
- Installiert alle Abhängigkeiten im venv
- Erstellt notwendige Verzeichnisse
- Kopiert .env.example zu .env

3. **Ollama starten:**
```bash
ollama serve
```

4. **Modell herunterladen:**
```bash
ollama pull deepseek-r1:8b

# Alternative Modelle:
# ollama pull qwen2.5:3b
# ollama pull llama3:7b
```

5. **CrawlLama starten:**

**Windows:**
```cmd
# Interaktiver Modus
run.bat

# Direkte Frage
run.bat "Was ist Python?"

# Offline-Modus
run.bat --no-web "Erkläre Photosynthese"
```

**Linux/macOS:**
```bash
# Interaktiver Modus
./run.sh

# Direkte Frage
./run.sh "Was ist Python?"

# Offline-Modus
./run.sh --no-web "Erkläre Photosynthese"
```

**Wichtig:** Nutze immer `run.bat` (Windows) oder `./run.sh` (Linux/macOS), damit das virtuelle Environment automatisch aktiviert wird!

## 💡 Verwendung

### Interaktiver Modus

**Windows:**
```cmd
run.bat
```

**Linux/macOS:**
```bash
./run.sh
```

```
╭─────────────────────────────────────────╮
│ CrawlLama - Lokaler Such- und Antwort-Agent │
│ Stelle Fragen und erhalte intelligente Antworten. │
│ Befehle: exit, quit, clear, stats      │
╰─────────────────────────────────────────╯

❯ Was ist die Hauptstadt von Deutschland?
```

### Direkte Fragen

**Windows:**
```cmd
run.bat "Was ist künstliche Intelligenz?"
```

**Linux/macOS:**
```bash
./run.sh "Was ist künstliche Intelligenz?"
```

### Offline-Modus

```cmd
run.bat --no-web "Erkläre das Sonnensystem"
```

### Modell wechseln

```cmd
run.bat --model llama3:7b "Wer hat Python erfunden?"
```

### Statistiken anzeigen

```cmd
run.bat --stats
```

### Cache leeren

```cmd
run.bat --clear-cache
```

## 🏗️ Projektstruktur

```
crawllama/
│
├── main.py                    # CLI Einstiegspunkt
├── config.json                # Konfiguration
├── requirements.txt           # Python-Abhängigkeiten
├── .env.example               # Umgebungsvariablen Vorlage
├── README.md                  # Diese Datei
│
├── core/                      # Kernlogik
│   ├── agent.py               # Hauptagent (Orchestrierung)
│   ├── llm_client.py          # Ollama-Client
│   ├── context_manager.py     # Token-Management
│   └── cache.py               # Cache-System
│
├── tools/                     # Modulare Tools
│   ├── web_search.py          # Web-Suche (DuckDuckGo)
│   ├── page_reader.py         # HTML-Parser
│   ├── wiki_lookup.py         # Wikipedia
│   ├── rag.py                 # RAG mit ChromaDB
│   └── tool_registry.py       # Tool-Verwaltung
│
├── utils/                     # Hilfsfunktionen
│   ├── logger.py              # Strukturiertes Logging
│   ├── retry.py               # Retry-Logik
│   ├── validators.py          # Sicherheit & Validierung
│   └── text_cleaner.py        # Text-Verarbeitung
│
├── data/                      # Daten & Cache
│   ├── cache/                 # Web-Cache
│   ├── embeddings/            # ChromaDB
│   └── history/               # Chat-Verlauf
│
├── logs/                      # Log-Dateien
│   └── app.log
│
└── tests/                     # Tests
    ├── test_web_search.py
    ├── test_cache.py
    ├── test_llm_client.py
    └── test_integration.py
```

## ⚙️ Konfiguration

Die Konfiguration erfolgt über `config.json`:

```json
{
  "llm": {
    "provider": "ollama",
    "base_url": "http://127.0.0.1:11434",
    "model": "deepseek-r1:8b",
    "temperature": 0.7,
    "max_tokens": 4096,
    "stream": true
  },
  "search": {
    "provider": "duckduckgo",
    "max_results": 3,
    "timeout": 10
  },
  "rag": {
    "enabled": true,
    "chunk_size": 500,
    "top_k": 5
  },
  "cache": {
    "enabled": true,
    "ttl_hours": 24
  }
}
```

## 🔧 Entwicklung

### Tests ausführen

```bash
# Alle Tests
pytest tests/

# Mit Coverage
pytest --cov=core --cov=tools tests/

# Spezifischer Test
pytest tests/test_web_search.py -v
```

### Debug-Modus

```bash
run.bat --debug  # Windows
./run.sh --debug  # Linux/macOS
```

## 📋 Verfügbare Befehle

| Befehl | Beschreibung |
|--------|--------------|
| `exit`, `quit` | Programm beenden |
| `clear` | Bildschirm leeren |
| `stats` | Statistiken anzeigen |

## 🛠️ Technologie-Stack

- **LLM**: Ollama (deepseek-r1:8b - Standard, qwen2.5:3b, llama3, mistral)
- **Web-Suche**: duckduckgo-search
- **RAG**: ChromaDB + Sentence Transformers
- **HTML-Parsing**: BeautifulSoup4
- **CLI**: Rich, argparse
- **Retry**: Tenacity
- **Tests**: pytest

## 🤝 Beitragen

Contributions sind willkommen! Bitte:
1. Fork das Repository
2. Erstelle einen Feature-Branch
3. Commit deine Änderungen
4. Push zum Branch
5. Erstelle einen Pull Request

## 📝 Lizenz

MIT License - siehe [LICENSE](LICENSE) für Details.

## ⚠️ Rechtliche Hinweise

### Web-Scraping
- Beachte `robots.txt` der Websites
- Respektiere Rate-Limits (1 Request/Sekunde)
- Verwende identifizierbaren User-Agent

### Datenschutz
- Alle Daten werden lokal verarbeitet
- Keine Cloud-Services
- Volle Kontrolle über Logs und Cache

## 🆘 Troubleshooting

### Ollama nicht erreichbar
```bash
# Prüfe ob Ollama läuft
ollama list

# Starte Ollama
ollama serve
```

### Import-Fehler
```bash
# Führe Setup neu aus (aktiviert automatisch venv)
setup.bat  # Windows
./setup.sh  # Linux/macOS
```

### ChromaDB Fehler
```bash
# Lösche Embeddings und starte neu
rm -rf data/embeddings/
```

## 📚 Weitere Dokumentation

- [Setup Guide](docs/setup.md) - Detaillierte Installation
- [Implementation Guide](docs/IMPLEMENTATION_GUIDE.md) - Technische Details
- [Checklist](docs/checklist.txt) - Entwicklungs-Roadmap

## 🌟 Roadmap

### Phase 1: Core ✅
- [x] Ollama-Integration
- [x] Web-Suche
- [x] Tool-Orchestrierung
- [x] Caching

### Phase 2: Robustheit 🚧
- [ ] Umfassende Fehlerbehandlung
- [ ] Fallback-System
- [ ] >80% Test-Coverage

### Phase 3: Intelligence 📅
- [ ] Multi-Hop-Reasoning
- [ ] Parallelisierung
- [ ] Erweiterte RAG-Features

### Phase 4: Production 📅
- [ ] API-Endpunkte (FastAPI)
- [ ] GUI (Open WebUI)
- [ ] Docker-Deployment

## 💬 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/crawllama/issues)
- **Diskussionen**: [GitHub Discussions](https://github.com/yourusername/crawllama/discussions)

---

**Erstellt mit ❤️ für lokale KI**

*Letzte Aktualisierung: 2025-10-22*
