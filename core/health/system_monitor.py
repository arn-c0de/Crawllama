"""System Monitoring Module - Live system metrics collection.

This module provides real-time monitoring of system resources:
- CPU usage per core
- Memory (RAM) usage
- Disk I/O and space
- Network traffic
"""

import psutil
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import threading


@dataclass
class SystemMetrics:
    """Container for system metrics snapshot."""
    timestamp: datetime
    cpu_percent: float
    cpu_per_core: List[float]
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_read_mb: float
    disk_write_mb: float
    network_sent_mb: float
    network_recv_mb: float


class SystemMonitor:
    """Monitor system resources in real-time."""

    def __init__(self, update_interval: float = 1.0):
        """Initialize system monitor.
        
        Args:
            update_interval: Seconds between metric updates
        """
        self.update_interval = update_interval
        self.is_running = False
        self.latest_metrics: Optional[SystemMetrics] = None
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # For network/disk delta calculations
        self._last_disk_io: Optional[psutil._common.sdiskio] = None
        self._last_net_io: Optional[psutil._common.snetio] = None
        self._last_time: Optional[float] = None

    def start(self):
        """Start monitoring in background thread."""
        if self.is_running:
            return
        
        self.is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop monitoring."""
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def get_latest_metrics(self) -> Optional[SystemMetrics]:
        """Get the most recent metrics snapshot.
        
        Returns:
            SystemMetrics object or None if not yet collected
        """
        with self._lock:
            return self.latest_metrics

    def _monitor_loop(self):
        """Main monitoring loop (runs in background thread)."""
        while self.is_running:
            try:
                metrics = self._collect_metrics()
                with self._lock:
                    self.latest_metrics = metrics
            except Exception as e:
                print(f"[SystemMonitor] Error collecting metrics: {e}")
            
            time.sleep(self.update_interval)

    def _collect_metrics(self) -> SystemMetrics:
        """Collect current system metrics."""
        current_time = time.time()
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        
        # Memory
        mem = psutil.virtual_memory()
        memory_percent = mem.percent
        memory_used_gb = mem.used / (1024 ** 3)
        memory_total_gb = mem.total / (1024 ** 3)
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_used_gb = disk.used / (1024 ** 3)
        disk_total_gb = disk.total / (1024 ** 3)
        
        # Disk I/O (calculate rate)
        disk_io = psutil.disk_io_counters()
        if self._last_disk_io and self._last_time:
            time_delta = current_time - self._last_time
            read_rate = (disk_io.read_bytes - self._last_disk_io.read_bytes) / time_delta
            write_rate = (disk_io.write_bytes - self._last_disk_io.write_bytes) / time_delta
            disk_read_mb = read_rate / (1024 ** 2)
            disk_write_mb = write_rate / (1024 ** 2)
        else:
            disk_read_mb = 0.0
            disk_write_mb = 0.0
        
        self._last_disk_io = disk_io
        
        # Network I/O (calculate rate)
        net_io = psutil.net_io_counters()
        if self._last_net_io and self._last_time:
            time_delta = current_time - self._last_time
            sent_rate = (net_io.bytes_sent - self._last_net_io.bytes_sent) / time_delta
            recv_rate = (net_io.bytes_recv - self._last_net_io.bytes_recv) / time_delta
            network_sent_mb = sent_rate / (1024 ** 2)
            network_recv_mb = recv_rate / (1024 ** 2)
        else:
            network_sent_mb = 0.0
            network_recv_mb = 0.0
        
        self._last_net_io = net_io
        self._last_time = current_time
        
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            cpu_per_core=cpu_per_core,
            memory_percent=memory_percent,
            memory_used_gb=memory_used_gb,
            memory_total_gb=memory_total_gb,
            disk_percent=disk_percent,
            disk_used_gb=disk_used_gb,
            disk_total_gb=disk_total_gb,
            disk_read_mb=disk_read_mb,
            disk_write_mb=disk_write_mb,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb
        )

    @staticmethod
    def get_cpu_count() -> Tuple[int, int]:
        """Get CPU counts.
        
        Returns:
            Tuple of (physical_cores, logical_cores)
        """
        return (psutil.cpu_count(logical=False) or 0, 
                psutil.cpu_count(logical=True) or 0)

    @staticmethod
    def get_system_info() -> Dict[str, str]:
        """Get static system information.
        
        Returns:
            Dictionary with system info
        """
        import platform
        
        phys_cores, log_cores = SystemMonitor.get_cpu_count()
        mem = psutil.virtual_memory()
        
        return {
            'platform': platform.system(),
            'platform_release': platform.release(),
            'platform_version': platform.version(),
            'architecture': platform.machine(),
            'processor': platform.processor(),
            'physical_cores': str(phys_cores),
            'logical_cores': str(log_cores),
            'total_memory': f"{mem.total / (1024**3):.2f} GB",
            'python_version': platform.python_version()
        }
