# 🏥 Health Monitoring System v1.2 - Feature Overview

## 📋 Komponenten-Übersicht

### 1. System Monitor (`system_monitor.py`)
**Live System-Metriken in Echtzeit**

✨ Features:
- CPU-Auslastung (Gesamt + pro Kern)
- RAM-Nutzung (Verwendet/Gesamt in GB + Prozent)
- Festplatten-I/O (Lese-/Schreibrate in MB/s)
- Netzwerk-Traffic (Upload/Download in MB/s)
- Automatische Delta-Berechnung für I/O-Raten
- Thread-safe mit Background-Monitoring

🎯 Verwendung:
```python
from core.health import SystemMonitor

monitor = SystemMonitor(update_interval=1.0)
monitor.start()

metrics = monitor.get_latest_metrics()
print(f"CPU: {metrics.cpu_percent}%")
```

---

### 2. Component Health Checker (`component_checker.py`)
**Automatische Gesundheitsprüfung aller Komponenten**

✨ Features:
- LLM Client Connectivity Check
- Cache System Funktionstest
- RAG System Dokumentenzählung
- Search Tools Verfügbarkeit
- File System Integrität
- Configuration Validierung
- Async/Sync Support

🎯 Status-Levels:
- ✅ HEALTHY - Alles funktioniert
- ⚠️ DEGRADED - Eingeschränkte Funktion
- ❌ UNHEALTHY - Komponente ausgefallen
- ❓ UNKNOWN - Status unklar

🎯 Verwendung:
```python
from core.health import ComponentHealthChecker

checker = ComponentHealthChecker(project_root)
health = checker.check_all()

for name, status in health.items():
    print(f"{name}: {status.status.value}")
```

---

### 3. Performance Tracker (`performance_tracker.py`)
**Detailliertes Performance-Monitoring**

✨ Features:
- Antwortzeit-Tracking (Min/Max/Avg)
- Perzentil-Berechnung (P50/P95/P99)
- Erfolgsrate-Tracking
- Durchsatz-Messung (Ops/Min)
- Operation-History (bis zu 1000 Einträge)
- Automatisches Caching mit TTL

📊 Metriken:
- Average Duration (Durchschnittliche Dauer)
- P50 (Median)
- P95 (95% der Anfragen schneller)
- P99 (99% der Anfragen schneller)
- Success Rate (Erfolgsquote in %)
- Throughput (Operationen pro Minute)

🎯 Verwendung:
```python
from core.health import PerformanceTracker, PerformanceTimer

tracker = PerformanceTracker()

with PerformanceTimer(tracker, "my_operation"):
    expensive_function()

stats = tracker.get_stats("my_operation")
print(f"P95: {stats.p95_duration_ms}ms")
```

---

### 4. Alert System (`alert_system.py`)
**Intelligentes Warnsystem mit Regeln**

✨ Features:
- Regelbasierte Alerts
- 4 Prioritätsstufen (INFO/WARNING/ERROR/CRITICAL)
- Cooldown-Mechanismus (verhindert Spam)
- Alert-Historie mit Acknowledgement
- Custom Alert Rules
- Callback-System für Notifications

🚨 Standard-Regeln:
- CPU > 85% → WARNING
- CPU > 95% → ERROR
- Memory > 85% → WARNING
- Memory > 95% → ERROR
- Disk < 5 GB → WARNING
- Disk < 1 GB → CRITICAL
- Component Unhealthy → ERROR
- Performance P95 > 5s → WARNING

🎯 Verwendung:
```python
from core.health import AlertSystem

alerts = AlertSystem()

# Callback registrieren
def on_alert(alert):
    print(f"Alert: {alert.message}")

alerts.register_callback(on_alert)

# Alerts prüfen
alerts.check_alerts({
    'system_metrics': metrics,
    'component_health': health
})
```

---

### 5. Rich Dashboard (`rich_dashboard.py`)
**Schöne Terminal-basierte Live-Anzeige**

✨ Features:
- Multi-Panel-Layout
- Live-Updates (konfigurierbar)
- Farbcodierte Status-Anzeigen
- Fortschrittsbalken für Auslastung
- Alert-Zusammenfassung
- Automatische Component-Checks
- Keyboard-Interrupt-Safe

🎨 UI-Elemente:
- 📊 System Metrics Panel (CPU/RAM/Disk/Network)
- 🔍 Component Health Panel (mit Status-Icons)
- 📈 Performance Panel (Top 5 Operationen)
- 🚨 Alerts Panel (Top 5 aktive Warnungen)
- 📌 Header mit Timestamp
- 📊 Footer mit Alert-Zusammenfassung

🎯 Verwendung:
```python
from core.health import RichHealthDashboard

dashboard = RichHealthDashboard(project_root)
dashboard.start()  # Blockiert bis Ctrl+C
```

---

### 6. Integration Helpers (`integration.py`)
**Einfache Integration in bestehenden Code**

✨ Features:
- @monitored Decorator (sync)
- @monitored_async Decorator (async)
- HealthMonitoringContext Context Manager
- Pre-wrapped Components (LLM, Search, RAG)
- Global Singleton Instances
- Quick Health Summary Print

🎯 Decorator-Beispiel:
```python
from core.health import monitored

@monitored("llm_query")
def generate_response(prompt):
    return llm.generate(prompt)
```

🎯 Context Manager:
```python
from core.health import HealthMonitoringContext

with HealthMonitoringContext() as monitor:
    # Ihr Code hier
    monitor.check_alerts()
```

🎯 Pre-wrapped Components:
```python
from core.health import create_monitored_llm_client

client = create_monitored_llm_client("config.json")
# Alle Aufrufe werden automatisch getrackt
```

