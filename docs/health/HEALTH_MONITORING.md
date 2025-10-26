# 🏥 Health Monitoring Dashboard v1.2

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🚀 Quickstart](../getting-started/QUICKSTART.md) | [📊 Dashboard](HEALTH_DASHBOARD.md) | [🔍 OSINT](../osint/OSINT_USAGE.md)

---

Das integrierte Health-Monitoring-System bietet umfassende Überwachung und Diagnose für CrawlLama.

## 🌟 Features

### 📊 Live System-Metriken
- **CPU-Auslastung**: Gesamt und pro Kern
- **RAM-Nutzung**: Verwendeter und verfügbarer Speicher
- **Festplatten-I/O**: Lese-/Schreibgeschwindigkeit und Speicherplatz
- **Netzwerk-Traffic**: Upload/Download-Raten

### 🔍 Component Health Checks
- **LLM Client**: Verbindung und Konfiguration
- **Cache System**: Funktionalität und Statistiken
- **RAG System**: Embeddings und Dokumentenanzahl
- **Search Tools**: Web-Suche und Wiki-Lookup
- **File System**: Kritische Verzeichnisse und Speicherplatz
- **Configuration**: Config-Validierung

### 📈 Performance-Tracking
- **Antwortzeiten**: Durchschnitt, Min, Max
- **Perzentile**: P50, P95, P99
- **Erfolgsrate**: Prozentsatz erfolgreicher Operationen
- **Durchsatz**: Operationen pro Minute

### 🚨 Alert-System
- **Automatische Warnungen**: Bei Überschreitung von Schwellwerten
- **Prioritätsstufen**: INFO, WARNING, ERROR, CRITICAL
- **Cooldown-Mechanismus**: Verhindert Alert-Spam
- **Alert-Historie**: Nachverfolgung aller Warnungen

### 🎨 Rich Terminal UI
- **Farbcodierte Anzeigen**: Grün (gut), Gelb (Warnung), Rot (kritisch)
- **Live-Updates**: Echtzeit-Aktualisierung der Metriken
- **Übersichtliches Layout**: Mehrspaltiges Dashboard
- **Fortschrittsbalken**: Visuelle Darstellung der Auslastung

## 🚀 Verwendung

### Einheitliches Health Dashboard

Das Health Dashboard bietet **zwei Modi** in einer Anwendung:

**Interaktives Menü:**
```bash
# Windows
health-dashboard.bat

# Linux/Mac
./health-dashboard.sh

# Direkt mit Python
python health-dashboard.py
```

**Direkt-Start Modi:**
```bash
# Live System Monitor
python health-dashboard.py --monitor

# Test Dashboard
python health-dashboard.py --tests
```

### Modus 1: Terminal-basiertes Live-Monitoring

Echtzeit-Überwachung mit Rich Terminal UI:
- System-Metriken
- Component Health
- Performance-Statistiken
- Active Alerts

### Modus 2: GUI Test-Dashboard

Tkinter-basiertes GUI für Test-Management:
- Test Discovery
- Test Execution
- Progress Tracking
- Results Export

## 💻 Programmatische Nutzung

### System Monitor

```python
from pathlib import Path
from core.health import SystemMonitor

# Initialisieren
monitor = SystemMonitor(update_interval=1.0)
monitor.start()

# Metriken abrufen
metrics = monitor.get_latest_metrics()
print(f"CPU: {metrics.cpu_percent}%")
print(f"Memory: {metrics.memory_used_gb}/{metrics.memory_total_gb} GB")
print(f"Disk: {metrics.disk_percent}%")

# Stoppen
monitor.stop()
```

### Component Health Checker

```python
from pathlib import Path
from core.health import ComponentHealthChecker, HealthStatus

# Initialisieren
checker = ComponentHealthChecker(Path.cwd())

# Alle Komponenten prüfen
health = checker.check_all()

# Ergebnisse anzeigen
for name, status in health.items():
    print(f"{name}: {status.status.value} - {status.message}")
    print(f"  Response Time: {status.response_time_ms:.2f}ms")
```

