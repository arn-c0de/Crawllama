# Health Monitoring System v1.2 - Feature Overview

---

 **Navigation:** [Home](../../README.md) | [Docs](../README.md) | [Health Monitoring](HEALTH_MONITORING.md) | [Dashboard](HEALTH_DASHBOARD.md) | [Starter](DASHBOARD_STARTER.md)

---

## Component Overview

### 1. System Monitor (`system_monitor.py`)
**Live System Metrics in Real-time**

 Features:
- CPU usage (Total + per core)
- RAM usage (Used/Total in GB + Percent)
- Disk I/O (Read/write rate in MB/s)
- Network traffic (Upload/download in MB/s)
- Automatic delta calculation for I/O rates
- Thread-safe with background monitoring

 Usage:
```python
from core.health import SystemMonitor

monitor = SystemMonitor(update_interval=1.0)
monitor.start()

metrics = monitor.get_latest_metrics()
print(f"CPU: {metrics.cpu_percent}%")
```

---

### 2. Component Health Checker (`component_checker.py`)
**Automatic Health Check of All Components**

 Features:
- LLM Client connectivity check
- Cache system functionality test
- RAG system document count
- Search tools availability
- File system integrity
- Configuration validation
- Async/sync support

 Status Levels:
- HEALTHY - Everything working
- DEGRADED - Limited functionality
- UNHEALTHY - Component failed
- UNKNOWN - Status unclear

 Usage:
```python
from core.health import ComponentHealthChecker

checker = ComponentHealthChecker(project_root)
health = checker.check_all()

for name, status in health.items():
 print(f"{name}: {status.status.value}")
```

---

### 3. Performance Tracker (`performance_tracker.py`)
**Detailed Performance Monitoring**

 Features:
- Response time tracking (Min/Max/Avg)
- Percentile calculation (P50/P95/P99)
- Success rate tracking
- Throughput measurement (Ops/Min)
- Operation history (up to 1000 entries)
- Automatic caching with TTL

 Metrics:
- Average Duration
- P50 (Median)
- P95 (95% of requests faster)
- P99 (99% of requests faster)
- Success Rate (in %)
- Throughput (Operations per minute)

 Usage:
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
**Intelligent Warning System with Rules**

 Features:
- Rule-based alerts
- 4 priority levels (INFO/WARNING/ERROR/CRITICAL)
- Cooldown mechanism (prevents spam)
- Alert history with acknowledgement
- Custom alert rules
- Callback system for notifications

 Default Rules:
- CPU > 85% → WARNING
- CPU > 95% → ERROR
- Memory > 85% → WARNING
- Memory > 95% → ERROR
- Disk < 5 GB → WARNING
- Disk < 1 GB → CRITICAL
- Component Unhealthy → ERROR
- Performance P95 > 5s → WARNING

 Usage:
```python
from core.health import AlertSystem

alerts = AlertSystem()

# Register callback
def on_alert(alert):
 print(f"Alert: {alert.message}")

alerts.register_callback(on_alert)

# Check alerts
alerts.check_alerts({
 'system_metrics': metrics,
 'component_health': health
})
```

---

### 5. Rich Dashboard (`rich_dashboard.py`)
**Beautiful Terminal-based Live Display**

 Features:
- Multi-panel layout
- Live updates (configurable)
- Color-coded status displays
- Progress bars for utilization
- Alert summary
- Automatic component checks
- Keyboard-interrupt safe

 UI Elements:
- System Metrics Panel (CPU/RAM/Disk/Network)
- Component Health Panel (with status icons)
- Performance Panel (Top 5 operations)
- Alerts Panel (Top 5 active warnings)
- Header with timestamp
- Footer with alert summary

 Usage:
```python
from core.health import RichHealthDashboard

dashboard = RichHealthDashboard(project_root)
dashboard.start() # Blocks until Ctrl+C
```

---

### 6. Integration Helpers (`integration.py`)
**Easy Integration into Existing Code**

 Features:
- @monitored Decorator (sync)
- @monitored_async Decorator (async)
- HealthMonitoringContext Context Manager
- Pre-wrapped Components (LLM, Search, RAG)
- Global Singleton Instances
- Quick Health Summary Print

 Decorator Example:
```python
from core.health import monitored

@monitored("llm_query")
def generate_response(prompt):
 return llm.generate(prompt)
```

 Context Manager:
```python
from core.health import HealthMonitoringContext

with HealthMonitoringContext() as monitor:
 # Your code here
 monitor.check_alerts()
```

 Pre-wrapped Components:
```python
from core.health import create_monitored_llm_client

client = create_monitored_llm_client("config.json")
# All calls are automatically tracked
```

---

## Quick Start Scenarios

### Scenario 1: Start Monitoring Immediately
```bash
# Terminal dashboard
python health-dashboard.py --monitor

# Or with batch/shell
health-dashboard.bat # Windows
./health-dashboard.sh # Linux/Mac
```

