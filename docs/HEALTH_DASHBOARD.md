# 🦙 CrawlLama Health Dashboard

---

📚 **Navigation:** [🏠 Home](../README.md) | [📖 Docs](README.md) | [🏥 Health Monitoring](HEALTH_MONITORING.md) | [⚙️ Features](HEALTH_FEATURES.md)

---

Ein umfassendes Tkinter-basiertes Test-Management-Dashboard für CrawlLama.

## Features

✅ **Automatische Test-Discovery** - Findet alle `test_*.py` Dateien im `tests/` Ordner
✅ **Einzelne & Batch-Ausführung** - Tests einzeln oder alle auf einmal ausführen
✅ **Live Progress Tracking** - Echtzeit-Status während der Ausführung
✅ **Detaillierte Fehler-Logs** - Vollständige Tracebacks und Error-Details
✅ **Kategorisierung** - Tests nach Typ gruppiert (Unit, Integration, OSINT, etc.)
✅ **Export-Funktionen** - Ergebnisse als JSON oder HTML exportieren
✅ **Parallele Ausführung** - Optional Tests parallel ausführen

## Installation

### Requirements

```bash
# Basis-Requirements
pip install pytest pytest-json-report pytest-timeout

# Optional für Clipboard-Support
pip install pyperclip
```

### Tkinter Installation

**Windows & macOS:** Tkinter ist normalerweise bereits mit Python installiert.

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

## Verwendung

### Dashboard starten

```bash
python test-dash.py
```

Das öffnet das Health Dashboard GUI.

### Bedienung

#### 1. **Test-Übersicht**
- Linke Seite: Hierarchische Ansicht aller Tests
- Tests sind nach Kategorien gruppiert:
  - 📁 UNIT - Unit-Tests
  - 📁 INTEGRATION - Integrationstests
  - 📁 OSINT - OSINT-Tests
  - 📁 ROBUSTNESS - Robustness-Tests
  - 📁 MULTIHOP - Multi-Hop-Reasoning-Tests

#### 2. **Status-Karten** (Oben)
- ✅ **Passed** - Anzahl bestandener Tests
- ❌ **Failed** - Anzahl fehlgeschlagener Tests
- ⏭️ **Skipped** - Anzahl übersprungener Tests
- ⏱️ **Duration** - Gesamtdauer

#### 3. **Control Buttons**
- **▶️ Run All Tests** - Alle Tests ausführen
- **▶️ Run Selected** - Ausgewählten Test ausführen
- **⏹️ Stop** - Laufende Tests stoppen
- **🔄 Refresh** - Test-Liste neu laden
- **🗑️ Clear** - Ergebnisse löschen
- **📊 Export** - Ergebnisse exportieren

#### 4. **Progress Panel**
Zeigt Live-Updates während der Test-Ausführung:
- Progress Bar
- Aktueller Test
- Passed/Failed/Skipped Counts

#### 5. **Error Log Viewer** (Unten)
Zeigt detaillierte Fehlerinformationen:
- Test-Datei und Funktion
- Error Messages
- Tracebacks
- **📋 Copy** - In Zwischenablage kopieren
- **💾 Export** - Als Textdatei speichern

### Keyboard Shortcuts

- **Double-Click auf Test** → Test ausführen
- **Menü → Tests → Run All** → Alle Tests ausführen

### Export-Funktionen

#### JSON Export
```
File → Export Results (JSON)
```
Exportiert vollständige Test-Ergebnisse im JSON-Format:
```json
{
  "summary": {
    "total_tests": 15,
    "passed": 12,
    "failed": 2,
    "skipped": 1,
    "pass_rate": 80.0,
    "duration": 15.8
  },
  "results": [...],
  "failed_tests": [...],
  "category_summary": {...}
}
```

#### HTML Report
```
File → Export Results (HTML)
```
Generiert einen übersichtlichen HTML-Report mit:
- Zusammenfassung
- Status-Karten
- Detaillierte Test-Liste

## Architektur

