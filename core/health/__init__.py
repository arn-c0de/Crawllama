"""Health Dashboard Module for CrawlLama Test Management.

This module provides comprehensive health monitoring:
- Tkinter-based GUI for test management
- Rich terminal-based live monitoring dashboard
- System metrics (CPU, RAM, Disk, Network)
- Component health checks (LLM, Cache, RAG, Tools)
- Performance tracking (Response times, Throughput)
- Alert system (Automatic warnings)
- Easy integration helpers

Usage:
    # GUI Dashboard (for tests)
    from core.health import HealthDashboard
    dashboard = HealthDashboard()
    dashboard.run()
    
    # Terminal Dashboard (for live monitoring)
    from core.health import RichHealthDashboard
    dashboard = RichHealthDashboard(project_root)
    dashboard.start()
    
    # Quick integration with decorators
    from core.health import monitored
    
    @monitored("my_operation")
    def expensive_function():
        pass
"""

from .alert_system import Alert, AlertLevel, AlertRule, AlertSystem
from .component_checker import ComponentHealth, ComponentHealthChecker, HealthStatus
from .integration import (
    HealthMonitoringContext,
    create_monitored_llm_client,
    create_monitored_rag,
    create_monitored_web_search,
    get_alert_system,
    get_performance_tracker,
    get_system_monitor,
    monitored,
    monitored_async,
    print_health_summary,
    shutdown_monitoring,
)
from .performance_tracker import PerformanceStats, PerformanceTimer, PerformanceTracker
from .result_parser import ResultParser
from .rich_dashboard import RichHealthDashboard, run_terminal_dashboard

# New v1.2 components
from .system_monitor import SystemMetrics, SystemMonitor
from .test_collector import TestCollector
from .test_runner import TestRunner


def __getattr__(name):
    """Lazily import the Tkinter-based GUI dashboard.

    ``HealthDashboard`` depends on ``tkinter``, which is a GUI toolkit that may
    not be installed in headless/server environments. Importing it lazily keeps
    ``core.health`` usable for monitoring/tests when Tkinter is unavailable.
    """
    if name == "HealthDashboard":
        from .dashboard import HealthDashboard as _HealthDashboard
        return _HealthDashboard
    if name == "DarkTheme":
        from .theme import DarkTheme as _DarkTheme
        return _DarkTheme
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Original components
    'HealthDashboard',
    'TestRunner',
    'TestCollector',
    'ResultParser',
    'DarkTheme',
    
    # v1.2 Health Monitoring
    'SystemMonitor',
    'SystemMetrics',
    'ComponentHealthChecker',
    'HealthStatus',
    'ComponentHealth',
    'PerformanceTracker',
    'PerformanceStats',
    'PerformanceTimer',
    'AlertSystem',
    'Alert',
    'AlertLevel',
    'AlertRule',
    'RichHealthDashboard',
    'run_terminal_dashboard',
    
    # Integration helpers
    'monitored',
    'monitored_async',
    'HealthMonitoringContext',
    'create_monitored_llm_client',
    'create_monitored_web_search',
    'create_monitored_rag',
    'get_performance_tracker',
    'get_alert_system',
    'get_system_monitor',
    'print_health_summary',
    'shutdown_monitoring'
]

__version__ = '1.2.0'
