"""Resource monitoring utilities for memory and performance tracking."""
import logging
import psutil
import time
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
import threading
from functools import wraps

logger = logging.getLogger("crawllama")


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""
    rss_mb: float  # Resident Set Size in MB
    vms_mb: float  # Virtual Memory Size in MB
    percent: float  # Memory usage percentage
    available_mb: float  # Available system memory
    timestamp: float


class RAMMonitor:
    """Monitor RAM usage for the application."""

    def __init__(self, warning_threshold: float = 80.0, critical_threshold: float = 90.0):
        """
        Initialize RAM monitor.

        Args:
            warning_threshold: Warn when memory usage exceeds this % of available
            critical_threshold: Critical when usage exceeds this %
        """
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self._process = psutil.Process()
        self._snapshots = []
        self._max_snapshots = 100

        logger.info(f"RAM monitor initialized (warn={warning_threshold}%, critical={critical_threshold}%)")

    def get_current_usage(self) -> MemorySnapshot:
        """
        Get current memory usage.

        Returns:
            MemorySnapshot with current usage
        """
        mem_info = self._process.memory_info()
        sys_mem = psutil.virtual_memory()

        snapshot = MemorySnapshot(
            rss_mb=mem_info.rss / 1024 / 1024,
            vms_mb=mem_info.vms / 1024 / 1024,
            percent=self._process.memory_percent(),
            available_mb=sys_mem.available / 1024 / 1024,
            timestamp=time.time()
        )

        # Store snapshot
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots.pop(0)

        return snapshot

    def check_thresholds(self) -> Optional[str]:
        """
        Check if memory usage exceeds thresholds.

        Returns:
            Warning level: None, "warning", or "critical"
        """
        usage = self.get_current_usage()

        if usage.percent >= self.critical_threshold:
            logger.critical(f"CRITICAL: Memory usage at {usage.percent:.1f}% ({usage.rss_mb:.1f} MB)")
            return "critical"

        elif usage.percent >= self.warning_threshold:
            logger.warning(f"WARNING: Memory usage at {usage.percent:.1f}% ({usage.rss_mb:.1f} MB)")
            return "warning"

        return None

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get memory usage statistics.

        Returns:
            Dictionary with memory stats
        """
        if not self._snapshots:
            return {}

        current = self.get_current_usage()

        # Calculate statistics from snapshots
        rss_values = [s.rss_mb for s in self._snapshots]
        percent_values = [s.percent for s in self._snapshots]

        return {
            "current_rss_mb": current.rss_mb,
            "current_vms_mb": current.vms_mb,
            "current_percent": current.percent,
            "available_mb": current.available_mb,
            "peak_rss_mb": max(rss_values),
            "avg_rss_mb": sum(rss_values) / len(rss_values),
            "peak_percent": max(percent_values),
            "avg_percent": sum(percent_values) / len(percent_values),
            "snapshots_count": len(self._snapshots)
        }

    def log_usage(self):
        """Log current memory usage."""
        usage = self.get_current_usage()
        logger.info(f"Memory: {usage.rss_mb:.1f} MB ({usage.percent:.1f}%), Available: {usage.available_mb:.1f} MB")

    def should_trigger_gc(self) -> bool:
        """
        Check if garbage collection should be triggered.

        Returns:
            True if GC recommended
        """
        usage = self.get_current_usage()
        return usage.percent >= self.warning_threshold

    def clear_snapshots(self):
        """Clear stored snapshots."""
        self._snapshots.clear()
        logger.info("Cleared memory snapshots")


class PerformanceMonitor:
    """Monitor performance metrics like execution time."""

    def __init__(self):
        """Initialize performance monitor."""
        self._timings: Dict[str, list] = {}
        self._lock = threading.Lock()

    def record_timing(self, operation: str, duration: float):
        """
        Record timing for an operation.

        Args:
            operation: Operation name
            duration: Duration in seconds
        """
        with self._lock:
            if operation not in self._timings:
                self._timings[operation] = []

            self._timings[operation].append(duration)

            # Keep only last 100 timings per operation
            if len(self._timings[operation]) > 100:
                self._timings[operation].pop(0)

    def get_stats(self, operation: str) -> Dict[str, float]:
        """
        Get statistics for an operation.

        Args:
            operation: Operation name

        Returns:
            Dictionary with timing stats
        """
        with self._lock:
            if operation not in self._timings or not self._timings[operation]:
                return {}

            timings = self._timings[operation]

            return {
                "count": len(timings),
                "total": sum(timings),
                "avg": sum(timings) / len(timings),
                "min": min(timings),
                "max": max(timings),
                "last": timings[-1]
            }

    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get stats for all operations."""
        return {
            operation: self.get_stats(operation)
            for operation in self._timings.keys()
        }

    def clear_stats(self, operation: Optional[str] = None):
        """
        Clear timing statistics.

        Args:
            operation: Specific operation to clear, or None for all
        """
        with self._lock:
            if operation:
                self._timings.pop(operation, None)
            else:
                self._timings.clear()


