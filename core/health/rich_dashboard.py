"""Rich Terminal UI for Health Monitoring.

This module provides a beautiful terminal-based dashboard with:
- Live system metrics
- Component health status
- Performance statistics
- Alert notifications
"""

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.progress import Progress, BarColumn, TextColumn
from rich.text import Text
from rich import box
from datetime import datetime
from pathlib import Path
import time
import threading
from typing import Optional

from .system_monitor import SystemMonitor, SystemMetrics
from .component_checker import ComponentHealthChecker, HealthStatus
from .performance_tracker import PerformanceTracker
from .alert_system import AlertSystem, AlertLevel


class RichHealthDashboard:
    """Rich terminal-based health monitoring dashboard."""

    def __init__(self, project_root: Path, update_interval: float = 2.0):
        """Initialize Rich dashboard.
        
        Args:
            project_root: Path to project root
            update_interval: Seconds between updates
        """
        self.project_root = project_root
        self.update_interval = update_interval
        
        # Initialize components
        self.console = Console()
        self.system_monitor = SystemMonitor(update_interval=1.0)
        self.component_checker = ComponentHealthChecker(project_root)
        self.performance_tracker = PerformanceTracker()
        self.alert_system = AlertSystem()
        
        # State
        self.is_running = False
        self._update_thread: Optional[threading.Thread] = None
        self._last_component_check = 0
        self._component_check_interval = 30  # Check components every 30s

    def start(self):
        """Start the dashboard."""
        self.console.clear()
        self.console.print("[bold green]🦙 CrawlLama Health Monitoring Dashboard[/bold green]")
        self.console.print(f"Project: {self.project_root}")
        self.console.print("Press Ctrl+C to exit\n")
        
        # Start system monitor
        self.system_monitor.start()
        
        # Start dashboard
        self.is_running = True
        
        try:
            with Live(self._generate_layout(), refresh_per_second=1, 
                     console=self.console, screen=False) as live:
                while self.is_running:
                    # Check components periodically
                    if time.time() - self._last_component_check > self._component_check_interval:
                        self._check_components()
                    
                    # Update display
                    live.update(self._generate_layout())
                    time.sleep(self.update_interval)
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Dashboard stopped by user[/yellow]")
        finally:
            self.stop()

    def stop(self):
        """Stop the dashboard."""
        self.is_running = False
        self.system_monitor.stop()

    def _check_components(self):
        """Check component health in background."""
        try:
            health = self.component_checker.check_all()
            
            # Check for alerts
            self.alert_system.check_alerts({
                'component_health': health,
                'system_metrics': self.system_monitor.get_latest_metrics(),
                'performance_stats': self.performance_tracker.get_all_stats()
            })
            
            self._last_component_check = time.time()
        except Exception as e:
            self.console.print(f"[red]Error checking components: {e}[/red]")

    def _generate_layout(self) -> Layout:
        """Generate the dashboard layout."""
        layout = Layout()
        
        # Create main sections
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        # Split body into columns
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )
        
        # Split left column
        layout["left"].split_column(
            Layout(name="system", ratio=2),
            Layout(name="components", ratio=2)
        )
        
        # Split right column
        layout["right"].split_column(
            Layout(name="performance", ratio=2),
            Layout(name="alerts", ratio=2)
        )
        
        # Fill sections
        layout["header"].update(self._create_header())
        layout["system"].update(self._create_system_panel())
        layout["components"].update(self._create_components_panel())
        layout["performance"].update(self._create_performance_panel())
        layout["alerts"].update(self._create_alerts_panel())
        layout["footer"].update(self._create_footer())
        
        return layout

    def _create_header(self) -> Panel:
        """Create header panel."""
        text = Text.assemble(
            ("🦙 CrawlLama Health Dashboard", "bold green"),
            " | ",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "cyan")
        )
        return Panel(text, style="bold", box=box.DOUBLE)

    def _create_system_panel(self) -> Panel:
        """Create system metrics panel."""
        metrics = self.system_monitor.get_latest_metrics()
        
        if not metrics:
            return Panel("Collecting metrics...", title="📊 System Metrics", 
                        border_style="blue")
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right")
        table.add_column("Bar", width=20)
        
        # CPU
        cpu_color = self._get_usage_color(metrics.cpu_percent)
        cpu_bar = self._create_bar(metrics.cpu_percent, 100, cpu_color)
        table.add_row(
            "CPU",
            f"[{cpu_color}]{metrics.cpu_percent:.1f}%[/{cpu_color}]",
            cpu_bar
        )
        
        # Memory
        mem_color = self._get_usage_color(metrics.memory_percent)
        mem_bar = self._create_bar(metrics.memory_percent, 100, mem_color)
        table.add_row(
            "Memory",
            f"[{mem_color}]{metrics.memory_used_gb:.1f}/{metrics.memory_total_gb:.1f} GB[/{mem_color}]",
            mem_bar
        )
        
        # Disk
        disk_color = self._get_usage_color(metrics.disk_percent)
        disk_bar = self._create_bar(metrics.disk_percent, 100, disk_color)
        table.add_row(
            "Disk",
            f"[{disk_color}]{metrics.disk_used_gb:.1f}/{metrics.disk_total_gb:.1f} GB[/{disk_color}]",
            disk_bar
        )
        
        # Network
        table.add_row(
            "Network ↓↑",
            f"[green]{metrics.network_recv_mb:.2f}/{metrics.network_sent_mb:.2f} MB/s[/green]",
            ""
        )
        
        # Disk I/O
        table.add_row(
            "Disk I/O",
            f"[blue]R:{metrics.disk_read_mb:.2f} W:{metrics.disk_write_mb:.2f} MB/s[/blue]",
            ""
        )
        
        return Panel(table, title="📊 System Metrics", border_style="blue")

    def _create_components_panel(self) -> Panel:
        """Create components health panel."""
        health = self.component_checker.last_results
        
        if not health:
            return Panel("Checking components...", title="🔍 Component Health",
                        border_style="green")
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Component", style="cyan")
        table.add_column("Status", justify="center", width=10)
        table.add_column("Response", justify="right")
        
        for name, status in health.items():
            status_icon, status_color = self._get_health_icon(status.status)
            
            table.add_row(
                name,
                f"[{status_color}]{status_icon}[/{status_color}]",
                f"[dim]{status.response_time_ms:.0f}ms[/dim]"
            )
        
        return Panel(table, title="🔍 Component Health", border_style="green")

    def _create_performance_panel(self) -> Panel:
        """Create performance statistics panel."""
        stats = self.performance_tracker.get_all_stats()
        
        if not stats:
            return Panel("No performance data", title="📈 Performance",
                        border_style="yellow")
        
        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("Operation", style="cyan")
        table.add_column("Avg", justify="right")
        table.add_column("P95", justify="right")
        table.add_column("Count", justify="right")
        
        for op_name, op_stats in list(stats.items())[:5]:  # Show top 5
            avg_color = "green" if op_stats.avg_duration_ms < 1000 else "yellow"
            p95_color = "green" if op_stats.p95_duration_ms < 2000 else "yellow"
            
            table.add_row(
                op_name[:15],
                f"[{avg_color}]{op_stats.avg_duration_ms:.0f}ms[/{avg_color}]",
                f"[{p95_color}]{op_stats.p95_duration_ms:.0f}ms[/{p95_color}]",
                f"[dim]{op_stats.count}[/dim]"
            )
        
        return Panel(table, title="📈 Performance", border_style="yellow")

    def _create_alerts_panel(self) -> Panel:
        """Create alerts panel."""
        alerts = self.alert_system.get_alerts(unacknowledged_only=True)
        
        if not alerts:
            return Panel("[green]No active alerts ✓[/green]", 
                        title="🚨 Alerts", border_style="red")
        
        # Sort by level (critical first)
        level_order = {
            AlertLevel.CRITICAL: 0,
            AlertLevel.ERROR: 1,
            AlertLevel.WARNING: 2,
            AlertLevel.INFO: 3
        }
        alerts.sort(key=lambda a: level_order[a.level])
        
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Level", width=8)
        table.add_column("Message")
        
        for alert in alerts[:5]:  # Show top 5 alerts
            level_icon, level_color = self._get_alert_icon(alert.level)
            
            table.add_row(
                f"[{level_color}]{level_icon}[/{level_color}]",
                f"[{level_color}]{alert.message}[/{level_color}]"
            )
        
        return Panel(table, title=f"🚨 Alerts ({len(alerts)})", 
                    border_style="red")

    def _create_footer(self) -> Panel:
        """Create footer panel."""
        alert_summary = self.alert_system.get_alert_summary()
        
        text = Text.assemble(
            ("Alerts: ", "dim"),
            (f"🔴 {alert_summary['critical']} ", "red" if alert_summary['critical'] > 0 else "dim"),
            (f"🟠 {alert_summary['error']} ", "yellow" if alert_summary['error'] > 0 else "dim"),
            (f"🟡 {alert_summary['warning']} ", "yellow" if alert_summary['warning'] > 0 else "dim"),
            " | ",
            ("Press Ctrl+C to exit", "dim")
        )
        
        return Panel(text, style="dim")

    def _get_usage_color(self, percent: float) -> str:
        """Get color based on usage percentage."""
        if percent < 60:
            return "green"
        elif percent < 80:
            return "yellow"
        else:
            return "red"

    def _create_bar(self, value: float, max_value: float, color: str) -> str:
        """Create a text-based progress bar."""
        bar_width = 20
        filled = int((value / max_value) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        return f"[{color}]{bar}[/{color}]"

    def _get_health_icon(self, status: HealthStatus) -> tuple:
        """Get icon and color for health status."""
        if status == HealthStatus.HEALTHY:
            return "✓", "green"
        elif status == HealthStatus.DEGRADED:
            return "⚠", "yellow"
        elif status == HealthStatus.UNHEALTHY:
            return "✗", "red"
        else:
            return "?", "dim"

    def _get_alert_icon(self, level: AlertLevel) -> tuple:
        """Get icon and color for alert level."""
        if level == AlertLevel.CRITICAL:
            return "🔴", "red bold"
        elif level == AlertLevel.ERROR:
            return "🟠", "red"
        elif level == AlertLevel.WARNING:
            return "🟡", "yellow"
        else:
            return "🔵", "blue"


def run_terminal_dashboard(project_root: Optional[Path] = None):
    """Run the terminal dashboard.
    
    Args:
        project_root: Project root path, or None to auto-detect
    """
    if project_root is None:
        project_root = Path.cwd()
    
    dashboard = RichHealthDashboard(project_root)
    dashboard.start()


if __name__ == "__main__":
    run_terminal_dashboard()
