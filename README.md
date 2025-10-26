<div align="left">
  <h1>   <img src="logo.ico" alt="CrawlLama Logo" width="64" height="64">  CrawlLama</h1>
</div>

![Python Version](https://img.shields.io/badge/python-3.1%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightblue)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)
![License](https://img.shields.io/badge/license-Non--Commercial-orange)
![Status](https://img.shields.io/badge/status-Active-success)

**Production-Ready AI Research Agent mit OSINT & Multi-Hop Reasoning**

**Version 1.4.2** - Memory Store Deletion & OSINT Fixes

---


---

📚 **[Dokumentation](docs/README.md)** | 🚀 **[Quickstart](docs/getting-started/QUICKSTART.md)** | 🤝 **[Contributing](CONTRIBUTING.md)** | 🔒 **[Security](SECURITY.md)** | 📝 **[Changelog](CHANGELOG.md)**

---

## 📖 Inhaltsverzeichnis

- [Features](#-features)
- [Schnellstart](#-schnellstart)
- [Installation](#-installation)
- [Verwendung](#-verwendung)
- [Konfiguration](#️-konfiguration)
- [Testing](#-testing)
- [Dokumentation](#-weitere-dokumentation)
- [Contributing](#-contributing)
- [License](#-lizenz)

---

Ein vollständig lokales, produktionsreifes KI-System mit erweiterten Intelligence-Features:
- 🔍 **OSINT Module** - Email/Phone/IP Intelligence, Social Media Analysis, Advanced Search Operators
- 🧠 **Multi-Hop-Reasoning** mit LangGraph für komplexe Fragen
- 🚀 **REST API** mit FastAPI für Integration
- 🔌 **Plugin-System** für einfache Erweiterbarkeit
- ⚡ **Performance-Optimierungen** (16k Context für RTX 3080, Async, Parallelisierung)
- ✨ **v1.4 NEW:** Vollständige Compliance-Dokumentation, Projekt-Struktur-Überarbeitung, Security Audit

## ✨ Features

### 🎯 Core Features
- 🔒 **100% Lokal** - Keine Cloud-Abhängigkeit, volle Datenkontrolle
- 🌐 **Multi-Source Web-Suche** - DuckDuckGo, Brave Search, Serper API mit Fallback
- 📚 **Wikipedia Integration** - Dedizierte Wikipedia-Suche (Deutsch/Englisch)
- 🧠 **Advanced RAG-System** - Batch-Processing, Multi-Query, Hybrid-Search
- 💾 **Intelligentes Caching** - TTL-basiert mit Hash-Keys, LRU-Eviction, konfigurierbare Max-Size (500MB)
- 🎯 **Tool-Orchestrierung** - Automatische Tool-Auswahl per LLM
- ⚙️ **Interaktives Settings-Menü** - Live-Konfiguration von LLM, Search, RAG & OSINT
- 📊 **Context Usage Tracker** - Echtzeit-Token-Verbrauchsüberwachung mit tiktoken
- 🏥 **Health Monitoring Dashboard** - Interaktive Systemüberwachung mit Rich UI
- 🔄 **Restart-Befehl** - Agent neu starten ohne Programm zu beenden
- 🔄 **Multi-Hop-Reasoning** - LangGraph-basierter Agent mit 6-Node-Workflow (Router → Search → Analyze → Follow-Up → Synthesize → Critique)
- ⚡ **Parallelisierung** - Multi-Aspect-Searches mit ThreadPoolExecutor
- 🔌 **Lazy-Loading** - On-Demand-Loading für Tools und Plugins
- 🌐 **Async Operations** - Parallele HTTP-Requests mit aiohttp
- 📊 **Resource Monitoring** - RAM-Usage, Performance-Tracking, Auto-GC
- 🌐 **FastAPI REST API** - 8+ Endpunkte mit Auto-Dokumentation (`/query`, `/plugins`, `/stats`, `/health`)
- 🔌 **Plugin-System** - Dynamisches Laden/Entladen von Plugins
- 🎨 **Enhanced CLI** - Rich-Formatting, Tabellen, Trees, Markdown
- 🔧 **Setup-Scripts** - setup.bat, setup.sh mit Auto-Configuration

### 🔍 OSINT Features
- 🔎 **Advanced Search Operators** - site:, inurl:, intext:, filetype:, email:, phone:, ip:
- 📧 **Email Intelligence** - Validation, MX Records, Disposable Detection, Variations
- 📱 **Phone Intelligence** - Validation, Carrier Lookup, Country Detection, Formatting
- 💾 **Persistent Memory Store** - Survives `clear` command, stores emails/phones/IPs/usernames/domains/notes
- 🗑️ **Memory Store CRUD** - Vollständige CRUD-Funktionalität mit `forget` Befehl
- 🔄 **Batch Processing** - Analyze multiple emails/phones simultaneously with summary statistics
- 🌐 **IP Intelligence** - IPv4/IPv6 Analysis, Geolocation, ISP Info, Security Reputation, VPN Detection
- 👤 **Social Intelligence** - 12 Platforms (GitHub, LinkedIn, Twitter, Instagram, Facebook, YouTube, Reddit, Pinterest, TikTok, Snapchat, Discord, Steam)
- 🤖 **AI Query Enhancement** - Query Variations, Operator Suggestions, Entity Detection, Auto-Type Detection
- ⚖️ **Compliance Module** - Rate Limiting, Terms of Use, Audit Logging, Robots.txt Compliance
- 🛡️ **Privacy Protection** - No API Keys Required, Ethical Scraping, Usage Tracking
- � **Safesearch Quality Filter** - Konfigurierbare Ergebnisqualität (off/moderate/strict)

### 🔒 Security & Performance
- 🔧 **Code Quality** - Refactored, fokussierte Methoden für bessere Wartbarkeit
- 🎯 **Accurate Token Counting** - tiktoken Integration für präzise Token-Zählung
- 🔄 **Intelligent Retry Logic** - tenacity-basierte Retries mit Exponential Backoff
- ⏱️ **Rate Limiting** - 1 Request/Sekunde + robots.txt-Checks
- �️ **Fallback-System** - Automatische Fallbacks bei API-Ausfällen
- 🔐 **Secure Config** - Verschlüsselte API-Key-Speicherung
- 🔍 **Output Validation** - Sanitization von LLM-Ausgaben
- ✅ **Domain Blacklist** - Schutz vor unerwünschten Domains
- 📊 **RTX 3080 Optimization** - 16k Context Support (qwen3:8b), Increased Cache Sizes

> **Hinweis:** Dieses Projekt ist aktuell nur auf Deutsch dokumentiert. Eine englische Übersetzung ist geplant, aber noch nicht verfügbar. Wer Zeit und Interesse hat, kann gerne eine Übersetzung als Pull Request beitragen!


## 🆕 Release-Highlights v1.4.2 (2025-10-26)

**Major Changes:**
- �️ **Memory Store Deletion**: Vollständige CRUD-Funktionalität mit `forget` Befehl
- 🔧 **OSINT Parser Fixes**: Memory-Operatoren haben jetzt Priorität vor Standard-Operatoren
- 📱 **Phone Pattern Fix**: Telefonnummern mit Durchwahl (z.B. 040-822268-0) werden korrekt geparst
- 🔄 **Live Dashboard Updates**: Memory Store Panel aktualisiert sich in Echtzeit
- 🚀 **API Starter Scripts**: Neue `run_api.bat` / `run_api.sh` für schnellen FastAPI-Server-Start

**Forget Command Syntax:**
```bash
forget email:test@example.com        # Spezifische Email löschen
forget phone:+491234567890           # Telefonnummer löschen
forget ip:192.168.1.1                # IP-Adresse löschen
forget username:johndoe              # Benutzername löschen
forget category:emails               # Alle Emails löschen
forget category:phones               # Alle Telefonnummern löschen
forget all:true                      # Gesamten Memory Store löschen
```

**API Server starten:**
```bash
# Windows
run_api.bat

# Linux/macOS
./run_api.sh

# Oder manuell
python app.py
```
Dann im Browser öffnen: http://localhost:8000/docs

### 🏥 Health Monitoring Dashboard
Das integrierte Health-Modul bietet **ein einheitliches Dashboard** mit zwei Modi:

#### Verwendung:
```bash
# Windows
health-dashboard.bat

# Linux/macOS
./health-dashboard.sh

# Direkt mit Python (Interaktives Menü)
python health-dashboard.py

# Direkt zum Live Monitor
python health-dashboard.py --monitor

# Direkt zum Test Dashboard
python health-dashboard.py --tests
```

#### 📊 Modus 1: Live System Monitor
Live-Überwachung in Echtzeit mit Rich Terminal UI:
- **Live System-Metriken** - CPU, RAM, Disk, Network in Echtzeit
- **Component Health Checks** - LLM, Cache, RAG, Tools automatisch prüfen
- **Performance-Tracking** - Response Times, Throughput, Perzentile
- **Alert-System** - Automatische Warnungen bei Schwellwert-Überschreitungen
- **Rich Terminal UI** - Farbcodierte Status-Anzeigen mit Live-Updates

#### 🧪 Modus 2: Test Dashboard (GUI)
Tkinter-basiertes GUI für Test-Management:
- ✅ Automatische Test-Erkennung
- ✅ Einzelne oder alle Tests ausführen
- ✅ Echtzeit-Fortschritts-Tracking
- ✅ Detaillierte Fehler-Logs
- ✅ Export (JSON/HTML)

**Siehe:** [Health Monitoring Guide](docs/health/HEALTH_MONITORING.md) für Details und programmatische Nutzung

**OSINT Usage:**
```bash
# Email intelligence
email:test@example.com

# Phone intelligence
phone:"+49 151 12345678"

# IP intelligence
ip:8.8.8.8

# Batch processing (NEW in v1.4.1!)
email:test@example.com user@domain.com admin@site.com
phone:+491234567890 +441234567890 +331234567890

# Memory Store (NEW in v1.4.2!)
remember email:test@example.com      # Email speichern
recall emails                        # Alle Emails abrufen
forget email:test@example.com        # Spezifische Email löschen
forget category:emails               # Alle Emails löschen
forget all:true                      # Gesamten Speicher löschen

# Advanced search
site:github.com inurl:python filetype:md

# Combined operators
email:john@example.com site:linkedin.com inurl:profile
```

**See:** [OSINT Usage Guide](docs/osint/OSINT_USAGE.md) | [OSINT Module README](core/osint/README.md)

### 🔒 Security & Robustness
- ✅ **Domain Blacklist** - Schutz vor unerwünschten Domains
- ⏱️ **Rate Limiting** - 1 Request/Sekunde + robots.txt-Checks
- 🔄 **Retry Logic** - Exponential Backoff mit tenacity (NEW v1.3: auch für LLM-Client)
- 🛡️ **Fallback-System** - Automatische Fallbacks bei API-Ausfällen
- 🔐 **Secure Config** - Verschlüsselte API-Key-Speicherung
- 🔍 **Output Validation** - Sanitization von LLM-Ausgaben
- 💾 **Smart Caching** - LRU-Eviction bei max_size_mb (NEW v1.3)

## 🚀 Schnellstart

### 📦 Downloads

**Fertige Releases (empfohlen für schnellen Start):**

| Version | Download | VirusTotal Check |
|---------|----------|------------------|
| **v1.4 Preview** | [Crawllama-1.4-preview.zip](https://github.com/arn-c0de/Crawllama/releases/download/v.1.4_Preview/Crawllama-1.4-preview.zip) | [🔒 VirusTotal Scan](https://www.virustotal.com/gui/url/dadd0eb337f8c30dc66134248399ebd990c1b11f3a950b6b752d5d567be45127) |

✅ **Alle Downloads sind virenfrei** - VirusTotal-Scans bestätigen keine Malware  
📦 **Plug & Play** - Einfach entpacken und starten (Ollama + Python erforderlich)

## 📦 Installation

**Windows:**
1. Download [Crawllama-1.4-preview.zip](https://github.com/arn-c0de/Crawllama/releases/download/v.1.4_Preview/Crawllama-1.4-preview.zip)
2. Entpacken in beliebigen Ordner (z.B. `C:\Crawllama`)
3. Ollama installieren von [ollama.ai/download](https://ollama.ai/download)
4. Ollama starten und Modell laden:
   ```cmd
   ollama serve
   ollama pull qwen3:4b
   ```
5. Im Crawllama-Ordner:
   ```cmd
   setup.bat
   run.bat
   ```

**Linux/macOS:**
1. Download und entpacken:
   ```bash
   wget https://github.com/arn-c0de/Crawllama/releases/download/v.1.4_Preview/Crawllama-1.4-preview.zip
   unzip Crawllama-1.4-preview.zip
   cd Crawllama-1.4
   ```
2. Ollama installieren:
   ```bash
   curl -fsSL https://ollama.ai/install.sh | sh
   ollama serve &
   ollama pull qwen3:4b
   ```
3. Setup und Start:
   ```bash
   chmod +x setup.sh run.sh
   ./setup.sh
   ./run.sh
   ```

---

### Option 1: Setup-Scripts (Empfohlen für Git-Installation)

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

⚠️ Hinweis zur Erstinstallation:

Beim ersten Ausführen von `pip install -r requirements.txt` innerhalb des neu erstellten `venv` kann die Installation aller Abhängigkeiten — insbesondere Pakete wie `torch`, `sentence-transformers` und wissenschaftliche Libraries — **5–10 Minuten** (oder länger, abhängig von Verbindung und Hardware) dauern. Bitte warte, bis der Vorgang abgeschlossen ist; danach ist das virtuelle Environment einsatzbereit.

Hinweis zur Festplattengröße: Nach der Installation (inkl. `venv`) benötigt das Projekt typischerweise etwa **1,2–1,5 GB** freien Festplattenspeicher (v1.4: ca. 1,23 GB). Dieser Wert kann je nach Betriebssystem, Python-Paketen (z. B. größere PyTorch-/CUDA-Wheels) und zusätzlichen Modellen deutlich höher ausfallen. Plane bei begrenztem Speicher großzügig zusätzlichen Platz ein.

Modell-Download-Größen (ungefähr):

- `qwen3:4b` — ca. **2–4 GB** (je nach Format/Quantisierung)
- `qwen3:8b` — ca. **8–12 GB**
- `deepseek-r1:8b` — ca. **6–10 GB**
- `llama3:7b` — ca. **6–9 GB**
- `mistral:7b` — ca. **4–8 GB**
- `phi3:14b` — ca. **12–20+ GB**

Hinweis: Modellgrößen variieren stark je nach Anbieter, Format (FP16, INT8-Quantisierung etc.) und zusätzlichen Assets. Quantisierte Modelle (z. B. INT8) können die Größe erheblich reduzieren, während FP32/FP16 oder Modelle mit zusätzlichen Tokenizer-/Vocab-Dateien mehr Platz benötigen. Plane ausreichend zusätzlichen Speicher ein, falls du größere Modelle oder mehrere Modelle gleichzeitig verwenden möchtest.

### Option 2: Manuelle Installation

**Voraussetzungen:**
- Python 3.10+ ([python.org](https://www.python.org/downloads/))
- Git ([git-scm.com](https://git-scm.com/downloads))
- Ollama ([ollama.ai/download](https://ollama.ai/download))

**Windows - Schritt für Schritt:**

```cmd
# 1. Repository klonen
git clone https://github.com/arn-c0de/Crawllama.git
cd Crawllama

# 2. Virtuelles Environment erstellen
python -m venv venv
venv\Scripts\activate

# 3. Dependencies installieren (dauert 5-10 Min)
pip install -r requirements.txt

# 4. Verzeichnisse erstellen
mkdir data\cache data\embeddings data\history logs plugins

# 5. Konfiguration
copy .env.example .env
notepad .env  # Optional: API-Keys eintragen

# 6. Ollama starten (separates Terminal)
ollama serve

# 7. Modell laden (separates Terminal)
ollama pull qwen3:4b

# 8. Crawllama starten
python main.py --interactive
```

**Linux/macOS - Schritt für Schritt:**

```bash
# 1. Repository klonen
git clone https://github.com/arn-c0de/Crawllama.git
cd Crawllama

# 2. Virtuelles Environment erstellen
python3 -m venv venv
source venv/bin/activate

# 3. Dependencies installieren (dauert 5-10 Min)
pip install -r requirements.txt

# 4. Verzeichnisse erstellen
mkdir -p data/cache data/embeddings data/history logs plugins

# 5. Konfiguration
cp .env.example .env
nano .env  # Optional: API-Keys eintragen

# 6. Ollama installieren und starten
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &

# 7. Modell laden
ollama pull qwen3:4b

# 8. Crawllama starten
python main.py --interactive
```

**Troubleshooting Installation:**

| Problem | Lösung |
|---------|--------|
| `python nicht gefunden` | Python 3.10+ installieren: [python.org](https://www.python.org/downloads/) |
| `pip install` schlägt fehl | `python -m pip install --upgrade pip` ausführen |
| `ollama: command not found` | Ollama installieren: [ollama.ai/download](https://ollama.ai/download) |
| `Connection refused` (Ollama) | Ollama starten: `ollama serve` |
| `ModuleNotFoundError` | Virtual Environment aktivieren: `venv\Scripts\activate` (Win) oder `source venv/bin/activate` (Linux) |
| Speicherplatz voll | Mind. 5 GB frei für venv + Modell |

---

### Option 3: Git Clone (Schnellinstallation)

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
ollama pull qwen3:4b
# Alternative: deepseek-r1:8b, llama3:7b, mistral
```

## 💡 Verwendung

> **Hinweis:**  
> Der erste Start kann deutlich länger dauern als alle folgenden Starts!  
> Die Initialisierung, Installation der Abhängigkeiten und der Download der Modelle benötigen – je nach Hardware und Internetverbindung – mehrere Minuten.  
> Nach dem ersten erfolgreichen Start sind alle weiteren Starts deutlich schneller.

### 1. CLI - Interaktiver Modus

```bash
python main.py --interactive

# Oder mit Setup-Script
run.bat           # Windows
./run.sh          # Linux/macOS
```

```
╭──────────────────────────────────────────────────────────────╮
│ CrawlLama - Lokaler Such- und Antwort-Agent                  │
│ Befehle:                                                     │
│   clear       - Session zurücksetzen (Historie + Cache)      │
│   clear-cache - Nur Cache löschen                            │
│   save        - Session manuell speichern                    │
│   load        - Session neu laden                            │
│   stats       - Statistiken anzeigen                         │
│   status      - Context-Verbrauch anzeigen                   │
│   settings    - Einstellungen anzeigen/ändern                │
│   restart     - Agent neu starten (Config neu laden)         │
│   exit, quit  - Beenden                                      │
╰──────────────────────────────────────────────────────────────╯

❯ Was ist Machine Learning?
```

**Neue Befehle:**

- `status` - Zeigt Token-Verbrauch und verfügbare Kontext-Kapazität
  ```
  ❯ status

            Context Usage Tracker
  ┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┓
  ┃ Quelle            ┃    Tokens ┃    Anteil ┃
  ┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━┩
  │ Konversation      │       850 │      8.5% │
  │ Suchergebnisse    │       320 │      3.2% │
  │ Gesamt verwendet  │     1,170 │     11.7% │
  │ Verfügbar         │     8,830 │     88.3% │
  │ Maximum           │    10,000 │      100% │
  └───────────────────┴───────────┴───────────┘
  ```

- `settings` - Interaktiver Konfigurations-Editor
  ```
  ❯ settings

  Zeigt alle Einstellungen an und ermöglicht:
  • Kategorie-Auswahl (llm, search, rag, cache, osint, all)
  • LLM-Modell ändern (qwen3:8b, deepseek-r1:8b, etc.)
  • Temperature anpassen (0.0-1.0)
  • Max Tokens konfigurieren (jetzt 16,000 für RTX 3080+)
  • Search Region ändern (de-de, us-en, wt-wt)
  • OSINT Max Results & Rate Limits konfigurieren
  • RAG aktivieren/deaktivieren
  • Cache aktivieren/deaktivieren
  • Änderungen direkt in config.json speichern
  • Auto-Restart nach Speichern (optional)
  ```

- `restart` - Agent neu starten
  ```
  ❯ restart

  • Lädt config.json neu
  • Initialisiert Agent komplett neu
  • Session-Preservation (optional)
  • Keine Unterbrechung der Sitzung
  ```

### 2. Health Monitoring Dashboard

```bash
# Windows
health-dashboard.bat

# Linux/macOS
python health-dashboard.py
```

Das Dashboard zeigt:
- ✅ System-Gesundheit (CPU, RAM, Disk, Network)
- ✅ Component-Status (LLM, Cache, RAG, Tools)
- ✅ Performance-Metriken (Response Times)
- ✅ Fehler-Log (Letzte 10 Fehler)
- ✅ Auto-Refresh (alle 5 Sekunden)

### 2. Health Monitoring Dashboard

```bash
# Windows
health-dashboard.bat

# Linux/macOS
python health-dashboard.py
```

Das Dashboard zeigt:
- ✅ System-Gesundheit (CPU, RAM, Disk, Network)
- ✅ Component-Status (LLM, Cache, RAG, Tools)
- ✅ Performance-Metriken (Response Times)
- ✅ Fehler-Log (Letzte 10 Fehler)
- ✅ Auto-Refresh (alle 5 Sekunden)

Interaktive Befehle:
- `r` - Refresh (manuell)
- `c` - Clear Error Log
- `t` - Run Component Tests
- `q` - Quit

### 3. Wie funktioniert die intelligente Suche?

Der Agent entscheidet automatisch, **wann und wie** er suchen soll:

#### 🤖 Automatische Entscheidung
```
❯ Wer ist der aktuelle Bundeskanzler?

1. LLM analysiert: "Benötigt aktuelle Infos" ✓
2. Agent führt Web-Suche durch
3. LLM verarbeitet Suchergebnisse
4. Agent liefert aktuelle Antwort
```

#### 🔍 Search-Operator für gezielte Suchen

**OSINT Search Operators:**
```bash
# Domain-spezifische Suche
❯ site:github.com machine learning

# E-Mail Intelligence
❯ email:john.doe@company.com

# Telefon Intelligence
❯ phone:"+49 151 12345678"

# IP Intelligence (NEW!)
❯ ip:8.8.8.8
❯ 192.168.1.1  # Auto-detects as IP

# Social Media Intelligence (12 Platforms)
❯ username:elonmusk
❯ @microsoft
❯ github  # Auto-detects as username

# Dateiformat-Suche
❯ site:example.com filetype:pdf

# URL-Filter
❯ inurl:documentation python

# Text-im-Content
❯ intext:"contact email" site:example.com
```

**Kombinierte Suchen:**
```bash
# Mehrere Operatoren
❯ site:linkedin.com inurl:profile "software engineer"

# Ausschluss mit minus
❯ python programming -java

# ODER-Verknüpfung
❯ site:github.com OR site:gitlab.com "machine learning"
```

Siehe **[OSINT Usage Guide](docs/osint/OSINT_USAGE.md)** für alle Features.

### 4. CLI - Direkte Fragen

```bash
# Standard-Query (Agent entscheidet automatisch ob Web-Suche nötig)
python main.py "Was ist Python?"

# Multi-Hop-Reasoning (für komplexe Fragen)
python main.py --multihop "Vergleiche Python und JavaScript für Web-Entwicklung"

# Offline-Modus (keine Web-Suche, nur LLM-Wissen)
python main.py --no-web "Erkläre Photosynthese"

# OSINT-Suche mit Search-Operatoren
python main.py "site:github.com python projects"
python main.py "email:contact@example.com"

# Mit spezifischem Modell
python main.py --model llama3:7b "Wer hat Einstein entdeckt?"
```

### 5. FastAPI Server

```bash
# Server starten
python app.py

# Oder mit Starter-Scripts
run_api.bat      # Windows
./run_api.sh     # Linux/macOS

# Oder manuell
uvicorn app:app --host 0.0.0.0 --port 8000
```

**API-Dokumentation:** http://localhost:8000/docs

**Verfügbare Endpunkte:**

**Query & Reasoning:**
- `POST /query` - Standard- oder Multi-Hop-Queries ausführen
- `POST /osint/query` - OSINT-Queries mit Operatoren (email:, phone:, ip:, etc.)

**Memory Store (CRUD):**
- `GET /memory` - Alle gespeicherten Einträge abrufen
- `POST /memory/remember` - Wert speichern (email, phone, ip, username, domain, note)
- `GET /memory/recall/{category}` - Kategorie abrufen (emails, phones, ips, etc.)
- `DELETE /memory/forget` - Einzelne Werte, Kategorien oder alles löschen
- `GET /memory/stats` - Memory Store Statistiken

**Session Management:**
- `POST /session/clear` - Session zurücksetzen
- `POST /session/save` - Session speichern
- `POST /session/load` - Session laden

**Cache:**
- `POST /cache/clear` - Cache leeren
- `GET /cache/stats` - Cache-Statistiken

**Configuration:**
- `GET /config` - Aktuelle Konfiguration abrufen
- `PATCH /config` - Konfiguration ändern (llm, search, rag, cache, osint)
- `GET /context/status` - Token-Verbrauch & Context-Usage

**Plugins & Tools:**
- `GET /plugins` - Verfügbare Plugins auflisten
- `POST /plugins/{name}/load` - Plugin laden
- `POST /plugins/{name}/unload` - Plugin entladen
- `GET /tools` - Verfügbare Tools auflisten

**System:**
- `GET /health` - Health Check (Agent, Monitoring, Components)
- `GET /stats` - System-Statistiken (Agent Stats, Resources, Performance)
- `GET /security-info` - Security-Konfiguration (Rate Limits, Features)

**🔒 API Security (v1.4.2+):**

Die API ist standardmäßig mit mehreren Sicherheitsfeatures geschützt:

- ✅ **API Key Authentication** - X-API-Key Header erforderlich
- ✅ **Rate Limiting** - 60 Requests/Minute (konfigurierbar)
- ✅ **Input Validation** - Pydantic-basierte Validierung
- ✅ **Query Sanitization** - Schutz vor Injection-Angriffen
- ✅ **Request Logging** - Alle Requests werden geloggt
- ✅ **CORS Protection** - Konfigurierbare Origins
- ✅ **Trusted Host Middleware** - Host Header Validation

**Setup:**
```bash
# 1. API Key in .env setzen
CRAWLLAMA_API_KEY=your_secure_api_key_min_32_chars

# 2. Für lokale Entwicklung (OHNE API Key)
CRAWLLAMA_DEV_MODE=true

# 3. Rate Limit anpassen (optional)
RATE_LIMIT=100

# 4. CORS Origins konfigurieren (optional)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

**Verwendung mit API Key:**
```bash
# Mit API Key Header
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{"query": "test"}'

# Oder im Dev Mode (ohne API Key)
export CRAWLLAMA_DEV_MODE=true
python app.py
```

**Beispiel-Requests:**

```bash
# Standard Query (Agent nutzt automatisch Web-Suche bei Bedarf)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Was ist Machine Learning?",
    "use_multihop": false
  }'

# Multi-Hop Query (für komplexe Analysen)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare Python and JavaScript",
    "use_multihop": true,
    "max_hops": 3
  }'

# OSINT-Suche mit Search-Operatoren
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "site:github.com python machine-learning",
    "use_multihop": false
  }'

# Statistiken abrufen
curl http://localhost:8000/stats

# Plugins auflisten
curl http://localhost:8000/plugins

# Plugin laden
curl -X POST http://localhost:8000/plugins/example_plugin/load
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

👉 Die vollständige und aktuelle Projektstruktur findest du hier: [docs/development/PROJECT_STRUCTURE.md](docs/development/PROJECT_STRUCTURE.md)

## ⚙️ Konfiguration

### config.json

```json
{
  "llm": {
    "base_url": "http://127.0.0.1:11434",
    "model": "qwen3:8b",
    "temperature": 0.7,
    "max_tokens": 10000,
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
    "ttl_hours": 24,
    "max_size_mb": 500,
    "clear_on_startup": false
  },
  "osint": {
    "max_results": 20,
    "email_search_limit": 50,
    "phone_search_limit": 50,
    "general_osint_limit": 100
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

**Empfohlene `max_tokens` Einstellungen:**

| GPU/Hardware | Empfohlene max_tokens | Modell |
|-------------|----------------------|--------|
| RTX 3080+ (10GB+) | 10,000 - 16,000 | qwen3:8b, deepseek-r1:8b |
| RTX 3060/3070 (8GB) | 6,000 - 8,000 | qwen3:4b, llama3:7b |
| CPU Only | 2,000 - 4,000 | qwen3:4b |

💡 **Tipp:** Nutze den `status` Befehl, um deinen Token-Verbrauch in Echtzeit zu überwachen!

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

**Siehe:** [Plugin-Tutorial](docs/guides/PLUGIN_TUTORIAL.md) für Details

## 🛠️ Technologie-Stack

### Core
- **LLM**: Ollama (qwen3:4b, deepseek-r1:8b, llama3, mistral)
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
- **CI/CD**: GitHub Actions (geplant)

## 📚 Dokumentation

### Benutzer-Guides
- 📖 [Installation Guide](docs/getting-started/INSTALLATION.md) - Detaillierte Installation
- 🧠 [LangGraph Guide](docs/guides/LANGGRAPH_GUIDE.md) - Multi-Hop-Reasoning
- 🔌 [Plugin Tutorial](docs/guides/PLUGIN_TUTORIAL.md) - Plugin-Entwicklung
- 🏥 [Health Monitoring](docs/health/HEALTH_MONITORING.md) - System-Überwachung

### Entwickler-Docs
- 🏗️ [Project Structure](docs/development/PROJECT_STRUCTURE.md) - Projekt-Übersicht
- 🔄 [Release Process](docs/development/RELEASE_PROCESS.md) - Release-Workflow
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

### API-Rate-Limits
```bash
# In config.json anpassen
"security": {
  "rate_limit": 2.0  # 2 req/s
}
```

## 💬 Support & Community

- 🐛 **Issues**: [GitHub Issues](https://github.com/arn-c0de/Crawllama/issues)
- 📧 **Support**: [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com)
- 🔒 **Security/Leaks**: [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com) (verschlüsselt via Proton Mail)

## 📝 Lizenz

**Crawllama License (Non-Commercial)** - Frei zur Nutzung und Entwicklung, aber kein Verkauf erlaubt.

✅ **Erlaubt:**
- Persönliche Nutzung
- Bildung & Forschung
- Modifikation & Weitergabe (nicht-kommerziell)
- Beiträge zum Projekt

❌ **Nicht erlaubt:**
- Verkauf der Software
- Kommerzielle Nutzung
- Integration in kostenpflichtige Produkte

Siehe [LICENSE](LICENSE) für vollständige Details.

## 🙏 Credits

Erstellt mit:
- [Ollama](https://ollama.ai) - Lokale LLMs
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent-Orchestrierung
- [FastAPI](https://fastapi.tiangolo.com) - REST API
- [ChromaDB](https://www.trychroma.com) - Vector Database
- [Rich](https://github.com/Textualize/rich) - Terminal-Formatting

## 📚 Weitere Dokumentation

- **[Dokumentations-Übersicht](docs/README.md)**
- **Schnellstart & Installation**
  - [QUICKSTART.md](docs/getting-started/QUICKSTART.md) – 5-Minuten Schnellstart
  - [INSTALLATION.md](docs/getting-started/INSTALLATION.md) – Detaillierte Installation
- **Feature-Guides**
  - [LANGGRAPH_GUIDE.md](docs/guides/LANGGRAPH_GUIDE.md) – Multi-Hop-Reasoning
  - [OSINT_USAGE.md](docs/osint/OSINT_USAGE.md) – OSINT Features
  - [OSINT_CONTEXT_USAGE.md](docs/osint/OSINT_CONTEXT_USAGE.md) – OSINT Context Usage
  - [SOCIAL_INTELLIGENCE.md](docs/SOCIAL_INTELLIGENCE.md) – Social Intelligence
  - [PLUGIN_TUTORIAL.md](docs/PLUGIN_TUTORIAL.md) – Plugin-Entwicklung
  - [HALLUCINATION_DETECTION.md](docs/HALLUCINATION_DETECTION.md) – Hallucination Detection
  - [SEARCH_LIMITATIONS.md](docs/SEARCH_LIMITATIONS.md) – Search Limitierungen
- **Health Monitoring**
  - [HEALTH_MONITORING.md](docs/HEALTH_MONITORING.md) – Health System
  - [HEALTH_DASHBOARD.md](docs/HEALTH_DASHBOARD.md) – Dashboard Usage
  - [HEALTH_FEATURES.md](docs/HEALTH_FEATURES.md) – Verfügbare Features
  - [DASHBOARD_STARTER.md](docs/DASHBOARD_STARTER.md) – Dashboard Starter
- **Maintainer-Docs**
  - [RELEASE_PROCESS.md](docs/RELEASE_PROCESS.md) – Release-Workflow
  - [SECRET_LEAK_RESPONSE.md](docs/SECRET_LEAK_RESPONSE.md) – Secret-Leak Notfallplan
  - [PRE_RELEASE_CHECK.md](docs/PRE_RELEASE_CHECK.md) – Pre-Release Checklist
  - [PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) – Projektstruktur

---

*Letzte Aktualisierung: 2025-10-26*