def monitor_memory(func: Callable) -> Callable:
    """
    Decorator to monitor memory usage of a function.

    Args:
        func: Function to monitor

    Returns:
        Wrapped function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        monitor = RAMMonitor()

        # Before
        before = monitor.get_current_usage()
        logger.debug(f"Before {func.__name__}: {before.rss_mb:.1f} MB")

        try:
            result = func(*args, **kwargs)
            return result

        finally:
            # After
            after = monitor.get_current_usage()
            delta = after.rss_mb - before.rss_mb

            logger.info(
                f"Memory delta for {func.__name__}: {delta:+.1f} MB "
                f"({before.rss_mb:.1f} -> {after.rss_mb:.1f} MB)"
            )

    return wrapper


def monitor_time(operation_name: Optional[str] = None):
    """
    Decorator to monitor execution time.

    Args:
        operation_name: Optional custom name for the operation

    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = operation_name or func.__name__
            start = time.time()

            try:
                result = func(*args, **kwargs)
                return result

            finally:
                elapsed = time.time() - start
                logger.info(f"{name} completed in {elapsed:.2f}s")

                # Record in global performance monitor if available
                if hasattr(wrapper, '_perf_monitor'):
                    wrapper._perf_monitor.record_timing(name, elapsed)

        return wrapper

    return decorator


class ResourceManager:
    """Comprehensive resource management with monitoring."""

    def __init__(
        self,
        enable_monitoring: bool = True,
        auto_gc_threshold: float = 80.0
    ):
        """
        Initialize resource manager.

        Args:
            enable_monitoring: Enable automatic monitoring
            auto_gc_threshold: Trigger GC when memory exceeds this %
        """
        self.enable_monitoring = enable_monitoring
        self.auto_gc_threshold = auto_gc_threshold

        self.ram_monitor = RAMMonitor(warning_threshold=auto_gc_threshold)
        self.perf_monitor = PerformanceMonitor()

        if enable_monitoring:
            self._start_monitoring_thread()

        logger.info("Resource manager initialized")

    def _start_monitoring_thread(self):
        """Start background monitoring thread."""
        def monitor_loop():
            while self.enable_monitoring:
                try:
                    # Check memory
                    level = self.ram_monitor.check_thresholds()

                    if level == "critical":
                        # Trigger garbage collection
                        import gc
                        logger.warning("Triggering garbage collection due to high memory usage")
                        gc.collect()

                    time.sleep(60)  # Check every minute

                except Exception as e:
                    logger.error(f"Monitoring error: {e}")

        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()

    def get_report(self) -> Dict[str, Any]:
        """
        Get comprehensive resource report.

        Returns:
            Dictionary with all resource stats
        """
        return {
            "memory": self.ram_monitor.get_statistics(),
            "performance": self.perf_monitor.get_all_stats(),
            "timestamp": time.time()
        }

    def log_report(self):
        """Log resource report."""
        report = self.get_report()

        logger.info("=== Resource Report ===")
        logger.info(f"Memory: {report['memory'].get('current_rss_mb', 0):.1f} MB "
                   f"({report['memory'].get('current_percent', 0):.1f}%)")

        if report['performance']:
            logger.info("Performance timings:")
            for op, stats in report['performance'].items():
                logger.info(f"  {op}: avg={stats.get('avg', 0):.2f}s, "
                           f"count={stats.get('count', 0)}")


# Global instance
_resource_manager = None


def get_resource_manager() -> ResourceManager:
    """Get global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager
