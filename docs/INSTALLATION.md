# CrawlLama - Installation & Start

---

📚 **Navigation:** [🏠 Home](../README.md) | [📖 Docs](README.md) | [🚀 Quickstart](QUICKSTART.md) | [🧠 LangGraph](LANGGRAPH_GUIDE.md)

---

## 🚀 Schnellinstallation

### Windows

1. **Setup ausführen:**
```cmd
setup.bat
```

2. **Ollama starten (separates Terminal):**
```cmd
ollama serve
```

3. **Modell laden:**
```cmd
ollama pull deepseek-r1:8b
```

4. **CrawlLama starten:**
```cmd
run.bat
```

### Linux/macOS

1. **Setup ausführen:**
```bash
chmod +x setup.sh run.sh
./setup.sh
```

2. **Ollama starten (separates Terminal):**
```bash
ollama serve
```

3. **Modell laden:**
```bash
ollama pull deepseek-r1:8b
```

4. **CrawlLama starten:**
```bash
./run.sh
```

## 📦 Was macht setup.bat/setup.sh?

1. ✅ Prüft Python-Installation (min. 3.10)
2. ✅ Erstellt virtuelles Environment (venv)
3. ✅ Aktiviert venv automatisch
4. ✅ Installiert alle Dependencies im venv
5. ✅ Erstellt notwendige Verzeichnisse (data/, logs/)
6. ✅ Kopiert .env.example zu .env
7. ✅ Prüft Ollama-Installation

## 🎮 run.bat/run.sh verwenden

**Wichtig:** Nutze IMMER die run-Scripts, damit das virtuelle Environment automatisch aktiviert wird!

### Beispiele:

```cmd
# Interaktiv
run.bat

# Direkte Frage
run.bat "Was ist Python?"

# Mit Optionen
run.bat --no-web "Offline-Frage"
run.bat --debug "Debug-Modus"
run.bat --stats
run.bat --clear-cache
```

## 🔧 Manuelle venv-Aktivierung (falls nötig)

Falls du das venv manuell aktivieren möchtest:

**Windows:**
```cmd
venv\Scripts\activate
python main.py
```

**Linux/macOS:**
```bash
source venv/bin/activate
python main.py
```

## 📂 Verzeichnisstruktur nach Installation

```
crawllama/
├── venv/                  # Virtuelles Environment (von setup erstellt)
├── data/
│   ├── cache/             # Web-Cache
│   ├── embeddings/        # ChromaDB
│   └── history/           # Chat-Verlauf
├── logs/
│   └── app.log           # Logs (automatisch erstellt)
├── setup.bat/setup.sh    # Setup-Script
├── run.bat/run.sh        # Start-Script (nutzt venv)
└── ...
```

## ⚠️ Häufige Probleme

### "venv not found"
```bash
# Setup neu ausführen
setup.bat  # oder ./setup.sh
```

### "Ollama not running"
```bash
# In separatem Terminal
ollama serve
```

### "Model not found"
```bash
ollama pull deepseek-r1:8b
```

### Dependencies fehlen
```bash
# Setup neu ausführen (installiert in venv)
setup.bat  # oder ./setup.sh
```

## 🎯 Alternative Modelle

```bash
# Standard (empfohlen)
ollama pull deepseek-r1:8b

# Schneller, kleiner
ollama pull qwen2.5:3b

# Größer, besser
ollama pull llama3:7b
ollama pull mistral:7b

# Sehr gut, braucht mehr RAM
ollama pull phi3:14b
```

## ✅ Installation testen

```cmd
# Statistiken anzeigen (ohne Frage)
run.bat --stats

# Sollte zeigen:
# - tools_available: 3
# - web_enabled: true
# - model: deepseek-r1:8b
# - cache: {...}
```

## 🆘 Support

Bei Problemen:
- **GitHub Issues:** [Link zum Repo]
- **Dokumentation:** README.md, QUICKSTART.md
- **Debug-Modus:** `run.bat --debug`
