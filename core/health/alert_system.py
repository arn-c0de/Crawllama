"""Alert System - Monitor and notify about system issues.

This module provides:
- Rule-based alerting
- Alert history and management
- Notification callbacks
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """System alert."""
    id: str
    level: AlertLevel
    component: str
    message: str
    timestamp: datetime
    acknowledged: bool = False
    resolved: bool = False
    details: dict | None = None


class AlertRule:
    """Base class for alert rules."""

    def __init__(self, name: str, level: AlertLevel, cooldown_minutes: int = 5):
        """Initialize alert rule.
        
        Args:
            name: Rule name
            level: Alert level to generate
            cooldown_minutes: Minutes to wait before re-alerting
        """
        self.name = name
        self.level = level
        self.cooldown = timedelta(minutes=cooldown_minutes)
        self.last_alert_time: datetime | None = None

    def check(self, data: dict) -> str | None:
        """Check if alert should be triggered.
        
        Args:
            data: Current system data
            
        Returns:
            Alert message if triggered, None otherwise
        """
        raise NotImplementedError

    def can_alert(self) -> bool:
        """Check if cooldown period has passed."""
        if self.last_alert_time is None:
            return True
        
        return datetime.now() - self.last_alert_time >= self.cooldown


class CPUAlertRule(AlertRule):
    """Alert on high CPU usage."""

    def __init__(self, threshold: float = 90.0, level: AlertLevel = AlertLevel.WARNING):
        super().__init__("High CPU Usage", level)
        self.threshold = threshold

    def check(self, data: dict) -> str | None:
        """Check CPU usage."""
        if 'system_metrics' not in data:
            return None
        
        metrics = data['system_metrics']
        if not metrics:
            return None
        
        cpu_percent = metrics.cpu_percent
        
        if cpu_percent >= self.threshold and self.can_alert():
            self.last_alert_time = datetime.now()
            return f"CPU usage at {cpu_percent:.1f}% (threshold: {self.threshold:.1f}%)"
        
        return None


class MemoryAlertRule(AlertRule):
    """Alert on high memory usage."""

    def __init__(self, threshold: float = 90.0, level: AlertLevel = AlertLevel.WARNING):
        super().__init__("High Memory Usage", level)
        self.threshold = threshold

    def check(self, data: dict) -> str | None:
        """Check memory usage."""
        if 'system_metrics' not in data:
            return None
        
        metrics = data['system_metrics']
        if not metrics:
            return None
        
        mem_percent = metrics.memory_percent
        
        if mem_percent >= self.threshold and self.can_alert():
            self.last_alert_time = datetime.now()
            return f"Memory usage at {mem_percent:.1f}% (threshold: {self.threshold:.1f}%)"
        
        return None


class DiskSpaceAlertRule(AlertRule):
    """Alert on low disk space."""

    def __init__(self, threshold_gb: float = 5.0, level: AlertLevel = AlertLevel.WARNING):
        super().__init__("Low Disk Space", level)
        self.threshold_gb = threshold_gb

    def check(self, data: dict) -> str | None:
        """Check disk space."""
        if 'system_metrics' not in data:
            return None
        
        metrics = data['system_metrics']
        if not metrics:
            return None
        
        disk_free_gb = metrics.disk_total_gb - metrics.disk_used_gb
        
        if disk_free_gb <= self.threshold_gb and self.can_alert():
            self.last_alert_time = datetime.now()
            return f"Low disk space: {disk_free_gb:.2f} GB free (threshold: {self.threshold_gb:.2f} GB)"
        
        return None


class ComponentHealthAlertRule(AlertRule):
    """Alert on unhealthy components."""

    def __init__(self, level: AlertLevel = AlertLevel.ERROR):
        super().__init__("Component Unhealthy", level)

    def check(self, data: dict) -> str | None:
        """Check component health."""
        if 'component_health' not in data:
            return None
        
        health = data['component_health']
        if not health:
            return None
        
        from .component_checker import HealthStatus
        
        unhealthy = []
        for name, status in health.items():
            if status.status == HealthStatus.UNHEALTHY:
                unhealthy.append(name)
        
        if unhealthy and self.can_alert():
            self.last_alert_time = datetime.now()
            return f"Unhealthy components: {', '.join(unhealthy)}"
        
        return None


class PerformanceAlertRule(AlertRule):
    """Alert on poor performance."""

    def __init__(self, threshold_ms: float = 5000.0, 
                 level: AlertLevel = AlertLevel.WARNING):
        super().__init__("Slow Performance", level)
        self.threshold_ms = threshold_ms

    def check(self, data: dict) -> str | None:
        """Check performance metrics."""
        if 'performance_stats' not in data:
            return None
        
        stats = data['performance_stats']
        if not stats:
            return None
        
        slow_operations = []
        for op_name, op_stats in stats.items():
            if op_stats.p95_duration_ms >= self.threshold_ms:
                slow_operations.append(f"{op_name} (P95: {op_stats.p95_duration_ms:.0f}ms)")
        
        if slow_operations and self.can_alert():
            self.last_alert_time = datetime.now()
            return f"Slow operations detected: {', '.join(slow_operations)}"
        
        return None


class AlertSystem:
    """Manage alerts and notifications."""

    def __init__(self):
        """Initialize alert system."""
        self.alerts: list[Alert] = []
        self.rules: list[AlertRule] = []
        self.callbacks: list[Callable[[Alert], None]] = []
        self._lock = threading.Lock()
        self._alert_counter = 0
        
        # Register default rules
        self._register_default_rules()

    def _register_default_rules(self):
        """Register default alert rules."""
        self.rules = [
            CPUAlertRule(threshold=85.0, level=AlertLevel.WARNING),
            CPUAlertRule(threshold=95.0, level=AlertLevel.ERROR),
            MemoryAlertRule(threshold=85.0, level=AlertLevel.WARNING),
            MemoryAlertRule(threshold=95.0, level=AlertLevel.ERROR),
            DiskSpaceAlertRule(threshold_gb=5.0, level=AlertLevel.WARNING),
            DiskSpaceAlertRule(threshold_gb=1.0, level=AlertLevel.CRITICAL),
            ComponentHealthAlertRule(level=AlertLevel.ERROR),
            PerformanceAlertRule(threshold_ms=5000.0, level=AlertLevel.WARNING),
        ]

    def add_rule(self, rule: AlertRule):
        """Add a custom alert rule.
        
        Args:
            rule: AlertRule instance
        """
        with self._lock:
            self.rules.append(rule)

    def register_callback(self, callback: Callable[[Alert], None]):
        """Register a callback for new alerts.
        
        Args:
            callback: Function to call when alert is created
        """
        with self._lock:
            self.callbacks.append(callback)

    def check_alerts(self, data: dict):
        """Check all rules and create alerts if needed.
        
        Args:
            data: Current system data to check
        """
        for rule in self.rules:
            try:
                message = rule.check(data)
                if message:
                    self._create_alert(
                        level=rule.level,
                        component=rule.name,
                        message=message
                    )
            except Exception as e:
                print(f"[AlertSystem] Error checking rule {rule.name}: {e}")

    def _create_alert(self, level: AlertLevel, component: str, message: str,
                     details: dict | None = None):
        """Create a new alert.
        
        Args:
            level: Alert level
            component: Component name
            message: Alert message
            details: Optional details
        """
        with self._lock:
            self._alert_counter += 1
            alert_id = f"alert_{self._alert_counter}_{int(datetime.now().timestamp())}"
            
            alert = Alert(
                id=alert_id,
                level=level,
                component=component,
                message=message,
                timestamp=datetime.now(),
                details=details
            )
            
            self.alerts.append(alert)
            
            # Keep only recent alerts (last 100)
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-100:]
        
        # Notify callbacks
        for callback in self.callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"[AlertSystem] Error in callback: {e}")

    def get_alerts(self, unacknowledged_only: bool = False,
                  level: AlertLevel | None = None) -> list[Alert]:
        """Get alerts with optional filtering.
        
        Args:
            unacknowledged_only: Only return unacknowledged alerts
            level: Filter by alert level
            
        Returns:
            List of alerts
        """
        with self._lock:
            alerts = list(self.alerts)
        
        if unacknowledged_only:
            alerts = [a for a in alerts if not a.acknowledged]
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        return alerts

    def acknowledge_alert(self, alert_id: str):
        """Mark alert as acknowledged.
        
        Args:
            alert_id: ID of alert to acknowledge
        """
        with self._lock:
            for alert in self.alerts:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    break

    def resolve_alert(self, alert_id: str):
        """Mark alert as resolved.
        
        Args:
            alert_id: ID of alert to resolve
        """
        with self._lock:
            for alert in self.alerts:
                if alert.id == alert_id:
                    alert.resolved = True
                    alert.acknowledged = True
                    break

    def clear_alerts(self, acknowledged_only: bool = True):
        """Clear alerts.
        
        Args:
            acknowledged_only: Only clear acknowledged alerts
        """
        with self._lock:
            if acknowledged_only:
                self.alerts = [a for a in self.alerts if not a.acknowledged]
            else:
                self.alerts.clear()

    def get_alert_summary(self) -> dict[str, int]:
        """Get summary of alert counts by level.
        
        Returns:
            Dictionary mapping level to count
        """
        with self._lock:
            summary = {level.value: 0 for level in AlertLevel}
            
            for alert in self.alerts:
                if not alert.acknowledged:
                    summary[alert.level.value] += 1
        
        return summary
