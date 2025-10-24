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

from .dashboard import HealthDashboard
from .test_runner import TestRunner
from .test_collector import TestCollector
from .result_parser import ResultParser
from .theme import DarkTheme

# New v1.2 components
from .system_monitor import SystemMonitor, SystemMetrics
from .component_checker import ComponentHealthChecker, HealthStatus, ComponentHealth
from .performance_tracker import PerformanceTracker, PerformanceStats, PerformanceTimer
from .alert_system import AlertSystem, Alert, AlertLevel, AlertRule
from .rich_dashboard import RichHealthDashboard, run_terminal_dashboard
from .integration import (
    monitored,
    monitored_async,
    HealthMonitoringContext,
    create_monitored_llm_client,
    create_monitored_web_search,
    create_monitored_rag,
    get_performance_tracker,
    get_alert_system,
    get_system_monitor,
    print_health_summary,
    shutdown_monitoring
)

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