### Scenario 2: Test Dashboard for Development
```bash
python health-dashboard.py
```

### Scenario 3: Integration in Your Code
```python
# Minimal integration
from core.health import monitored, print_health_summary
import atexit

@monitored("main_task")
def main():
 pass

atexit.register(print_health_summary)
```

### Scenario 4: Full Integration
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
 # Your app logic
 pass
```

---

## Example Dashboard Output

```
╔══════════════════════════════════════════════════════════╗
║ CrawlLama Health Dashboard | 2025-10-24 14:30:00 ║
╚══════════════════════════════════════════════════════════╝

┌─────────────────────────┬─────────────────────────┐
│ System Metrics │ Performance │
│ │ │
│ CPU 45.2% ████░░ │ llm_query 1250ms │
│ Memory 62.1% ██████░ │ web_search 850ms │
│ Disk 38.5% ███░░░ │ cache_read 25ms │
│ Network ↓1.2/↑0.3 MB/s │ │
├─────────────────────────┤ │
│ Component Health │ │
│ │ │
│ LLM Client 45ms │ │
│ Cache System 12ms │ │
│ RAG System 89ms │ │
│ Search Tools 23ms │ │
└─────────────────────────┴─────────────────────────┘
┌─────────────────────────────────────────────────────┐
│ Alerts (2) │
│ │
│ High CPU usage: 87.5% (threshold: 85.0%) │
│ Slow operations: llm_query (P95: 5200ms) │
└─────────────────────────────────────────────────────┘

Alerts: 0 1 1 | Press Ctrl+C to exit
```

---

## Performance Metrics Interpretation

### Response Time Guideline
- **< 100ms**: Excellent (green) 
- **100-500ms**: Good (green) 
- **500-1000ms**: Acceptable (yellow) 
- **1000-2000ms**: Slow (yellow) 
- **> 2000ms**: Very slow (red) 

### Throughput Guideline
- **> 60 ops/min**: High throughput 
- **30-60 ops/min**: Good throughput 
- **10-30 ops/min**: Low throughput 
- **< 10 ops/min**: Very low throughput 

### Success Rate
- **100%**: Perfect 
- **95-99%**: Very good 
- **90-95%**: Good (some error rate) 
- **< 90%**: Problematic 

---

## Configuration & Customization

### Adjust Alert Thresholds
```python
from core.health import AlertSystem, AlertLevel
from core.health.alert_system import CPUAlertRule

alerts = AlertSystem()
alerts.rules.clear() # Remove default rules

# Add custom rule
alerts.add_rule(CPUAlertRule(
 threshold=70.0,
 level=AlertLevel.WARNING
))
```

### Adjust Performance Tracking Window
```python
from core.health import PerformanceTracker

tracker = PerformanceTracker(
 max_history=2000, # Keep 2000 entries
 window_minutes=30 # 30-minute window for throughput
)
```

### Adjust System Monitor Interval
```python
from core.health import SystemMonitor

monitor = SystemMonitor(update_interval=0.5) # 0.5s updates
```

---

## Dependencies

All already in `pyproject.toml`:
- `rich>=15.0.0` - Terminal UI
- `psutil>=7.2.2` - System metrics

No additional installation needed!

---

## Troubleshooting

### Problem: "No module named 'rich'"
**Solution:** `pip install rich psutil`

### Problem: Dashboard shows no metrics
**Solution:** Wait 1-2 seconds after start for first metrics

### Problem: Component checks fail
**Solution:**
1. Check `config.json`
2. Create missing directories: `mkdir -p data/cache data/embeddings`

### Problem: Performance data missing
**Solution:** Integrate `@monitored` decorator in your code

---

## Best Practices

1. **Start System Monitor Early**: In `__init__` or `main()`
2. **Use Decorators**: Easiest integration
3. **Register Alert Callbacks**: For logging/notifications
4. **Check Health Periodically**: Every 30-60 seconds
5. **Export Metrics**: For historical analysis
6. **Adjust Thresholds**: Based on your environment
7. **Monitor Critical Paths**: LLM, Search, RAG
8. **Use Context Manager**: For temporary monitoring

---

## Documentation

- **[HEALTH_MONITORING.md](HEALTH_MONITORING.md)** - Complete documentation
- **[tests/other/test_health_monitoring.py](../../tests/other/test_health_monitoring.py)** - Verification tests

---

## Version History

**v1.2.0 (2025-10-24)**
- System Monitor (CPU, RAM, Disk, Network)
- Component Health Checker (6 components)
- Performance Tracker (with percentiles)
- Alert System (8 default rules)
- Rich Terminal Dashboard
- Integration Helpers (Decorators, Context Manager)
- Comprehensive documentation
- Test suite

---

**Made with for CrawlLama v1.2**
