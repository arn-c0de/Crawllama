"""Integration Helper: Add Health Monitoring to Core Components.

This module provides easy integration of health monitoring
into existing CrawlLama components.
"""

from typing import Optional, Callable
import functools
import threading
import time

# Global tracker instances (lazy initialized)
_performance_tracker = None
_alert_system = None
_system_monitor = None
_monitor_lock = threading.Lock()


def get_performance_tracker():
    """Get or create global performance tracker."""
    global _performance_tracker
    if _performance_tracker is None:
        from core.health import PerformanceTracker
        _performance_tracker = PerformanceTracker()
    return _performance_tracker


def get_alert_system():
    """Get or create global alert system."""
    global _alert_system
    if _alert_system is None:
        from core.health import AlertSystem
        _alert_system = AlertSystem()
    return _alert_system


def get_system_monitor():
    """Get or create global system monitor."""
    global _system_monitor
    if _system_monitor is None:
        with _monitor_lock:
            if _system_monitor is None:
                from core.health import SystemMonitor
                _system_monitor = SystemMonitor(update_interval=1.0)
                _system_monitor.start()
    return _system_monitor


def monitored(operation_name: Optional[str] = None):
    """Decorator to automatically track function performance.
    
    Args:
        operation_name: Custom operation name, defaults to function name
    
    Example:
        @monitored("llm_query")
        def generate_response(prompt):
            return llm.generate(prompt)
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracker = get_performance_tracker()
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                tracker.record(
                    operation=op_name,
                    duration_ms=duration_ms,
                    success=success
                )
        
        return wrapper
    return decorator


def monitored_async(operation_name: Optional[str] = None):
    """Decorator to automatically track async function performance.
    
    Args:
        operation_name: Custom operation name, defaults to function name
    
    Example:
        @monitored_async("web_search")
        async def search(query):
            return await search_api(query)
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation_name or func.__name__
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracker = get_performance_tracker()
            start_time = time.time()
            success = True
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                tracker.record(
                    operation=op_name,
                    duration_ms=duration_ms,
                    success=success
                )
        
        return wrapper
    return decorator


class HealthMonitoringContext:
    """Context manager for health monitoring in a section of code.
    
    Example:
        with HealthMonitoringContext() as monitor:
            # Your code here
            result = expensive_operation()
            
            # Optional: manually check alerts
            monitor.check_alerts()
    """
    
    def __init__(self, check_alerts: bool = True, interval: float = 30.0):
        """Initialize monitoring context.
        
        Args:
            check_alerts: Whether to check alerts on exit
            interval: Minimum seconds between alert checks
        """
        self.check_alerts_enabled = check_alerts
        self.check_interval = interval
        self._last_check = 0
        self.tracker = get_performance_tracker()
        self.alerts = get_alert_system()
        self.monitor = get_system_monitor()
    
    def __enter__(self):
        """Enter context."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and optionally check alerts."""
        if self.check_alerts_enabled:
            self.check_alerts()
        return False
    
    def check_alerts(self, force: bool = False):
        """Check alerts if interval has passed.
        
        Args:
            force: Force check even if interval hasn't passed
        """
        current_time = time.time()
        
        if force or (current_time - self._last_check) >= self.check_interval:
            
            # Get current metrics
            metrics = self.monitor.get_latest_metrics()
            stats = self.tracker.get_all_stats()
            
            # Check alerts
            self.alerts.check_alerts({
                'system_metrics': metrics,
                'performance_stats': stats
            })
            
            self._last_check = current_time
    
    def get_stats(self, operation: Optional[str] = None):
        """Get performance stats.
        
        Args:
            operation: Specific operation name, or None for all
        """
        if operation:
            return self.tracker.get_stats(operation)
        return self.tracker.get_all_stats()
    
    def get_metrics(self):
        """Get latest system metrics."""
        return self.monitor.get_latest_metrics()


def create_monitored_llm_client(config_path: str):
    """Create LLM client with automatic performance monitoring.
    
    Args:
        config_path: Path to config.json
    
    Returns:
        Monitored LLM client
    """
    from core.llm_client import LLMClient
    
    original_client = LLMClient(config_path)
    
    # Wrap generate method
    original_generate = original_client.generate
    
    @monitored("llm_query")
    def monitored_generate(*args, **kwargs):
        return original_generate(*args, **kwargs)
    
    original_client.generate = monitored_generate
    
    return original_client


def create_monitored_web_search():
    """Create web search function with automatic monitoring.
    
    Returns:
        Monitored web search function
    """
    from tools.web_search import web_search as original_search
    
    @monitored("web_search")
    def monitored_search(*args, **kwargs):
        return original_search(*args, **kwargs)
    
    return monitored_search


def create_monitored_rag(persist_dir: str):
    """Create RAG instance with automatic monitoring.
    
    Args:
        persist_dir: Path to embeddings directory
    
    Returns:
        Monitored RAG instance
    """
    from tools.rag import RAG
    
    rag = RAG(persist_dir=persist_dir)
    
    # Wrap query method
    original_query = rag.query
    
    @monitored("rag_query")
    def monitored_query(*args, **kwargs):
        return original_query(*args, **kwargs)
    
    rag.query = monitored_query
    
    return rag


def print_health_summary(console=None):
    """Print a quick health summary to console.
    
    Args:
        console: Rich Console instance, or None to create one
    """
    from rich.console import Console
    from rich.table import Table
    from rich import box
    
    if console is None:
        console = Console()
    
    tracker = get_performance_tracker()
    monitor = get_system_monitor()
    alerts = get_alert_system()
    
    # System metrics
    metrics = monitor.get_latest_metrics()
    if metrics:
        console.print("\n[bold cyan]📊 System Metrics[/bold cyan]")
        console.print(f"  CPU: {metrics.cpu_percent:.1f}%")
        console.print(f"  Memory: {metrics.memory_percent:.1f}%")
        console.print(f"  Disk: {metrics.disk_percent:.1f}%")
    
    # Performance stats
    stats = tracker.get_all_stats()
    if stats:
        console.print("\n[bold cyan]📈 Performance[/bold cyan]")
        
        table = Table(show_header=True, box=box.SIMPLE)
        table.add_column("Operation", style="cyan")
        table.add_column("Avg", justify="right")
        table.add_column("P95", justify="right")
        table.add_column("Count", justify="right")
        
        for op_name, op_stats in list(stats.items())[:5]:
            table.add_row(
                op_name,
                f"{op_stats.avg_duration_ms:.0f}ms",
                f"{op_stats.p95_duration_ms:.0f}ms",
                str(op_stats.count)
            )
        
        console.print(table)
    
    # Alerts
    active_alerts = alerts.get_alerts(unacknowledged_only=True)
    if active_alerts:
        console.print(f"\n[bold red]🚨 Active Alerts: {len(active_alerts)}[/bold red]")
        for alert in active_alerts[:3]:
            console.print(f"  [{alert.level.value}] {alert.message}")
    else:
        console.print("\n[green]✓ No active alerts[/green]")


def shutdown_monitoring():
    """Shutdown all monitoring components gracefully."""
    global _system_monitor
    
    if _system_monitor is not None:
        _system_monitor.stop()
        _system_monitor = None


# Convenience exports
__all__ = [
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