```
core/health/
├── __init__.py              # Modul-Init
├── dashboard.py             # Haupt-GUI
├── test_collector.py        # Test-Discovery
├── test_runner.py           # Test-Ausführung
├── result_parser.py         # Ergebnis-Parsing
└── widgets/                 # Custom Widgets
    ├── test_tree.py         # TreeView für Tests
    ├── status_card.py       # Status-Karten
    ├── progress_panel.py    # Progress Bar
    └── log_viewer.py        # Error Log Viewer
```

## Workflow

1. **Test Discovery**
   ```
   TestCollector → Findet alle test_*.py → Parsed Funktionen
   ```

2. **Test Execution**
   ```
   TestRunner → pytest subprocess → JSON Report → Result Parsing
   ```

3. **UI Updates**
   ```
   Callback → Update TreeView → Update Status Cards → Update Logs
   ```

## Kategorisierung

Tests werden automatisch kategorisiert basierend auf Dateinamen:

| Kategorie | Keywords | Beispiele |
|-----------|----------|-----------|
| Unit | cache, llm_client, rate_limiter | test_cache.py |
| Integration | integration, web_search | test_integration.py |
| OSINT | osint, ddgs | test_osint.py |
| Robustness | robustness, error_simulation | test_robustness_simple.py |
| Multihop | multihop_reasoning | test_multihop_reasoning.py |

## Parallele Ausführung

Aktiviere "Parallel Execution" Checkbox für schnellere Test-Ausführung:
- Standard: 4 parallele Workers
- Achtung: Manche Tests könnten Ressourcen-Konflikte haben

## Troubleshooting

### "No tests found"
```bash
# Stelle sicher, dass tests/ Verzeichnis existiert
ls tests/

# Teste Test-Discovery manuell
python -c "from core.health import TestCollector; print(TestCollector().discover_tests())"
```

### "pytest not found"
```bash
pip install pytest pytest-json-report
```

### Tkinter ImportError
```bash
# Windows/macOS: Python neu installieren mit tcl/tk Support
# Linux: python3-tk installieren (siehe Installation oben)
```

### Tests hängen sich auf
- Drücke **Stop** Button
- Überprüfe Test-Code auf Infinite Loops
- Aktiviere Timeout: Tests haben automatisch 5min Timeout

## Best Practices

1. **Nach jedem Patch**
   - Dashboard öffnen
   - "Run All Tests" ausführen
   - Fehler in Log Viewer analysieren

2. **Vor Commits**
   - Alle Tests grün machen
   - HTML Report exportieren
   - Report in Commit-Message erwähnen

3. **CI/CD Integration**
   ```bash
   # Dashboard auch für CI/CD Reports nutzen
   pytest --json-report --json-report-file=results.json
   # results.json ins Dashboard laden
   ```

## Beispiel-Output

```
═══════════════════════════════════════════════
🦙 CrawlLama Health Dashboard
═══════════════════════════════════════════════

✅ Checking dependencies...
✅ All dependencies available

Launching Health Dashboard...
Close the window or press Ctrl+C to exit

[Dashboard GUI öffnet sich]

═══════════════════════════════════════════════
Test Results
═══════════════════════════════════════════════
Total Tests:    15
Passed:         12
Failed:         2
Skipped:        1
Pass Rate:      80.0%
Duration:       15.8s
═══════════════════════════════════════════════
```

## Erweiterungen

Das Dashboard kann einfach erweitert werden:

1. **Neue Kategorien** → `test_collector.py` anpassen
2. **Custom Reports** → `result_parser.py` erweitern
3. **Neue Widgets** → In `widgets/` hinzufügen
4. **CI/CD Integration** → JSON Export nutzen

## Support

Bei Problemen:
1. Prüfe `pytest --version`
2. Teste manuelle Test-Ausführung: `pytest tests/test_example.py -v`
3. Prüfe Dashboard Logs auf Fehler

## Lizenz

Teil des CrawlLama Projekts © 2025