### Performance Tracker

```python
from core.health import PerformanceTracker, PerformanceTimer

# Initialisieren
tracker = PerformanceTracker()

# Operation tracken
with PerformanceTimer(tracker, "llm_query") as timer:
    # Ihre Operation hier
    result = expensive_operation()

# Statistiken abrufen
stats = tracker.get_stats("llm_query")
print(f"Average: {stats.avg_duration_ms:.2f}ms")
print(f"P95: {stats.p95_duration_ms:.2f}ms")
print(f"Success Rate: {stats.success_rate:.1f}%")
```

### Alert System

```python
from core.health import AlertSystem, AlertLevel

# Initialisieren
alerts = AlertSystem()

# Alert-Callback registrieren
def on_alert(alert):
    print(f"[{alert.level.value}] {alert.component}: {alert.message}")

alerts.register_callback(on_alert)

# System-Daten prüfen
alerts.check_alerts({
    'system_metrics': monitor.get_latest_metrics(),
    'component_health': checker.check_all(),
    'performance_stats': tracker.get_all_stats()
})

# Aktive Alerts abrufen
active = alerts.get_alerts(unacknowledged_only=True)
for alert in active:
    print(f"{alert.level.value}: {alert.message}")
```

### Rich Terminal Dashboard

```python
from pathlib import Path
from core.health import RichHealthDashboard

# Dashboard starten
dashboard = RichHealthDashboard(
    project_root=Path.cwd(),
    update_interval=2.0  # Sekunden
)

dashboard.start()  # Blockiert bis Ctrl+C
```

## 🔧 Integration in eigenen Code

### LLM Client mit Performance-Tracking

```python
from core.llm_client import LLMClient
from core.health import PerformanceTracker

tracker = PerformanceTracker()
client = LLMClient("config.json")

# Wrapper-Funktion
def tracked_query(prompt: str):
    with PerformanceTimer(tracker, "llm_query") as timer:
        try:
            response = client.generate(prompt)
            return response
        except Exception as e:
            timer.mark_failure()
            raise

# Verwenden
response = tracked_query("What is AI?")

# Statistiken anzeigen
stats = tracker.get_stats("llm_query")
print(f"Average response time: {stats.avg_duration_ms:.2f}ms")
```

### Web Search mit Monitoring

```python
from tools.web_search import web_search
from core.health import PerformanceTracker

tracker = PerformanceTracker()

def monitored_search(query: str):
    with PerformanceTimer(tracker, "web_search"):
        return web_search(query)

# Verwenden
results = monitored_search("Python tutorials")
```

## 📋 Alert-Regeln

### Standard-Regeln

| Regel | Schwellwert | Level | Beschreibung |
|-------|-------------|-------|--------------|
| CPU Warning | 85% | WARNING | CPU-Auslastung hoch |
| CPU Error | 95% | ERROR | CPU-Auslastung kritisch |
| Memory Warning | 85% | WARNING | RAM-Auslastung hoch |
| Memory Error | 95% | ERROR | RAM-Auslastung kritisch |
| Disk Warning | 5 GB frei | WARNING | Wenig Speicherplatz |
| Disk Critical | 1 GB frei | CRITICAL | Sehr wenig Speicherplatz |
| Component Health | Unhealthy | ERROR | Komponente fehlerhaft |
| Performance | P95 > 5s | WARNING | Langsame Performance |

### Custom Alert-Regeln

```python
from core.health import AlertRule, AlertLevel

class CustomAlertRule(AlertRule):
    def __init__(self):
        super().__init__(
            name="Custom Rule",
            level=AlertLevel.WARNING,
            cooldown_minutes=10
        )
    
    def check(self, data: dict) -> str | None:
        # Ihre Custom-Logik
        if some_condition:
            return "Custom alert message"
        return None

# Regel hinzufügen
alerts.add_rule(CustomAlertRule())
```

## 🎯 Empfohlene Schwellwerte

