"""Log Viewer Widget - Displays test error logs and details."""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Dict, Any, Optional
import sys
from pathlib import Path

# Add parent directory to path for theme import
sys.path.insert(0, str(Path(__file__).parent.parent))
from theme import DarkTheme

# Optional dependency
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False


class LogViewer(ttk.Frame):
    """Widget for displaying test error logs."""

    def __init__(self, parent):
        """
        Initialize LogViewer.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        self.current_error = None

        self._create_widgets()

    def _create_widgets(self):
        """Create log viewer widgets."""
        # Main frame
        main_frame = ttk.LabelFrame(self, text="Error Details", padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Toolbar
        toolbar = ttk.Frame(main_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        # Clear button
        self.clear_btn = ttk.Button(
            toolbar,
            text="🗑️ Clear",
            command=self.clear
        )
        self.clear_btn.pack(side=tk.LEFT, padx=2)

        # Copy button
        self.copy_btn = ttk.Button(
            toolbar,
            text="📋 Copy",
            command=self.copy_to_clipboard
        )
        self.copy_btn.pack(side=tk.LEFT, padx=2)

        # Export button
        self.export_btn = ttk.Button(
            toolbar,
            text="💾 Export",
            command=self.export_to_file
        )
        self.export_btn.pack(side=tk.LEFT, padx=2)

        # Text widget with scrollbar
        self.text = scrolledtext.ScrolledText(
            main_frame,
            height=12,
            font=('Courier', 9),
            wrap=tk.WORD,
            bg=DarkTheme.BG_DARK,
            fg=DarkTheme.TEXT_PRIMARY,
            insertbackground=DarkTheme.TEXT_PRIMARY,
            selectbackground=DarkTheme.TREEVIEW_SELECT,
            selectforeground=DarkTheme.TEXT_PRIMARY,
            relief=tk.FLAT
        )
        self.text.pack(fill=tk.BOTH, expand=True)

        # Configure tags for syntax highlighting
        self.text.tag_configure('error', foreground=DarkTheme.STATUS_FAILED)
        self.text.tag_configure('file', foreground=DarkTheme.ACCENT_BLUE)
        self.text.tag_configure('line', foreground=DarkTheme.ACCENT_YELLOW)
        self.text.tag_configure('test', foreground=DarkTheme.STATUS_PASSED)
        self.text.tag_configure('message', foreground=DarkTheme.ACCENT_ORANGE)
        self.text.tag_configure('dim', foreground=DarkTheme.TEXT_DIM)
        self.text.tag_configure('skipped', foreground=DarkTheme.ACCENT_YELLOW)

        # Initial message
        self._show_empty_message()

    def add_skipped(self, result: Dict[str, Any]):
        """
        Add skipped test information.

        Args:
            result: Test result dictionary with skipped tests
        """
        self.text.config(state=tk.NORMAL)

        # Clear if this is the first entry
        if self.current_error is None:
            self.text.delete('1.0', tk.END)

        self.current_error = result

        # Add separator if not first entry
        if self.text.get('1.0', tk.END).strip():
            self.text.insert(tk.END, "\n" + "=" * 80 + "\n\n")

        # Test file name
        filename = result['test_file']['filename']
        self.text.insert(tk.END, f"📁 Test File: ", 'dim')
        self.text.insert(tk.END, f"{filename}\n", 'file')

        # Status
        self.text.insert(tk.END, f"⏭️ Status: ", 'dim')
        self.text.insert(tk.END, "SKIPPED\n", 'skipped')

        # Duration
        duration = result.get('duration', 0)
        self.text.insert(tk.END, f"⏱️  Duration: ", 'dim')
        self.text.insert(tk.END, f"{duration:.2f}s\n\n", 'line')

        # Count
        skipped_count = result.get('skipped', 0)
        self.text.insert(tk.END, f"Skipped {skipped_count} test(s)\n\n", 'skipped')

        # Skipped tests details
        for detail in result.get('details', []):
            if detail.get('outcome') == 'skipped':
                self._add_skipped_test_detail(detail)

        # Reason if present
        if 'error' in result and result['error']:
            self.text.insert(tk.END, "Reason: ", 'skipped')
            self.text.insert(tk.END, f"{result['error']}\n", 'message')

        self.text.config(state=tk.DISABLED)
        self.text.see(tk.END)

    def _add_skipped_test_detail(self, detail: Dict[str, Any]):
        """Add details of a skipped test."""
        test_name = detail['name']

        self.text.insert(tk.END, "  ├─ Test: ", 'dim')
        self.text.insert(tk.END, f"{test_name}\n", 'skipped')

        # Reason message if available
        skip_msg = detail.get('error_message') or detail.get('call', {}).get('longrepr', 'No reason provided')
        if skip_msg and skip_msg != 'No reason provided':
            self.text.insert(tk.END, "  └─ Reason: ", 'dim')
            self.text.insert(tk.END, f"{skip_msg}\n\n", 'message')
        else:
            self.text.insert(tk.END, "\n")

    def add_error(self, result: Dict[str, Any]):
        """
        Add error information from test result.

        Args:
            result: Test result dictionary
        """
        self.text.config(state=tk.NORMAL)

        # Clear if this is the first error
        if self.current_error is None:
            self.text.delete('1.0', tk.END)

        self.current_error = result

        # Add separator if not first error
        if self.text.get('1.0', tk.END).strip():
            self.text.insert(tk.END, "\n" + "=" * 80 + "\n\n")

        # Test file name
        filename = result['test_file']['filename']
        self.text.insert(tk.END, f"📁 Test File: ", 'dim')
        self.text.insert(tk.END, f"{filename}\n", 'file')

        # Status
        status = result.get('status', 'unknown')
        self.text.insert(tk.END, f"❌ Status: ", 'dim')
        self.text.insert(tk.END, f"{status.upper()}\n", 'error')

        # Duration
        duration = result.get('duration', 0)
        self.text.insert(tk.END, f"⏱️  Duration: ", 'dim')
        self.text.insert(tk.END, f"{duration:.2f}s\n\n", 'line')

        # Failed tests details
        for detail in result.get('details', []):
            if detail.get('outcome') == 'failed':
                self._add_failed_test_detail(detail)

        # General error if present
        if 'error' in result:
            self.text.insert(tk.END, "Error: ", 'error')
            self.text.insert(tk.END, f"{result['error']}\n", 'message')

        self.text.config(state=tk.DISABLED)
        self.text.see(tk.END)

    def _add_failed_test_detail(self, detail: Dict[str, Any]):
        """Add details of a failed test."""
        test_name = detail['name']

        self.text.insert(tk.END, "  ├─ Test: ", 'dim')
        self.text.insert(tk.END, f"{test_name}\n", 'test')

        # Error message
        error_msg = detail.get('error_message', 'Unknown error')
        self.text.insert(tk.END, "  ├─ Error: ", 'dim')
        self.text.insert(tk.END, f"{error_msg}\n", 'message')

        # Duration
        duration = detail.get('duration', 0)
        self.text.insert(tk.END, "  └─ Duration: ", 'dim')
        self.text.insert(tk.END, f"{duration:.2f}s\n\n", 'line')

    def show_detail(self, result: Dict[str, Any], test_name: Optional[str] = None):
        """
        Show detailed error for a specific test or file.

        Args:
            result: Test result dictionary
            test_name: Optional specific test name to show
        """
        self.text.config(state=tk.NORMAL)
        self.text.delete('1.0', tk.END)

        self.current_error = result

        # Header
        filename = result['test_file']['filename']
        self.text.insert(tk.END, "=" * 80 + "\n", 'dim')
        self.text.insert(tk.END, f"📁 {filename}\n", 'file')
        self.text.insert(tk.END, "=" * 80 + "\n\n", 'dim')

        if test_name:
            # Show specific test
            for detail in result.get('details', []):
                if detail['name'] == test_name:
                    self._show_detailed_error(detail)
                    break
        else:
            # Show all failed tests
            failed_tests = [d for d in result.get('details', [])
                          if d.get('outcome') == 'failed']

            if failed_tests:
                for detail in failed_tests:
                    self._show_detailed_error(detail)
                    self.text.insert(tk.END, "\n" + "-" * 80 + "\n\n")
            else:
                # Show general error
                error = result.get('error', 'No error details available')
                self.text.insert(tk.END, error, 'message')

        self.text.config(state=tk.DISABLED)
        self.text.see('1.0')

    def _show_detailed_error(self, detail: Dict[str, Any]):
        """Show detailed error information."""
        test_name = detail['name']

        self.text.insert(tk.END, f"Test: {test_name}\n", 'test')
        self.text.insert(tk.END, f"Duration: {detail.get('duration', 0):.2f}s\n\n", 'line')

        # Error message
        error_msg = detail.get('error_message', 'Unknown error')
        self.text.insert(tk.END, "Error Message:\n", 'error')
        self.text.insert(tk.END, f"{error_msg}\n\n", 'message')

        # Traceback if available
        if 'traceback' in detail and detail['traceback']:
            self.text.insert(tk.END, "Traceback:\n", 'dim')
            self.text.insert(tk.END, f"{detail['traceback']}\n", 'message')

    def copy_to_clipboard(self):
        """Copy current error to clipboard."""
        if not PYPERCLIP_AVAILABLE:
            self._show_status("❌ pyperclip not installed. Install with: pip install pyperclip")
            return

        try:
            content = self.text.get('1.0', tk.END)
            pyperclip.copy(content)
            self._show_status("✅ Copied to clipboard")
        except Exception as e:
            self._show_status(f"❌ Failed to copy: {e}")

    def export_to_file(self):
        """Export errors to file."""
        from tkinter import filedialog

        try:
            filepath = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )

            if filepath:
                content = self.text.get('1.0', tk.END)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                self._show_status(f"✅ Exported to {filepath}")
        except Exception as e:
            self._show_status(f"❌ Export failed: {e}")

    def clear(self):
        """Clear all error logs."""
        self.text.config(state=tk.NORMAL)
        self.text.delete('1.0', tk.END)
        self.current_error = None
        self._show_empty_message()
        self.text.config(state=tk.DISABLED)

    def _show_empty_message(self):
        """Show message when no errors."""
        self.text.config(state=tk.NORMAL)
        self.text.insert(tk.END, "No errors to display\n\n", 'dim')
        self.text.insert(tk.END, "✅ All tests passed or no tests run yet.", 'dim')
        self.text.config(state=tk.DISABLED)

    def _show_status(self, message: str):
        """Show temporary status message."""
        # You could implement a status bar here
        print(message)


if __name__ == "__main__":
    # Test the widget
    root = tk.Tk()
    root.title("Log Viewer Widget")
    root.geometry("800x500")

    viewer = LogViewer(root)
    viewer.pack(fill=tk.BOTH, expand=True)

    # Test with dummy error
    def add_test_error():
        result = {
            'test_file': {
                'filename': 'test_example.py',
                'category': 'unit'
            },
            'status': 'failed',
            'duration': 1.5,
            'details': [
                {
                    'name': 'test_function_1',
                    'outcome': 'failed',
                    'duration': 0.8,
                    'error_message': 'AssertionError: Expected True but got False',
                    'traceback': 'File "test_example.py", line 42, in test_function_1\n    assert result == True'
                }
            ]
        }
        viewer.add_error(result)

    tk.Button(root, text="Add Test Error", command=add_test_error).pack(pady=10)

    root.mainloop()
