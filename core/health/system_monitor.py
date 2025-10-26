"""System Monitoring Module - Live system metrics collection.

This module provides real-time monitoring of system resources:
- CPU usage per core
- Memory (RAM) usage
- Disk I/O and space
- Network traffic
- GPU usage and memory (NVIDIA/AMD)
- Memory Store usage and statistics
"""

import psutil
import time
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import threading
import subprocess  # nosec B404 - subprocess needed for nvidia-smi GPU monitoring


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
    # GPU metrics
    gpu_available: bool
    gpu_count: int
    gpu_utilization: List[float]  # Utilization % per GPU
    gpu_memory_used: List[float]  # Used memory in GB per GPU
    gpu_memory_total: List[float]  # Total memory in GB per GPU
    gpu_temperature: List[float]  # Temperature in °C per GPU
    gpu_names: List[str]  # GPU names
    # Memory Store metrics
    memory_store_entries: int
    memory_store_size_kb: float
    memory_store_emails: int
    memory_store_phones: int
    memory_store_ips: int
    memory_store_usernames: int
    memory_store_domains: int
    memory_store_notes: int


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

        # GPU monitoring availability check
        self._gpu_available = self._check_gpu_availability()

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

        # GPU metrics
        gpu_metrics = self._get_gpu_metrics()
        
        # Memory Store metrics
        memory_store_metrics = self._get_memory_store_metrics()

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
            network_recv_mb=network_recv_mb,
            gpu_available=gpu_metrics['available'],
            gpu_count=gpu_metrics['count'],
            gpu_utilization=gpu_metrics['utilization'],
            gpu_memory_used=gpu_metrics['memory_used'],
            gpu_memory_total=gpu_metrics['memory_total'],
            gpu_temperature=gpu_metrics['temperature'],
            gpu_names=gpu_metrics['names'],
            memory_store_entries=memory_store_metrics['entries'],
            memory_store_size_kb=memory_store_metrics['size_kb'],
            memory_store_emails=memory_store_metrics['emails'],
            memory_store_phones=memory_store_metrics['phones'],
            memory_store_ips=memory_store_metrics['ips'],
            memory_store_usernames=memory_store_metrics['usernames'],
            memory_store_domains=memory_store_metrics['domains'],
            memory_store_notes=memory_store_metrics['notes']
        )

    def _check_gpu_availability(self) -> bool:
        """Check if GPU monitoring is available via nvidia-smi.

        Returns:
            True if nvidia-smi is available, False otherwise
        """
        try:
            result = subprocess.run(  # nosec B603, B607 - nvidia-smi is a trusted system binary
                ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return False

    def _get_gpu_metrics(self) -> Dict:
        """Collect GPU metrics using nvidia-smi.

        Returns:
            Dictionary with GPU metrics
        """
        default_metrics = {
            'available': False,
            'count': 0,
            'utilization': [],
            'memory_used': [],
            'memory_total': [],
            'temperature': [],
            'names': []
        }

        if not self._gpu_available:
            return default_metrics

        try:
            # Query nvidia-smi for GPU metrics
            result = subprocess.run([  # nosec B603, B607 - nvidia-smi is a trusted system binary
                'nvidia-smi',
                '--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu',
                '--format=csv,noheader,nounits'
            ], capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                return default_metrics

            lines = result.stdout.strip().split('\n')
            if not lines or not lines[0]:
                return default_metrics

            names = []
            utilization = []
            memory_used = []
            memory_total = []
            temperature = []

            for line in lines:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 5:
                    names.append(parts[0])
                    utilization.append(float(parts[1]))
                    memory_used.append(float(parts[2]) / 1024)  # Convert MB to GB
                    memory_total.append(float(parts[3]) / 1024)  # Convert MB to GB
                    temperature.append(float(parts[4]))

            return {
                'available': True,
                'count': len(names),
                'utilization': utilization,
                'memory_used': memory_used,
                'memory_total': memory_total,
                'temperature': temperature,
                'names': names
            }

        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, Exception):
            return default_metrics
    
    def _get_memory_store_metrics(self) -> Dict:
        """Collect Memory Store metrics.
        
        Returns:
            Dictionary with memory store metrics
        """
        try:
            from core.memory_store import get_memory_store
            
            memory = get_memory_store()
            
            # Force reload from disk to get latest data
            memory._load()
            
            summary = memory.get_summary()
            
            # Get file size
            memory_file = memory.memory_file
            size_kb = 0.0
            if os.path.exists(memory_file):
                size_kb = os.path.getsize(memory_file) / 1024
            
            return {
                'entries': summary['total_entries'],
                'size_kb': size_kb,
                'emails': summary['emails'],
                'phones': summary['phones'],
                'ips': summary['ips'],
                'usernames': summary['usernames'],
                'domains': summary['domains'],
                'notes': summary['notes']
            }
        except Exception as e:
            # If memory store not available, return zeros
            return {
                'entries': 0,
                'size_kb': 0.0,
                'emails': 0,
                'phones': 0,
                'ips': 0,
                'usernames': 0,
                'domains': 0,
                'notes': 0
            }

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
