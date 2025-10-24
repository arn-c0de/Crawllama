"""DEPRECATED: Resource monitoring utilities - Use core.health instead.

⚠️  DEPRECATION WARNING ⚠️
This module is deprecated and will be removed in a future version.

Migration Guide:
    OLD: from utils.resource_monitor import RAMMonitor
    NEW: from core.health import SystemMonitor

    OLD: from utils.resource_monitor import PerformanceMonitor
    NEW: from core.health import PerformanceTracker

    OLD: from utils.resource_monitor import ResourceManager, get_resource_manager
    NEW: from core.health import get_system_monitor, get_performance_tracker

    OLD: from utils.resource_monitor import monitor_memory
    NEW: from core.health import monitored

See docs/HEALTH_IMPLEMENTATION_SUMMARY.md for full migration guide.
"""
import warnings
import logging

logger = logging.getLogger("crawllama")

_DEPRECATION_MSG = """
⚠️  utils.resource_monitor is DEPRECATED!

This module has been replaced by the comprehensive health monitoring system in core.health.

Migration:
  - RAMMonitor → SystemMonitor (from core.health)
  - PerformanceMonitor → PerformanceTracker (from core.health)
  - ResourceManager → get_system_monitor() + get_performance_tracker()
  - monitor_memory → @monitored decorator

For details see: docs/HEALTH_IMPLEMENTATION_SUMMARY.md
"""


def _show_deprecation_warning(old_name: str, new_name: str):
    """Show deprecation warning for old API."""
    msg = f"{old_name} is deprecated. Use {new_name} from core.health instead."
    warnings.warn(msg, DeprecationWarning, stacklevel=3)
    logger.warning(msg)


# Backwards compatibility wrappers
class RAMMonitor:
    """DEPRECATED: Use SystemMonitor from core.health instead."""

    def __init__(self, warning_threshold: float = 80.0, critical_threshold: float = 90.0):
        _show_deprecation_warning("RAMMonitor", "SystemMonitor")
        from core.health import SystemMonitor
        self._monitor = SystemMonitor(update_interval=1.0)
        self._monitor.start()
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def get_current_usage(self):
        """Get current memory usage (compatibility wrapper)."""
        metrics = self._monitor.get_latest_metrics()
        if metrics:
            # Return a simple object with old interface
            class MemorySnapshot:
                def __init__(self, m):
                    self.rss_mb = m.memory_used_gb * 1024
                    self.vms_mb = m.memory_used_gb * 1024  # Approximation
                    self.percent = m.memory_percent
                    self.available_mb = (m.memory_total_gb - m.memory_used_gb) * 1024
                    self.timestamp = m.timestamp.timestamp()
            return MemorySnapshot(metrics)
        return None

    def check_thresholds(self):
        """Check memory thresholds."""
        usage = self.get_current_usage()
        if usage and usage.percent >= self.critical_threshold:
            return "critical"
        elif usage and usage.percent >= self.warning_threshold:
            return "warning"
        return None

    def get_statistics(self):
        """Get memory statistics."""
        usage = self.get_current_usage()
        if usage:
            return {
                "current_rss_mb": usage.rss_mb,
                "current_vms_mb": usage.vms_mb,
                "current_percent": usage.percent,
                "available_mb": usage.available_mb,
            }
        return {}

    def log_usage(self):
        """Log current usage."""
        usage = self.get_current_usage()
        if usage:
            logger.info(f"Memory: {usage.rss_mb:.1f} MB ({usage.percent:.1f}%)")


class PerformanceMonitor:
    """DEPRECATED: Use PerformanceTracker from core.health instead."""

    def __init__(self):
        _show_deprecation_warning("PerformanceMonitor", "PerformanceTracker")
        from core.health import PerformanceTracker
        self._tracker = PerformanceTracker()

    def record_timing(self, operation: str, duration: float):
        """Record timing (duration in seconds)."""
        # Convert seconds to milliseconds for new API
        self._tracker.record(operation, duration * 1000, success=True)

    def get_stats(self, operation: str):
        """Get statistics for operation."""
        stats = self._tracker.get_stats(operation)
        if stats:
            return {
                "count": stats.count,
                "total": stats.count * stats.avg_duration_ms / 1000,  # seconds
                "avg": stats.avg_duration_ms / 1000,  # seconds
                "min": stats.min_duration_ms / 1000,  # seconds
                "max": stats.max_duration_ms / 1000,  # seconds
                "last": stats.avg_duration_ms / 1000,  # approximation
            }
        return {}

    def get_all_stats(self):
        """Get all statistics."""
        all_stats = self._tracker.get_all_stats()
        return {op: self.get_stats(op) for op in all_stats.keys()}


class ResourceManager:
    """DEPRECATED: Use get_system_monitor() and get_performance_tracker() instead."""

    def __init__(self, enable_monitoring: bool = True, auto_gc_threshold: float = 80.0):
        _show_deprecation_warning("ResourceManager", "get_system_monitor() + get_performance_tracker()")
        from core.health import get_system_monitor, get_performance_tracker
        self.ram_monitor = RAMMonitor(warning_threshold=auto_gc_threshold)
        self.perf_monitor = PerformanceMonitor()
        self._system_monitor = get_system_monitor()
        self._perf_tracker = get_performance_tracker()

    def get_report(self):
        """Get resource report."""
        report = {
            "memory": self.ram_monitor.get_statistics(),
            "performance": self._perf_tracker.get_all_stats(),
        }
        return report

    def log_report(self):
        """Log resource report."""
        from core.health import print_health_summary
        logger.info("=== Resource Report (via deprecated API) ===")
        print_health_summary()


def monitor_memory(func):
    """DEPRECATED: Use @monitored decorator from core.health instead."""
    _show_deprecation_warning("@monitor_memory", "@monitored")
    from core.health import monitored
    return monitored(func.__name__)(func)


def monitor_time(operation_name: str = None):
    """DEPRECATED: Use @monitored decorator from core.health instead."""
    _show_deprecation_warning("@monitor_time", "@monitored")
    from core.health import monitored
    return monitored(operation_name)


def get_resource_manager():
    """DEPRECATED: Use get_system_monitor() and get_performance_tracker() instead."""
    _show_deprecation_warning("get_resource_manager()", "get_system_monitor() + get_performance_tracker()")
    return ResourceManager()


# Show deprecation message on import
warnings.warn(_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
logger.warning("⚠️  utils.resource_monitor is deprecated. Migrate to core.health!")
