"""Status Card Widget - Displays test statistics in card format."""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any
import sys
from pathlib import Path

# Add parent directory to path for theme import
sys.path.insert(0, str(Path(__file__).parent.parent))
from theme import DarkTheme


class StatusCardWidget(ttk.Frame):
    """Widget displaying test status statistics in card format."""

    def __init__(self, parent):
        """
        Initialize StatusCardWidget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.cards = {}
        self._create_widgets()

    def _create_widgets(self):
        """Create status cards."""
        # Frame for cards
        cards_frame = ttk.Frame(self)
        cards_frame.pack(fill=tk.X, padx=5, pady=5)

        # Create cards
        self.cards['passed'] = self._create_card(
            cards_frame, '✅ Passed', '0/0', '#10b981', 0
        )

        self.cards['failed'] = self._create_card(
            cards_frame, '❌ Failed', '0', '#ef4444', 1
        )

        self.cards['skipped'] = self._create_card(
            cards_frame, '⏭️ Skipped', '0', '#6b7280', 2
        )

        self.cards['duration'] = self._create_card(
            cards_frame, '⏱️ Duration', '0.0s', '#3b82f6', 3
        )

    def _create_card(self, parent, title: str, initial_value: str,
                    color: str, column: int) -> Dict[str, Any]:
        """
        Create a single status card.

        Args:
            parent: Parent widget
            title: Card title
            initial_value: Initial value to display
            color: Color code
            column: Grid column position

        Returns:
            Dictionary with card widgets
        """
        # Card frame with dark theme
        card_frame = tk.Frame(
            parent,
            bg=DarkTheme.BG_MEDIUM,
            relief=tk.FLAT,
            borderwidth=1,
            highlightbackground=DarkTheme.BORDER,
            highlightthickness=1
        )
        card_frame.grid(row=0, column=column, padx=5, pady=5, sticky='ew')

        # Title
        title_label = tk.Label(
            card_frame,
            text=title,
            font=('Arial', 10, 'bold'),
            bg=DarkTheme.BG_MEDIUM,
            fg=DarkTheme.TEXT_DIM
        )
        title_label.pack(pady=(10, 5))

        # Value
        value_label = tk.Label(
            card_frame,
            text=initial_value,
            font=('Arial', 24, 'bold'),
            bg=DarkTheme.BG_MEDIUM,
            fg=color
        )
        value_label.pack(pady=(5, 10))

        # Configure grid
        parent.grid_columnconfigure(column, weight=1)

        return {
            'frame': card_frame,
            'title': title_label,
            'value': value_label,
            'color': color
        }

    def update(self, summary: Dict[str, Any]):
        """
        Update cards with new statistics.

        Args:
            summary: Summary dictionary from ResultParser
        """
        total = summary.get('total_tests', 0)
        passed = summary.get('passed', 0)
        failed = summary.get('failed', 0)
        skipped = summary.get('skipped', 0)
        duration = summary.get('duration', 0)

        # Update passed card
        self.cards['passed']['value'].config(text=f"{passed}/{total}")

        # Update failed card
        self.cards['failed']['value'].config(text=str(failed))

        # Update skipped card
        self.cards['skipped']['value'].config(text=str(skipped))

        # Update duration card
        if duration < 60:
            duration_str = f"{duration:.1f}s"
        elif duration < 3600:
            duration_str = f"{duration/60:.1f}m"
        else:
            duration_str = f"{duration/3600:.1f}h"

        self.cards['duration']['value'].config(text=duration_str)

        # Update colors based on status
        if failed > 0:
            self.cards['passed']['value'].config(fg='#ef4444')
        else:
            self.cards['passed']['value'].config(fg='#10b981')

    def reset(self):
        """Reset all cards to initial state."""
        self.cards['passed']['value'].config(text='0/0')
        self.cards['failed']['value'].config(text='0')
        self.cards['skipped']['value'].config(text='0')
        self.cards['duration']['value'].config(text='0.0s')


class DetailedStatusWidget(ttk.Frame):
    """Extended status widget with more detailed information."""

    def __init__(self, parent):
        """
        Initialize DetailedStatusWidget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self._create_widgets()

    def _create_widgets(self):
        """Create detailed status display."""
        # Main frame
        main_frame = ttk.LabelFrame(self, text="Test Summary", padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create text widget for detailed info
        self.text = tk.Text(
            main_frame,
            height=8,
            width=50,
            font=('Courier', 9),
            bg=DarkTheme.BG_MEDIUM,
            fg=DarkTheme.TEXT_PRIMARY,
            insertbackground=DarkTheme.TEXT_PRIMARY,
            selectbackground=DarkTheme.TREEVIEW_SELECT,
            selectforeground=DarkTheme.TEXT_PRIMARY,
            relief=tk.FLAT,
            state=tk.DISABLED
        )
        self.text.pack(fill=tk.BOTH, expand=True)

        # Configure tags for colors
        self.text.tag_configure('header', font=('Courier', 9, 'bold'), foreground=DarkTheme.TEXT_PRIMARY)
        self.text.tag_configure('passed', foreground=DarkTheme.STATUS_PASSED)
        self.text.tag_configure('failed', foreground=DarkTheme.STATUS_FAILED)
        self.text.tag_configure('skipped', foreground=DarkTheme.STATUS_SKIPPED)

    def update(self, summary: Dict[str, Any], category_summary: Dict[str, Any] = None):
        """
        Update detailed status information.

        Args:
            summary: Summary dictionary
            category_summary: Optional category breakdown
        """
        self.text.config(state=tk.NORMAL)
        self.text.delete('1.0', tk.END)

        # Overall summary
        total = summary.get('total_tests', 0)
        passed = summary.get('passed', 0)
        failed = summary.get('failed', 0)
        skipped = summary.get('skipped', 0)
        pass_rate = summary.get('pass_rate', 0)
        duration = summary.get('duration', 0)

        self.text.insert(tk.END, "═" * 50 + "\n", 'header')
        self.text.insert(tk.END, f"Total Tests:    {total}\n", 'header')
        self.text.insert(tk.END, f"Passed:         {passed}\n", 'passed')
        self.text.insert(tk.END, f"Failed:         {failed}\n", 'failed')
        self.text.insert(tk.END, f"Skipped:        {skipped}\n", 'skipped')
        self.text.insert(tk.END, f"Pass Rate:      {pass_rate:.1f}%\n", 'header')
        self.text.insert(tk.END, f"Duration:       {duration:.1f}s\n", 'header')
        self.text.insert(tk.END, "═" * 50 + "\n\n", 'header')

        # Category summary
        if category_summary:
            self.text.insert(tk.END, "Category Breakdown:\n", 'header')
            self.text.insert(tk.END, "─" * 50 + "\n")

            for category, stats in sorted(category_summary.items()):
                cat_total = stats.get('tests', 0)
                cat_passed = stats.get('passed', 0)
                cat_failed = stats.get('failed', 0)

                status_color = 'passed' if cat_failed == 0 else 'failed'

                self.text.insert(
                    tk.END,
                    f"  {category.upper():15} | {cat_passed:3}/{cat_total:3} passed\n",
                    status_color
                )

        self.text.config(state=tk.DISABLED)

    def clear(self):
        """Clear the text widget."""
        self.text.config(state=tk.NORMAL)
        self.text.delete('1.0', tk.END)
        self.text.config(state=tk.DISABLED)


if __name__ == "__main__":
    # Test the widget
    root = tk.Tk()
    root.title("Status Card Widget")
    root.geometry("600x400")

    # Simple cards
    cards = StatusCardWidget(root)
    cards.pack(fill=tk.X)

    # Detailed status
    detailed = DetailedStatusWidget(root)
    detailed.pack(fill=tk.BOTH, expand=True)

    # Test update
    summary = {
        'total_tests': 15,
        'passed': 12,
        'failed': 2,
        'skipped': 1,
        'pass_rate': 80.0,  # nosec B105 - numeric UI demo metric, not credentials
        'duration': 15.8
    }

    category_summary = {
        'unit': {'tests': 8, 'passed': 7, 'failed': 1},
        'integration': {'tests': 5, 'passed': 5, 'failed': 0},
        'osint': {'tests': 2, 'passed': 0, 'failed': 2}
    }

    cards.update(summary)
    detailed.update(summary, category_summary)

    root.mainloop()