### Produktionsumgebung
- CPU Warning: 70%
- CPU Error: 85%
- Memory Warning: 75%
- Memory Error: 90%
- Response Time Warning: 2000ms
- Response Time Error: 5000ms

### Entwicklungsumgebung
- CPU Warning: 85%
- CPU Error: 95%
- Memory Warning: 85%
- Memory Error: 95%
- Response Time Warning: 5000ms
- Response Time Error: 10000ms

## 🐛 Troubleshooting

### Dashboard startet nicht

**Problem**: `ModuleNotFoundError: No module named 'rich'`

**Lösung**:
```bash
pip install rich psutil
```

### Keine System-Metriken

**Problem**: Metriken werden nicht angezeigt

**Lösung**: Stellen Sie sicher, dass `psutil` installiert ist:
```bash
pip install psutil
```

### Component Checks schlagen fehl

**Problem**: Alle Components zeigen "Unhealthy"

**Lösung**:
1. Überprüfen Sie `config.json`
2. Stellen Sie sicher, dass alle Verzeichnisse existieren:
   ```bash
   mkdir -p data/cache data/embeddings logs
   ```

### Performance-Daten fehlen

**Problem**: Keine Performance-Statistiken

**Lösung**: Integrieren Sie `PerformanceTimer` in Ihren Code (siehe Beispiele oben)

## 📊 Dashboard-Layout

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🦙 CrawlLama Health Dashboard | 2025-10-24 14:30:00      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┌─────────────────────────┬─────────────────────────┐
│ 📊 System Metrics       │ 📈 Performance          │
│                         │                         │
│ CPU      45.2%  ████░░  │ llm_query   1250ms  ✓  │
│ Memory   62.1%  ██████░ │ web_search   850ms  ✓  │
│ Disk     38.5%  ███░░░  │ cache_read    25ms  ✓  │
│ Network  ↓1.2/↑0.3 MB/s │                         │
├─────────────────────────┤                         │
│ 🔍 Component Health     │                         │
│                         │                         │
│ LLM Client      ✓ 45ms  │                         │
│ Cache System    ✓ 12ms  │                         │
│ RAG System      ✓ 89ms  │                         │
│ Search Tools    ✓ 23ms  │                         │
└─────────────────────────┴─────────────────────────┘
┌─────────────────────────────────────────────────────┐
│ 🚨 Alerts (2)                                        │
│                                                      │
│ 🟡 High CPU usage: 87.5% (threshold: 85.0%)        │
│ 🟠 Slow operations: llm_query (P95: 5200ms)        │
└─────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────┐
┃ Alerts: 🔴 0 🟠 1 🟡 1 | Press Ctrl+C to exit     ┃
└─────────────────────────────────────────────────────┘
```

## 🔐 Best Practices

1. **Regelmäßiges Monitoring**: Starten Sie das Dashboard während der Entwicklung
2. **Performance-Integration**: Nutzen Sie `PerformanceTimer` für kritische Operationen
3. **Alert-Callbacks**: Implementieren Sie Logging oder Notifications
4. **Schwellwerte anpassen**: Passen Sie Alerts an Ihre Umgebung an
5. **Historische Daten**: Exportieren Sie regelmäßig Performance-Statistiken

## 📝 Changelog

### v1.2.0 (2025-10-24)
- ✨ Live System-Metriken (CPU, RAM, Disk, Network)
- ✨ Component Health Checks
- ✨ Performance-Tracking mit Perzentilen
- ✨ Alert-System mit konfigurierbaren Regeln
- ✨ Rich Terminal UI mit Live-Updates
- ✨ Programmatische API für alle Features

### v1.0.0
- 🎉 Initiale Version mit Test-Dashboard

## 📚 Weitere Ressourcen

- [HEALTH_DASHBOARD.md](HEALTH_DASHBOARD.md) - Detaillierte Dokumentation
- [README.md](README.md) - Projekt-Übersicht
- [QUICKSTART.md](docs/QUICKSTART.md) - Schnellstart-Anleitung
