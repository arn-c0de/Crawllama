# CrawlLama - Schnellstart-Anleitung

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [📦 Installation](INSTALLATION.md) | [🧠 LangGraph](../guides/LANGGRAPH_GUIDE.md) | [🔍 OSINT](../features/OSINT_USAGE.md)

---

## 🚀 Installation in 5 Minuten

### Schritt 1: Voraussetzungen prüfen

- **Python 3.10+** muss installiert sein
- **Ollama** muss installiert und laufend sein
- **Git** (zum Klonen des Repos)

### Schritt 2: Repository klonen

```bash
git clone https://github.com/arn-c0de/Crawllama.git
cd crawllama
```

### Schritt 3: Setup-Script ausführen

**Windows:**
```cmd
setup.bat
```

**Linux/macOS:**
```bash
chmod +x setup.sh
./setup.sh
```

Das Script installiert automatisch:
- Alle Python-Abhängigkeiten
- Erstellt notwendige Verzeichnisse
- Kopiert .env.example zu .env

⚠️ Hinweis zur Erstinstallation:

Beim ersten Ausführen von `pip install -r requirements.txt` innerhalb des neu erstellten `venv` kann die Installation aller Abhängigkeiten — insbesondere Pakete wie `torch`, `sentence-transformers` und wissenschaftliche Libraries — **5–10 Minuten** (oder länger, abhängig von Verbindung und Hardware) dauern. Bitte warte, bis der Vorgang abgeschlossen ist; danach ist das virtuelle Environment einsatzbereit.

### Schritt 4: Ollama starten

```bash
# In einem separaten Terminal
ollama serve
```

Hinweis zur Festplattengröße: Nach der Installation (inkl. `venv` und optionaler Modell-Downloads) benötigt das Projekt typischerweise etwa **1–2 GB** freien Festplattenspeicher. Dieser Wert kann je nach Betriebssystem, Python-Paketen (z. B. größere PyTorch-/CUDA-Wheels) und zusätzlichen Modellen deutlich höher ausfallen. Plane bei begrenztem Speicher großzügig zusätzlichen Platz ein.

Modell-Download-Größen (ungefähr):

- `qwen2.5:3b` — ca. **2–4 GB** (je nach Format/Quantisierung)
- `qwen3:8b` — ca. **8–12 GB**
- `deepseek-r1:8b` — ca. **6–10 GB**
- `llama3:7b` — ca. **6–9 GB**
- `mistral:7b` — ca. **4–8 GB**
- `phi3:14b` — ca. **12–20+ GB**

Hinweis: Modellgrößen variieren stark je nach Anbieter, Format (FP16, INT8-Quantisierung etc.) und zusätzlichen Assets. Quantisierte Modelle (z. B. INT8) können die Größe erheblich reduzieren, während FP32/FP16 oder Modelle mit zusätzlichen Tokenizer-/Vocab-Dateien mehr Platz benötigen. Plane ausreichend zusätzlichen Speicher ein, falls du größere Modelle oder mehrere Modelle gleichzeitig verwenden möchtest.

### Schritt 5: Modell herunterladen

```bash
ollama pull deepseek-r1:8b
```

Alternative Modelle:
```bash
ollama pull qwen2.5:3b   # Kleiner, schneller
ollama pull llama3:7b    # Größer, besser
ollama pull mistral:7b   # Sehr gut für Reasoning
ollama pull phi3:14b     # Noch besser, braucht mehr RAM
```

### Schritt 6: CrawlLama starten

**Windows:**
```cmd
run.bat
```

**Linux/macOS:**
```bash
./run.sh
```

**Wichtig:** Nutze immer die run-Scripts, damit das virtuelle Environment automatisch aktiviert wird!

## 💡 Erste Schritte

### Interaktiver Modus

Einfach starten und Fragen stellen:

**Windows:**
```cmd
run.bat
```

**Linux/macOS:**
```bash
./run.sh
```

```
❯ Was ist Python?
❯ Wie funktioniert Photosynthese?
❯ Wer hat die Relativitätstheorie entwickelt?
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

### Offline-Modus (ohne Web-Suche)

```cmd
run.bat --no-web "Erkläre das Sonnensystem"  # Windows
./run.sh --no-web "Erkläre das Sonnensystem"  # Linux/macOS
```

## 🔧 Konfiguration anpassen

Bearbeite `config.json`:

```json
{
  "llm": {
    "model": "deepseek-r1:8b",    // Ändere hier das Modell
    "temperature": 0.7,       // Kreativität (0.0-1.0)
    "max_tokens": 4096
  },
  "cache": {
    "enabled": true,          // Cache aktivieren/deaktivieren
    "ttl_hours": 24          // Cache-Gültigkeit
  }
}
```

## 🎯 Häufige Befehle

| Befehl (Windows) | Befehl (Linux/macOS) | Beschreibung |
|------------------|----------------------|--------------|
| `run.bat` | `./run.sh` | Interaktiver Modus |
| `run.bat "Frage"` | `./run.sh "Frage"` | Direkte Frage |
| `run.bat --stats` | `./run.sh --stats` | Statistiken anzeigen |
| `run.bat --clear-cache` | `./run.sh --clear-cache` | Cache leeren |
| `run.bat --no-web` | `./run.sh --no-web` | Offline-Modus |
| `run.bat --debug` | `./run.sh --debug` | Debug-Modus |

## ⚠️ Troubleshooting

### "Ollama is not running"

```bash
# Starte Ollama in einem separaten Terminal
ollama serve
```

### "Model not found"

```bash
# Lade das Modell herunter
ollama pull deepseek-r1:8b
```

### Import-Fehler

```bash
# Führe Setup neu aus (aktiviert automatisch venv)
setup.bat  # Windows
./setup.sh  # Linux/macOS
```

### ChromaDB-Fehler

```bash
# Lösche Embeddings und starte neu
rm -rf data/embeddings/
# Windows: rmdir /s data\embeddings
```

## 📚 Weitere Dokumentation

- **README.md** - Vollständige Dokumentation
- **[INSTALLATION.md](../getting-started/INSTALLATION.md)** - Detaillierte Setup-Anleitung
- **[LANGGRAPH_GUIDE.md](../guides/LANGGRAPH_GUIDE.md)** - Multi-Hop Reasoning Details

## 💬 Beispiel-Session

```
$ run.bat  # Windows oder ./run.sh (Linux/macOS)

╭─────────────────────────────────────────╮
│ CrawlLama - Lokaler Such- und Antwort-Agent │
╰─────────────────────────────────────────╯

❯ Was ist die Hauptstadt von Deutschland?

Verarbeite Anfrage...

Die Hauptstadt von Deutschland ist **Berlin**. Berlin ist seit der
Wiedervereinigung 1990 die Hauptstadt und zugleich ein Bundesland der
Bundesrepublik Deutschland.

❯ Wie viele Einwohner hat Berlin?

Verarbeite Anfrage...

[Sucht im Web...]

Berlin hat etwa **3,7 Millionen Einwohner** (Stand 2024) und ist damit
die bevölkerungsreichste Stadt Deutschlands.

❯ stats

{
  "tools_available": 3,
  "web_enabled": true,
  "model": "qwen2.5:3b",
  "cache": {
    "total_files": 2,
    "total_size_mb": 0.05
  }
}

❯ exit
Auf Wiedersehen!
```

## 🎉 Fertig!

Du kannst jetzt Fragen stellen und CrawlLama nutzen!

Bei Problemen: [GitHub Issues](https://github.com/arn-c0de/Crawllama/issues)
