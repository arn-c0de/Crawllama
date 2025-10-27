# 🏥 Health Monitoring Dashboard v1.2

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🚀 Quickstart](../getting-started/QUICKSTART.md) | [📊 Dashboard](HEALTH_DASHBOARD.md) | [🔍 OSINT](../osint/OSINT_USAGE.md)

---

The integrated health monitoring system provides comprehensive monitoring and diagnostics for CrawlLama.

## 🌟 Features

### 📊 Live System Metrics
- **CPU Usage**: Total and per core
- **RAM Usage**: Used and available memory
- **Disk I/O**: Read/write speed and storage space
- **Network Traffic**: Upload/download rates

### 🔍 Component Health Checks
- **LLM Client**: Connection and configuration
- **Cache System**: Functionality and statistics
- **RAG System**: Embeddings and document count
- **Search Tools**: Web search and wiki lookup
- **File System**: Critical directories and storage space
- **Configuration**: Config validation

### 📈 Performance Tracking
- **Response Times**: Average, Min, Max
- **Percentiles**: P50, P95, P99
- **Success Rate**: Percentage of successful operations
- **Throughput**: Operations per minute

### 🚨 Alert System
- **Automatic Warnings**: When thresholds are exceeded
- **Priority Levels**: INFO, WARNING, ERROR, CRITICAL
- **Cooldown Mechanism**: Prevents alert spam
- **Alert History**: Tracking of all warnings

### 🎨 Rich Terminal UI
- **Color-coded Displays**: Green (good), Yellow (warning), Red (critical)
- **Live Updates**: Real-time metric updates
- **Clear Layout**: Multi-column dashboard
- **Progress Bars**: Visual representation of utilization

## 🚀 Usage

### Unified Health Dashboard

The Health Dashboard offers **two modes** in one application:

**Interactive Menu:**
```bash
# Windows
health-dashboard.bat

# Linux/Mac
./health-dashboard.sh

# Direct with Python
python health-dashboard.py
```

**Direct Start Modes:**
```bash
# Live System Monitor
python health-dashboard.py --monitor

# Test Dashboard
python health-dashboard.py --tests
```

### Mode 1: Terminal-based Live Monitoring

Real-time monitoring with Rich Terminal UI:
- System Metrics
- Component Health
- Performance Statistics
- Active Alerts

### Mode 2: GUI Test Dashboard

Tkinter-based GUI for test management:
- Test Discovery
- Test Execution
- Progress Tracking
- Results Export

## 💻 Programmatic Usage

### System Monitor

```python
from pathlib import Path
from core.health import SystemMonitor

# Initialize
monitor = SystemMonitor(update_interval=1.0)
monitor.start()

# Get metrics
metrics = monitor.get_latest_metrics()
print(f"CPU: {metrics.cpu_percent}%")
print(f"Memory: {metrics.memory_used_gb}/{metrics.memory_total_gb} GB")
print(f"Disk: {metrics.disk_percent}%")

# Stop
monitor.stop()
```

### Component Health Checker

```python
from pathlib import Path
from core.health import ComponentHealthChecker, HealthStatus

# Initialize
checker = ComponentHealthChecker(Path.cwd())

# Check all components
health = checker.check_all()

# Display results
for name, status in health.items():
    print(f"{name}: {status.status.value} - {status.message}")
    print(f"  Response Time: {status.response_time_ms:.2f}ms")
```

### Performance Tracker

```python
from core.health import PerformanceTracker, PerformanceTimer

# Initialize
tracker = PerformanceTracker()

# Track operation
with PerformanceTimer(tracker, "llm_query") as timer:
    # Your operation here
    result = expensive_operation()

# Get statistics
stats = tracker.get_stats("llm_query")
print(f"Average: {stats.avg_duration_ms:.2f}ms")
print(f"P95: {stats.p95_duration_ms:.2f}ms")
print(f"Success Rate: {stats.success_rate:.1f}%")
```

### Alert System

```python
from core.health import AlertSystem, AlertLevel

# Initialize
alerts = AlertSystem()

# Register alert callback
def on_alert(alert):
    print(f"[{alert.level.value}] {alert.component}: {alert.message}")

alerts.register_callback(on_alert)

# Check system data
alerts.check_alerts({
    'system_metrics': monitor.get_latest_metrics(),
    'component_health': checker.check_all(),
    'performance_stats': tracker.get_all_stats()
})

# Get active alerts
active = alerts.get_alerts(unacknowledged_only=True)
for alert in active:
    print(f"{alert.level.value}: {alert.message}")
```

