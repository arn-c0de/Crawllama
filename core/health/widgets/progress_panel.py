"""Progress Panel Widget - Displays test execution progress."""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

# Add parent directory to path for theme import
sys.path.insert(0, str(Path(__file__).parent.parent))
from theme import DarkTheme


class ProgressPanel(ttk.Frame):
    """Widget displaying test execution progress."""

    def __init__(self, parent):
        """
        Initialize ProgressPanel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.current = 0
        self.total = 0

        self._create_widgets()

    def _create_widgets(self):
        """Create progress widgets."""
        # Main frame
        main_frame = ttk.LabelFrame(self, text="Progress", padding=10)
        main_frame.pack(fill=tk.X, padx=5, pady=5)

        # Progress bar
        self.progressbar = ttk.Progressbar(
            main_frame,
            mode='determinate',
            length=400
        )
        self.progressbar.pack(fill=tk.X, pady=(0, 5))

        # Status label
        self.status_label = tk.Label(
            main_frame,
            text="Ready",
            font=('Arial', 10),
            fg='#6b7280'
        )
        self.status_label.pack()

        # Details label
        self.details_label = tk.Label(
            main_frame,
            text="0/0 tests (0%)",
            font=('Arial', 9),
            fg='#9ca3af'
        )
        self.details_label.pack()

    def start(self, total: int):
        """
        Start progress tracking.

        Args:
            total: Total number of tests
        """
        self.total = total
        self.current = 0
        self.progressbar['maximum'] = total
        self.progressbar['value'] = 0
        self.status_label.config(text="Running tests...", fg='#3b82f6')
        self._update_details()

    def update(self, current: int | None = None, status: str = ""):
        """
        Update progress.

        Args:
            current: Current test number (increments if None)
            status: Optional status message
        """
        if current is not None:
            self.current = current
        else:
            self.current += 1

        self.progressbar['value'] = self.current

        if status:
            self.status_label.config(text=status)

        self._update_details()

    def complete(self, success: bool = True):
        """
        Mark progress as complete.

        Args:
            success: Whether tests passed successfully
        """
        self.current = self.total
        self.progressbar['value'] = self.total

        if success:
            self.status_label.config(text="✅ All tests completed", fg='#10b981')
        else:
            self.status_label.config(text="❌ Tests completed with failures", fg='#ef4444')

        self._update_details()

    def reset(self):
        """Reset progress to initial state."""
        self.current = 0
        self.total = 0
        self.progressbar['value'] = 0
        self.status_label.config(text="Ready", fg='#6b7280')
        self.details_label.config(text="0/0 tests (0%)")

    def _update_details(self):
        """Update details label."""
        if self.total > 0:
            percentage = (self.current / self.total) * 100
            self.details_label.config(
                text=f"{self.current}/{self.total} tests ({percentage:.0f}%)"
            )
        else:
            self.details_label.config(text="0/0 tests (0%)")


class DetailedProgressPanel(ttk.Frame):
    """Extended progress panel with more details."""

    def __init__(self, parent):
        """
        Initialize DetailedProgressPanel.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.current = 0
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0

        self._create_widgets()

    def _create_widgets(self):
        """Create detailed progress widgets."""
        # Main frame
        main_frame = ttk.LabelFrame(self, text="Test Execution Progress", padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Progress bar
        self.progressbar = ttk.Progressbar(
            main_frame,
            mode='determinate',
            length=500
        )
        self.progressbar.pack(fill=tk.X, pady=(0, 10))

        # Status frame
        status_frame = tk.Frame(main_frame, bg=DarkTheme.BG_DARK)
        status_frame.pack(fill=tk.X, pady=5)

        # Current test label
        self.current_label = tk.Label(
            status_frame,
            text="Waiting to start...",
            font=('Arial', 10, 'bold'),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.TEXT_PRIMARY
        )
        self.current_label.pack(anchor=tk.W)

        # Stats frame
        stats_frame = tk.Frame(main_frame, bg=DarkTheme.BG_DARK)
        stats_frame.pack(fill=tk.X, pady=5)

        # Progress label
        self.progress_label = tk.Label(
            stats_frame,
            text="0/0 tests (0%)",
            font=('Arial', 9),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.TEXT_SECONDARY
        )
        self.progress_label.pack(side=tk.LEFT)

        # Separator
        tk.Label(stats_frame, text=" | ", bg=DarkTheme.BG_DARK, fg=DarkTheme.TEXT_DIM).pack(side=tk.LEFT)

        # Passed label
        self.passed_label = tk.Label(
            stats_frame,
            text="✅ 0",
            font=('Arial', 9),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.STATUS_PASSED
        )
        self.passed_label.pack(side=tk.LEFT, padx=5)

        # Failed label
        self.failed_label = tk.Label(
            stats_frame,
            text="❌ 0",
            font=('Arial', 9),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.STATUS_FAILED
        )
        self.failed_label.pack(side=tk.LEFT, padx=5)

        # Skipped label
        self.skipped_label = tk.Label(
            stats_frame,
            text="⏭️ 0",
            font=('Arial', 9),
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.STATUS_SKIPPED
        )
        self.skipped_label.pack(side=tk.LEFT, padx=5)

    def start(self, total: int):
        """
        Start progress tracking.

        Args:
            total: Total number of tests
        """
        self.total = total
        self.current = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0

        self.progressbar['maximum'] = total
        self.progressbar['value'] = 0

        self.current_label.config(text="Starting tests...", fg='#3b82f6')
        self._update_stats()

    def update(self, test_name: str, status: str):
        """
        Update progress with test result.

        Args:
            test_name: Name of completed test
            status: Test status (passed/failed/skipped)
        """
        self.current += 1
        self.progressbar['value'] = self.current

        # Update counts
        if status == 'passed':
            self.passed += 1
        elif status == 'failed':
            self.failed += 1
        elif status == 'skipped':
            self.skipped += 1

        # Update current test label
        status_icons = {
            'passed': '✅',
            'failed': '❌',
            'skipped': '⏭️',
            'running': '🔄'
        }

        icon = status_icons.get(status, '❓')
        self.current_label.config(text=f"{icon} {test_name}")

        self._update_stats()

    def complete(self):
        """Mark progress as complete."""
        self.current = self.total
        self.progressbar['value'] = self.total

        if self.failed > 0:
            self.current_label.config(
                text=f"❌ Completed with {self.failed} failure(s)",
                fg='#ef4444'
            )
        else:
            self.current_label.config(
                text="✅ All tests passed!",
                fg='#10b981'
            )

        self._update_stats()

    def reset(self):
        """Reset progress to initial state."""
        self.current = 0
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0

        self.progressbar['value'] = 0
        self.current_label.config(text="Waiting to start...", fg='#111827')
        self._update_stats()

    def _update_stats(self):
        """Update statistics labels."""
        if self.total > 0:
            percentage = (self.current / self.total) * 100
            self.progress_label.config(
                text=f"{self.current}/{self.total} tests ({percentage:.0f}%)"
            )
        else:
            self.progress_label.config(text="0/0 tests (0%)")

        self.passed_label.config(text=f"✅ {self.passed}")
        self.failed_label.config(text=f"❌ {self.failed}")
        self.skipped_label.config(text=f"⏭️ {self.skipped}")


if __name__ == "__main__":
    # Test the widget
    root = tk.Tk()
    root.title("Progress Panel Widget")
    root.geometry("600x300")

    # Simple progress
    simple = ProgressPanel(root)
    simple.pack(fill=tk.X)

    # Detailed progress
    detailed = DetailedProgressPanel(root)
    detailed.pack(fill=tk.BOTH, expand=True)

    # Test updates
    def test_progress():
        simple.start(10)
        detailed.start(10)

        def update_step(step):
            if step < 10:
                simple.update(status=f"Running test {step+1}...")
                status = 'passed' if step % 3 != 1 else 'failed'
                detailed.update(f"test_example_{step}", status)
                root.after(500, lambda: update_step(step + 1))
            else:
                simple.complete(success=detailed.failed == 0)
                detailed.complete()

        update_step(0)

    tk.Button(root, text="Start Test", command=test_progress).pack(pady=10)

    root.mainloop()