---

## 🚀 Schnellstart-Szenarien

### Szenario 1: Sofort-Überwachung starten
```bash
# Terminal Dashboard
python health-monitor.py

# Oder mit Batch/Shell
health-monitor.bat     # Windows
./health-monitor.sh    # Linux/Mac
```

### Szenario 2: Test-Dashboard für Entwicklung
```bash
python health-dashboard.py
```

### Szenario 3: Integration in eigenen Code
```python
# Minimale Integration
from core.health import monitored, print_health_summary
import atexit

@monitored("main_task")
def main():
    pass

atexit.register(print_health_summary)
```

### Szenario 4: Vollständige Integration
```python
from core.health import (
    SystemMonitor,
    PerformanceTracker,
    AlertSystem,
    HealthMonitoringContext
)

class MyApp:
    def __init__(self):
        self.monitor = SystemMonitor()
        self.monitor.start()
    
    def run(self):
        with HealthMonitoringContext() as health:
            # Ihre App-Logik
            pass
```

---

## 📊 Beispiel-Dashboard-Output

```
╔══════════════════════════════════════════════════════════╗
║ 🦙 CrawlLama Health Dashboard | 2025-10-24 14:30:00     ║
╚══════════════════════════════════════════════════════════╝

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

Alerts: 🔴 0 🟠 1 🟡 1 | Press Ctrl+C to exit
```

---

## 📈 Performance-Metriken Interpretation

### Response Time Guideline
- **< 100ms**: Exzellent (grün) ⚡
- **100-500ms**: Gut (grün) ✓
- **500-1000ms**: Akzeptabel (gelb) ⚠️
- **1000-2000ms**: Langsam (gelb) ⚠️
- **> 2000ms**: Sehr langsam (rot) 🔴

### Throughput Guideline
- **> 60 ops/min**: Hoher Durchsatz ⚡
- **30-60 ops/min**: Guter Durchsatz ✓
- **10-30 ops/min**: Niedriger Durchsatz ⚠️
- **< 10 ops/min**: Sehr niedriger Durchsatz 🔴

### Success Rate
- **100%**: Perfekt ✓
- **95-99%**: Sehr gut ✓
- **90-95%**: Gut (etwas Fehlerrate) ⚠️
- **< 90%**: Problematisch 🔴

---

## 🔧 Konfiguration & Anpassung

### Alert-Schwellwerte anpassen
```python
from core.health import AlertSystem, CPUAlertRule, AlertLevel

alerts = AlertSystem()
alerts.rules.clear()  # Standard-Regeln entfernen

# Custom Regel hinzufügen
alerts.add_rule(CPUAlertRule(
    threshold=70.0,
    level=AlertLevel.WARNING
))
```

### Performance-Tracking-Window anpassen
```python
from core.health import PerformanceTracker

tracker = PerformanceTracker(
    max_history=2000,      # 2000 Einträge behalten
    window_minutes=30      # 30-Minuten-Fenster für Durchsatz
)
```

### System-Monitor-Intervall anpassen
```python
from core.health import SystemMonitor

monitor = SystemMonitor(update_interval=0.5)  # 0.5s Updates
```

---

## 📦 Abhängigkeiten

Alle bereits in `requirements.txt`:
- ✅ `rich>=13.0.0` - Terminal UI
- ✅ `psutil>=5.9.0` - System-Metriken

Keine zusätzliche Installation nötig!

---

## 🐛 Troubleshooting

### Problem: "No module named 'rich'"
**Lösung:** `pip install rich psutil`

### Problem: Dashboard zeigt keine Metriken
**Lösung:** Warten Sie 1-2 Sekunden nach Start für erste Metriken

### Problem: Component Checks schlagen fehl
**Lösung:** 
1. Prüfen Sie `config.json`
2. Erstellen Sie fehlende Verzeichnisse: `mkdir -p data/cache data/embeddings`

### Problem: Performance-Daten fehlen
**Lösung:** Integrieren Sie `@monitored` Decorator in Ihren Code

---

## 🎯 Best Practices

1. **Starten Sie System Monitor früh**: Im `__init__` oder `main()`
2. **Verwenden Sie Decorators**: Einfachste Integration
3. **Registrieren Sie Alert-Callbacks**: Für Logging/Notifications
4. **Prüfen Sie Health periodisch**: Alle 30-60 Sekunden
5. **Exportieren Sie Metriken**: Für historische Analyse
6. **Passen Sie Schwellwerte an**: Je nach Ihrer Umgebung
7. **Monitoren Sie kritische Pfade**: LLM, Search, RAG
8. **Nutzen Sie Context Manager**: Für temporäres Monitoring

---

## 📚 Dokumentation

- **[HEALTH_MONITORING.md](HEALTH_MONITORING.md)** - Vollständige Dokumentation
- **[examples/health_monitoring_example.py](../examples/health_monitoring_example.py)** - Vollständiges Beispiel
- **[examples/health_quickstart.py](../examples/health_quickstart.py)** - Quick-Start-Snippets
- **[tests/test_health_monitoring.py](../tests/test_health_monitoring.py)** - Verifikations-Tests

---

## ✨ Version History

**v1.2.0 (2025-10-24)**
- ✨ System Monitor (CPU, RAM, Disk, Network)
- ✨ Component Health Checker (6 Komponenten)
- ✨ Performance Tracker (mit Perzentilen)
- ✨ Alert System (8 Standard-Regeln)
- ✨ Rich Terminal Dashboard
- ✨ Integration Helpers (Decorators, Context Manager)
- 📝 Umfangreiche Dokumentation
- 🧪 Test-Suite

---

**Made with ❤️ for CrawlLama v1.2**
