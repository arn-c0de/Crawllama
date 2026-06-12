"""Performance Tracker - Monitor response times and throughput.

This module tracks:
- Response times for LLM queries
- Search operation durations
- Cache hit rates
- Request throughput
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque
import threading
import statistics


@dataclass
class PerformanceMetric:
    """Individual performance measurement."""
    operation: str
    duration_ms: float
    timestamp: datetime
    success: bool
    details: Optional[Dict] = None


@dataclass
class PerformanceStats:
    """Aggregated performance statistics."""
    operation: str
    count: int
    avg_duration_ms: float
    min_duration_ms: float
    max_duration_ms: float
    p50_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    success_rate: float
    throughput_per_min: float
    last_updated: datetime


class PerformanceTracker:
    """Track and analyze performance metrics."""

    def __init__(self, max_history: int = 1000, window_minutes: int = 60):
        """Initialize performance tracker.
        
        Args:
            max_history: Maximum number of metrics to keep per operation
            window_minutes: Time window for throughput calculation
        """
        self.max_history = max_history
        self.window_minutes = window_minutes
        
        # Store metrics per operation type
        self._metrics: Dict[str, deque] = {}
        self._lock = threading.Lock()
        
        # Cache stats to avoid recalculation
        self._cached_stats: Dict[str, PerformanceStats] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(seconds=5)

    def record(self, operation: str, duration_ms: float, success: bool = True,
               details: Optional[Dict] = None):
        """Record a performance metric.
        
        Args:
            operation: Operation type (e.g., 'llm_query', 'web_search')
            duration_ms: Duration in milliseconds
            success: Whether operation succeeded
            details: Optional additional details
        """
        metric = PerformanceMetric(
            operation=operation,
            duration_ms=duration_ms,
            timestamp=datetime.now(),
            success=success,
            details=details
        )
        
        with self._lock:
            if operation not in self._metrics:
                self._metrics[operation] = deque(maxlen=self.max_history)
            
            self._metrics[operation].append(metric)
            
            # Invalidate cache for this operation
            if operation in self._cached_stats:
                del self._cached_stats[operation]

    def get_stats(self, operation: str) -> Optional[PerformanceStats]:
        """Get performance statistics for an operation.
        
        Args:
            operation: Operation type to get stats for
            
        Returns:
            PerformanceStats object or None if no data
        """
        # Check cache
        if operation in self._cached_stats:
            cache_age = datetime.now() - self._cache_time[operation]
            if cache_age < self._cache_ttl:
                return self._cached_stats[operation]
        
        with self._lock:
            if operation not in self._metrics or len(self._metrics[operation]) == 0:
                return None
            
            metrics = list(self._metrics[operation])
        
        # Calculate stats
        stats = self._calculate_stats(operation, metrics)
        
        # Cache result
        self._cached_stats[operation] = stats
        self._cache_time[operation] = datetime.now()
        
        return stats

    def get_all_stats(self) -> Dict[str, PerformanceStats]:
        """Get statistics for all operations.
        
        Returns:
            Dictionary mapping operation name to stats
        """
        result = {}
        
        with self._lock:
            operations = list(self._metrics.keys())
        
        for operation in operations:
            stats = self.get_stats(operation)
            if stats:
                result[operation] = stats
        
        return result

    def _calculate_stats(self, operation: str, 
                        metrics: List[PerformanceMetric]) -> PerformanceStats:
        """Calculate statistics from metrics.
        
        Args:
            operation: Operation name
            metrics: List of metrics to analyze
            
        Returns:
            PerformanceStats object
        """
        if not metrics:
            return PerformanceStats(
                operation=operation,
                count=0,
                avg_duration_ms=0.0,
                min_duration_ms=0.0,
                max_duration_ms=0.0,
                p50_duration_ms=0.0,
                p95_duration_ms=0.0,
                p99_duration_ms=0.0,
                success_rate=0.0,
                throughput_per_min=0.0,
                last_updated=datetime.now()
            )
        
        # Extract durations
        durations = [m.duration_ms for m in metrics]
        successes = [m for m in metrics if m.success]
        
        # Calculate percentiles
        sorted_durations = sorted(durations)
        count = len(sorted_durations)
        
        p50_idx = int(count * 0.50)
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)
        
        # Calculate throughput (operations in last N minutes)
        cutoff_time = datetime.now() - timedelta(minutes=self.window_minutes)
        recent_metrics = [m for m in metrics if m.timestamp >= cutoff_time]
        
        if recent_metrics:
            time_span = (datetime.now() - recent_metrics[0].timestamp).total_seconds() / 60.0
            throughput = len(recent_metrics) / time_span if time_span > 0 else 0.0
        else:
            throughput = 0.0
        
        return PerformanceStats(
            operation=operation,
            count=count,
            avg_duration_ms=statistics.mean(durations),
            min_duration_ms=min(durations),
            max_duration_ms=max(durations),
            p50_duration_ms=sorted_durations[p50_idx] if count > 0 else 0.0,
            p95_duration_ms=sorted_durations[p95_idx] if count > 0 else 0.0,
            p99_duration_ms=sorted_durations[p99_idx] if count > 0 else 0.0,
            success_rate=len(successes) / count * 100 if count > 0 else 0.0,
            throughput_per_min=throughput,
            last_updated=datetime.now()
        )

    def clear(self, operation: Optional[str] = None):
        """Clear metrics.
        
        Args:
            operation: Specific operation to clear, or None to clear all
        """
        with self._lock:
            if operation:
                if operation in self._metrics:
                    self._metrics[operation].clear()
                if operation in self._cached_stats:
                    del self._cached_stats[operation]
            else:
                self._metrics.clear()
                self._cached_stats.clear()

    def get_recent_metrics(self, operation: str, 
                          limit: int = 10) -> List[PerformanceMetric]:
        """Get recent metrics for an operation.
        
        Args:
            operation: Operation type
            limit: Maximum number of metrics to return
            
        Returns:
            List of recent metrics (newest first)
        """
        with self._lock:
            if operation not in self._metrics:
                return []
            
            metrics = list(self._metrics[operation])
        
        # Return most recent metrics
        return metrics[-limit:][::-1]

    def get_operation_types(self) -> List[str]:
        """Get list of all tracked operation types.
        
        Returns:
            List of operation type names
        """
        with self._lock:
            return list(self._metrics.keys())


class PerformanceTimer:
    """Context manager for timing operations."""

    def __init__(self, tracker: PerformanceTracker, operation: str,
                 details: Optional[Dict] = None):
        """Initialize timer.
        
        Args:
            tracker: PerformanceTracker instance
            operation: Operation name
            details: Optional details to record
        """
        self.tracker = tracker
        self.operation = operation
        self.details = details
        self.start_time = None
        self.success = True

    def __enter__(self):
        """Start timing."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and record."""
        duration_ms = (time.time() - self.start_time) * 1000
        
        # Mark as failed if exception occurred
        if exc_type is not None:
            self.success = False
        
        self.tracker.record(
            operation=self.operation,
            duration_ms=duration_ms,
            success=self.success,
            details=self.details
        )
        
        return False  # Don't suppress exceptions

    def mark_failure(self):
        """Mark operation as failed."""
        self.success = False
