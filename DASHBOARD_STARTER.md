# 🦙 Health Dashboard - Quick Start Guide

Einfache Starter-Scripts für das Health Dashboard.

## 🚀 Schnellstart

### Windows
Doppelklick auf:
```
start-dashboard.bat
```

Oder in PowerShell/CMD:
```cmd
.\start-dashboard.bat
```

### Linux/Mac
```bash
chmod +x start-dashboard.sh  # Einmalig ausführbar machen
./start-dashboard.sh
```

---

## 📋 Was die Scripts machen

1. ✅ Prüfen ob venv existiert
2. ✅ venv automatisch aktivieren
3. ✅ Health Dashboard starten
4. ✅ Error-Handling falls etwas schief geht

---

## 🔧 Erste Einrichtung

Falls venv noch nicht existiert:

### Windows
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Linux/Mac
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 📝 Manuelle Ausführung

Falls du die Scripts nicht nutzen willst:

### Windows (PowerShell/CMD)
```cmd
cd C:\Artificial-Intelligent\Crawllama
venv\Scripts\activate
python health-dashboard.py
```

### Linux/Mac (Bash)
```bash
cd /path/to/Crawllama
source venv/bin/activate
python health-dashboard.py
```

---

## ⚙️ Verfügbare Dashboard-Versionen

### 1. Standard Dashboard (empfohlen)
```bash
python health-dashboard.py
```
- Automatische Detection von pytest-json-report
- Fallback auf Text-Parsing falls Plugin fehlt
- Dark Mode
- Alle Features

### 2. Simple Dashboard (Text-Only)
```bash
python test-dash-simple.py
```
- Nur Text-Parsing (kein pytest-json-report nötig)
- Gleiche Features
- Dark Mode
- Für wenn JSON-Report Probleme macht

---

## 🐛 Troubleshooting

### "Virtual environment not found"
```bash
# Erstelle venv neu
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Dependencies installieren
pip install pytest
```

### "tkinter not found"
**Windows/macOS:**
- Python neu installieren mit tcl/tk Support

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

### Dashboard startet nicht
```bash
# Debug-Modus
python health-dashboard.py --verbose

# Oder prüfe Dependencies
pip list | grep pytest
python -c "import tkinter; print('tkinter OK')"
```

### Tests werden nicht gefunden
```bash
# Prüfe ob tests/ existiert
ls tests/

# Prüfe ob test_*.py Dateien da sind
ls tests/test_*.py
```

---

## 📊 Nach dem Start

Das Dashboard zeigt:
- 📁 Alle test_*.py Dateien im `tests/` Ordner
- ✅ Status: PASSED, FAILED, SKIPPED, ERROR
- ⏱️ Ausführungszeit pro Test
- 📝 Detaillierte Fehler-Logs
- 📊 Export als JSON/HTML

### Bedienung

1. **Tests laden:** Automatisch beim Start
2. **Alle Tests ausführen:** Button "▶️ Run All Tests"
3. **Einzelnen Test:** Doppelklick auf Test in TreeView
4. **Parallele Ausführung:** Checkbox "Parallel Execution" aktivieren
5. **Export:** Button "📊 Export" → JSON oder HTML

---

## 🎨 Dark Mode

Das Dashboard nutzt automatisch ein VS Code-inspiriertes Dark Theme:
- Dunkler Hintergrund (#1e1e1e)
- Grüne PASSED Tests (#4ec9b0)
- Rote FAILED Tests (#f48771)
- Blaue RUNNING Tests (#569cd6)

---

## 🔄 Updates

Nach Git Pull:
```bash
# Windows
.\start-dashboard.bat

# Linux/Mac
./start-dashboard.sh
```

Die Scripts aktivieren automatisch die venv!

---

## 💡 Tipps

### Schneller Workflow
1. Nach Code-Änderung
2. Dashboard öffnen (`start-dashboard.bat`)
3. "Run All Tests" klicken
4. Errors im Log Viewer prüfen
5. Code fixen, Dashboard bleibt offen
6. Nochmal "Run All Tests"

### Test-Cleanup
```bash
# Alte/kaputte Tests entfernen
python cleanup_old_tests.py
```

### Keyboard Shortcuts
- **Doppelklick** auf Test → Ausführen
- **Ctrl+C** in Terminal → Dashboard schließen

---

## 📚 Weitere Hilfe

- **Vollständige Doku:** `HEALTH_DASHBOARD.md`
- **Troubleshooting:** `core/health/TROUBLESHOOTING.md`
- **Test Cleanup:** `TEST_CLEANUP_RECOMMENDATIONS.md`

---

## ✅ Checkliste

Nach Projekt-Setup:
- [ ] venv erstellt und aktiviert
- [ ] pytest installiert (`pip install pytest`)
- [ ] start-dashboard.bat/.sh ausführbar
- [ ] Dashboard startet ohne Errors
- [ ] Tests werden gefunden
- [ ] Tests laufen durch

Alles grün? Dann bist du ready! 🎉