### Rich Terminal Dashboard

```python
from pathlib import Path
from core.health import RichHealthDashboard

# Start dashboard
dashboard = RichHealthDashboard(
    project_root=Path.cwd(),
    update_interval=2.0  # Seconds
)

dashboard.start()  # Blocks until Ctrl+C
```

## 🔧 Integration in Your Code

### LLM Client with Performance Tracking

```python
from core.llm_client import LLMClient
from core.health import PerformanceTracker

tracker = PerformanceTracker()
client = LLMClient("config.json")

# Wrapper function
def tracked_query(prompt: str):
    with PerformanceTimer(tracker, "llm_query") as timer:
        try:
            response = client.generate(prompt)
            return response
        except Exception as e:
            timer.mark_failure()
            raise

# Use
response = tracked_query("What is AI?")

# Display statistics
stats = tracker.get_stats("llm_query")
print(f"Average response time: {stats.avg_duration_ms:.2f}ms")
```

### Web Search with Monitoring

```python
from tools.web_search import web_search
from core.health import PerformanceTracker

tracker = PerformanceTracker()

def monitored_search(query: str):
    with PerformanceTimer(tracker, "web_search"):
        return web_search(query)

# Use
results = monitored_search("Python tutorials")
```

## 📋 Alert Rules

### Default Rules

| Rule | Threshold | Level | Description |
|-------|-------------|-------|--------------|
| CPU Warning | 85% | WARNING | High CPU usage |
| CPU Error | 95% | ERROR | Critical CPU usage |
| Memory Warning | 85% | WARNING | High RAM usage |
| Memory Error | 95% | ERROR | Critical RAM usage |
| Disk Warning | 5 GB free | WARNING | Low storage space |
| Disk Critical | 1 GB free | CRITICAL | Very low storage space |
| Component Health | Unhealthy | ERROR | Component failure |
| Performance | P95 > 5s | WARNING | Slow performance |

### Custom Alert Rules

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
        # Your custom logic
        if some_condition:
            return "Custom alert message"
        return None

# Add rule
alerts.add_rule(CustomAlertRule())
```

## 🎯 Recommended Thresholds

### Production Environment
- CPU Warning: 70%
- CPU Error: 85%
- Memory Warning: 75%
- Memory Error: 90%
- Response Time Warning: 2000ms
- Response Time Error: 5000ms

### Development Environment
- CPU Warning: 85%
- CPU Error: 95%
- Memory Warning: 85%
- Memory Error: 95%
- Response Time Warning: 5000ms
- Response Time Error: 10000ms

## 🐛 Troubleshooting

### Dashboard Won't Start

**Problem**: `ModuleNotFoundError: No module named 'rich'`

**Solution**:
```bash
pip install rich psutil
```

### No System Metrics

**Problem**: Metrics not displayed

**Solution**: Ensure `psutil` is installed:
```bash
pip install psutil
```

### Component Checks Fail

**Problem**: All components show "Unhealthy"

**Solution**:
1. Check `config.json`
2. Ensure all directories exist:
   ```bash
   mkdir -p data/cache data/embeddings logs
   ```

### Performance Data Missing

**Problem**: No performance statistics

**Solution**: Integrate `PerformanceTimer` in your code (see examples above)

## 📊 Dashboard Layout

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

1. **Regular Monitoring**: Start the dashboard during development
2. **Performance Integration**: Use `PerformanceTimer` for critical operations
3. **Alert Callbacks**: Implement logging or notifications
4. **Adjust Thresholds**: Adapt alerts to your environment
5. **Historical Data**: Regularly export performance statistics

## 📝 Changelog

### v1.2.0 (2025-10-24)
- ✨ Live system metrics (CPU, RAM, Disk, Network)
- ✨ Component health checks
- ✨ Performance tracking with percentiles
- ✨ Alert system with configurable rules
- ✨ Rich terminal UI with live updates
- ✨ Programmatic API for all features

### v1.0.0
- 🎉 Initial version with test dashboard

## 📚 Further Resources

- [HEALTH_DASHBOARD.md](HEALTH_DASHBOARD.md) - Detailed documentation
- [README.md](README.md) - Project overview
- [QUICKSTART.md](docs/QUICKSTART.md) - Quick start guide
