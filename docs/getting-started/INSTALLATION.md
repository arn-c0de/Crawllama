# CrawlLama - Installation & Start

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🚀 Quickstart](QUICKSTART.md) | [🧠 LangGraph](../guides/LANGGRAPH_GUIDE.md)

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

⚠️ Hinweis zur Erstinstallation:

Beim ersten Ausführen von `pip install -r requirements.txt` innerhalb des neu erstellten `venv` kann die Installation aller Abhängigkeiten — insbesondere Pakete wie `torch`, `sentence-transformers` und wissenschaftliche Libraries — **5–10 Minuten** (oder länger, abhängig von Verbindung und Hardware) dauern. Bitte warte, bis der Vorgang abgeschlossen ist; danach ist das virtuelle Environment einsatzbereit.

3. **Modell laden:**
```cmd
ollama pull deepseek-r1:8b
```

Hinweis zur Festplattengröße: Nach der Installation (inkl. `venv` und optionaler Modell-Downloads) benötigt das Projekt typischerweise etwa **1–2 GB** freien Festplattenspeicher. Dieser Wert kann je nach Betriebssystem, Python-Paketen (z. B. größere PyTorch-/CUDA-Wheels) und zusätzlichen Modellen deutlich höher ausfallen. Plane bei begrenztem Speicher großzügig zusätzlichen Platz ein.

Modell-Download-Größen (ungefähr):

- `qwen3:4b` — ca. **2–4 GB** (je nach Format/Quantisierung)
- `qwen3:8b` — ca. **8–12 GB**
- `deepseek-r1:8b` — ca. **6–10 GB**
- `llama3:7b` — ca. **6–9 GB**
- `mistral:7b` — ca. **4–8 GB**
- `phi3:14b` — ca. **12–20+ GB**

Hinweis: Modellgrößen variieren stark je nach Anbieter, Format (FP16, INT8-Quantisierung etc.) und zusätzlichen Assets. Quantisierte Modelle (z. B. INT8) können die Größe erheblich reduzieren, während FP32/FP16 oder Modelle mit zusätzlichen Tokenizer-/Vocab-Dateien mehr Platz benötigen. Plane ausreichend zusätzlichen Speicher ein, falls du größere Modelle oder mehrere Modelle gleichzeitig verwenden möchtest.

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
ollama pull qwen3:4b

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
- **GitHub Issues:** [Crawllama Issues](https://github.com/arn-c0de/Crawllama/issues)
- **Support E-Mail:** [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com)
- **Dokumentation:** README.md, QUICKSTART.md
- **Debug-Modus:** `run.bat --debug`
