"""Health Dashboard - Main GUI for test management."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json

from .test_collector import TestCollector
from .test_runner import TestRunner
from .result_parser import ResultParser
from .theme import DarkTheme
from .widgets.test_tree import TestTreeWidget
from .widgets.status_card import StatusCardWidget, DetailedStatusWidget
from .widgets.progress_panel import DetailedProgressPanel
from .widgets.log_viewer import LogViewer


class HealthDashboard:
    """Main Health Dashboard GUI application."""

    def __init__(self):
        """Initialize Health Dashboard."""
        self.root = tk.Tk()
        self.root.title("🦙 CrawlLama Health Dashboard")
        self.root.geometry("1400x900")

        # Apply dark theme
        DarkTheme.apply_to_root(self.root)

        # Components
        self.collector = TestCollector()

        # Disable JSON report by default to avoid hanging issues
        self.use_json = False
        print("[Dashboard] Using text-only mode for test reporting")

        self.runner = TestRunner(max_workers=4, use_json_report=self.use_json)
        self.parser = ResultParser()

        # State
        self.test_files = []
        self.is_running = False
        self.current_thread = None

        # Create GUI
        self._create_menu()
        self._create_widgets()
        self._load_tests()

        # Configure window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_menu(self):
        """Create menu bar."""
        menubar = tk.Menu(
            self.root,
            bg=DarkTheme.BG_MEDIUM,
            fg=DarkTheme.TEXT_PRIMARY,
            activebackground=DarkTheme.TREEVIEW_SELECT,
            activeforeground=DarkTheme.TEXT_PRIMARY
        )
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0,
                           bg=DarkTheme.BG_MEDIUM, fg=DarkTheme.TEXT_PRIMARY,
                           activebackground=DarkTheme.TREEVIEW_SELECT,
                           activeforeground=DarkTheme.TEXT_PRIMARY)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Refresh Tests", command=self._load_tests)
        file_menu.add_separator()
        file_menu.add_command(label="Export Results (JSON)", command=self._export_json)
        file_menu.add_command(label="Export Results (HTML)", command=self._export_html)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)

        # Tests menu
        tests_menu = tk.Menu(menubar, tearoff=0,
                            bg=DarkTheme.BG_MEDIUM, fg=DarkTheme.TEXT_PRIMARY,
                            activebackground=DarkTheme.TREEVIEW_SELECT,
                            activeforeground=DarkTheme.TEXT_PRIMARY)
        menubar.add_cascade(label="Tests", menu=tests_menu)
        tests_menu.add_command(label="Run All Tests", command=self._run_all_tests)
        tests_menu.add_command(label="Run Selected Test", command=self._run_selected_test)
        tests_menu.add_command(label="Stop Tests", command=self._stop_tests)
        tests_menu.add_separator()
        tests_menu.add_command(label="Clear Results", command=self._clear_results)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0,
                           bg=DarkTheme.BG_MEDIUM, fg=DarkTheme.TEXT_PRIMARY,
                           activebackground=DarkTheme.TREEVIEW_SELECT,
                           activeforeground=DarkTheme.TEXT_PRIMARY)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Expand All", command=lambda: self.test_tree.expand_all())
        view_menu.add_command(label="Collapse All", command=lambda: self.test_tree.collapse_all())

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0,
                           bg=DarkTheme.BG_MEDIUM, fg=DarkTheme.TEXT_PRIMARY,
                           activebackground=DarkTheme.TREEVIEW_SELECT,
                           activeforeground=DarkTheme.TEXT_PRIMARY)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _create_widgets(self):
        """Create main GUI widgets."""
        main_container = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        top_panel = ttk.Frame(main_container)
        main_container.add(top_panel, weight=1)

        bottom_panel = ttk.Frame(main_container)
        main_container.add(bottom_panel, weight=1)

        self._create_top_panel(top_panel)
        self._create_bottom_panel(bottom_panel)

    def _create_top_panel(self, top_panel: ttk.Frame):
        """Create status cards, control bar, and tree/details area."""
        self.status_cards = StatusCardWidget(top_panel)
        self.status_cards.pack(fill=tk.X, pady=(0, 5))

        self._create_control_bar(top_panel)
        self._create_tree_and_details(top_panel)

    def _create_control_bar(self, parent: ttk.Frame):
        """Create the row of control buttons, options, and status label."""
        control_frame = ttk.Frame(parent)
        control_frame.pack(fill=tk.X, pady=5)

        self.run_all_btn = ttk.Button(
            control_frame, text="▶️ Run All Tests",
            command=self._run_all_tests, style='Accent.TButton')
        self.run_all_btn.pack(side=tk.LEFT, padx=2)

        self.run_selected_btn = ttk.Button(
            control_frame, text="▶️ Run Selected",
            command=self._run_selected_test)
        self.run_selected_btn.pack(side=tk.LEFT, padx=2)

        self.stop_btn = ttk.Button(
            control_frame, text="⏹️ Stop",
            command=self._stop_tests, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=2)

        self.refresh_btn = ttk.Button(
            control_frame, text="🔄 Refresh", command=self._load_tests)
        self.refresh_btn.pack(side=tk.LEFT, padx=2)

        self.clear_btn = ttk.Button(
            control_frame, text="🗑️ Clear", command=self._clear_results)
        self.clear_btn.pack(side=tk.LEFT, padx=2)

        self.export_btn = ttk.Button(
            control_frame, text="📊 Export", command=self._export_menu)
        self.export_btn.pack(side=tk.LEFT, padx=2)

        self.parallel_var = tk.BooleanVar(value=False)
        self.parallel_check = ttk.Checkbutton(
            control_frame, text="Parallel Execution",
            variable=self.parallel_var)
        self.parallel_check.pack(side=tk.LEFT, padx=10)

        self.status_label = ttk.Label(
            control_frame, text="Ready", font=('Arial', 9))
        self.status_label.pack(side=tk.RIGHT, padx=10)

    def _create_tree_and_details(self, parent: ttk.Frame):
        """Create the test tree and detailed status side by side."""
        h_paned = ttk.PanedWindow(parent, orient=tk.HORIZONTAL)
        h_paned.pack(fill=tk.BOTH, expand=True)

        # Test tree
        tree_frame = ttk.Frame(h_paned)
        h_paned.add(tree_frame, weight=2)

        ttk.Label(tree_frame, text="Tests", font=('Arial', 10, 'bold')).pack(anchor=tk.W, padx=5, pady=2)
        self.test_tree = TestTreeWidget(
            tree_frame,
            on_select=self._on_test_select,
            on_double_click=self._on_test_double_click
        )
        self.test_tree.pack(fill=tk.BOTH, expand=True)

        # Detailed status
        details_frame = ttk.Frame(h_paned)
        h_paned.add(details_frame, weight=1)

        self.detailed_status = DetailedStatusWidget(details_frame)
        self.detailed_status.pack(fill=tk.BOTH, expand=True)

    def _create_bottom_panel(self, bottom_panel: ttk.Frame):
        """Create the progress panel and log viewer."""
        self.progress_panel = DetailedProgressPanel(bottom_panel)
        self.progress_panel.pack(fill=tk.X)

        self.log_viewer = LogViewer(bottom_panel)
        self.log_viewer.pack(fill=tk.BOTH, expand=True)

    def _load_tests(self):
        """Load all test files."""
        try:
            self.test_files = self.collector.discover_tests()
            self.test_tree.populate(self.test_files)

            total_tests = self.collector.get_total_test_count(self.test_files)
            self.status_label.config(
                text=f"Loaded {len(self.test_files)} test files ({total_tests} tests)"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load tests: {e}")

    def _run_all_tests(self):
        """Run all tests."""
        if self.is_running:
            messagebox.showwarning("Warning", "Tests are already running!")
            return

        if not self.test_files:
            messagebox.showwarning("Warning", "No tests found!")
            return

        # Clear previous results
        self.parser.clear()
        self.log_viewer.clear()

        # Update UI
        self.is_running = True
        self._update_buttons()

        total_tests = self.collector.get_total_test_count(self.test_files)
        self.progress_panel.start(len(self.test_files))
        self.status_label.config(text="Running tests...")

        # Run tests in background thread
        def run_tests():
            try:
                parallel = self.parallel_var.get()
                self.runner.run_all_tests(
                    self.test_files,
                    callback=self._on_test_complete,
                    parallel=parallel
                )

                # Update UI on completion
                self.root.after(0, self._on_all_tests_complete)
            except Exception as e:
                self.root.after(0, lambda exc=e: self._on_test_error(exc))

        self.current_thread = threading.Thread(target=run_tests, daemon=True)
        self.current_thread.start()

    def _run_selected_test(self):
        """Run selected test."""
        selected = self.test_tree.get_selected_item()

        if not selected:
            messagebox.showwarning("Warning", "No test selected!")
            return

        if self.is_running:
            messagebox.showwarning("Warning", "Tests are already running!")
            return

        # Get test info
        test_file = selected['test_file']
        test_function = selected.get('function')

        # Update UI
        self.is_running = True
        self._update_buttons()
        self.progress_panel.start(1)

        # Run test in background
        def run_test():
            try:
                result = self.runner.run_single_test(
                    test_file,
                    test_function,
                    callback=self._on_test_complete
                )

                self.root.after(0, self._on_all_tests_complete)
            except Exception as e:
                self.root.after(0, lambda exc=e: self._on_test_error(exc))

        self.current_thread = threading.Thread(target=run_test, daemon=True)
        self.current_thread.start()

    def _stop_tests(self):
        """Stop running tests."""
        if not self.is_running:
            return

        response = messagebox.askyesno(
            "Confirm",
            "Are you sure you want to stop running tests?"
        )

        if response:
            self.runner.stop()
            self.status_label.config(text="Stopping tests...")

    def _on_test_complete(self, result):
        """
        Callback when a test completes.

        Args:
            result: Test result dictionary
        """
        # Update UI from main thread
        def update():
            # Add to parser
            self.parser.add_result(result)

            # Update tree
            self.test_tree.update_test_status(result)

            # Update progress
            filename = result['test_file']['filename']
            status = result['status']
            self.progress_panel.update(filename, status)

            # Update status cards
            summary = self.parser.get_summary()
            self.status_cards.update(summary)

            # Update detailed status
            category_summary = self.parser.get_category_summary()
            self.detailed_status.update(summary, category_summary)

            # Add to log viewer (errors, timeouts, AND skipped tests)
            if result['status'] in ['failed', 'error', 'timeout']:
                self.log_viewer.add_error(result)
            elif result['status'] == 'skipped' and result.get('skipped', 0) > 0:
                self.log_viewer.add_skipped(result)

        self.root.after(0, update)

    def _on_all_tests_complete(self):
        """Callback when all tests complete."""
        self.is_running = False
        self._update_buttons()

        # Update progress
        self.progress_panel.complete()

        # Get summary
        summary = self.parser.get_summary()
        passed = summary['passed']
        failed = summary['failed']
        total = summary['total_tests']

        if failed == 0:
            self.status_label.config(text=f"✅ All tests passed ({passed}/{total})")
            messagebox.showinfo("Success", f"All {total} tests passed!")
        else:
            self.status_label.config(text=f"❌ Tests completed with {failed} failures")
            messagebox.showwarning("Failures", f"{failed} out of {total} tests failed!")

    def _on_test_error(self, error):
        """Handle test execution error."""
        self.is_running = False
        self._update_buttons()
        self.progress_panel.reset()
        self.status_label.config(text="Error")

        messagebox.showerror("Error", f"Test execution failed:\n{error}")

    def _clear_results(self):
        """Clear all test results."""
        response = messagebox.askyesno(
            "Confirm",
            "Clear all test results?"
        )

        if response:
            self.parser.clear()
            self.log_viewer.clear()
            self.progress_panel.reset()
            self.status_cards.reset()
            self.detailed_status.clear()
            self._load_tests()
            self.status_label.config(text="Results cleared")

    def _on_test_select(self, item):
        """Handle test selection."""
        pass  # Could show test details here

    def _on_test_double_click(self, item):
        """Handle test double-click - run the test."""
        if not self.is_running:
            self._run_selected_test()

    def _export_menu(self):
        """Show export menu."""
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Export as JSON", command=self._export_json)
        menu.add_command(label="Export as HTML", command=self._export_html)

        # Show menu at mouse position
        menu.post(self.root.winfo_pointerx(), self.root.winfo_pointery())

    def _export_json(self):
        """Export results as JSON."""
        if not self.parser.results:
            messagebox.showwarning("Warning", "No results to export!")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="test_results.json"
        )

        if filepath:
            try:
                data = self.parser.export_json()
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)

                messagebox.showinfo("Success", f"Results exported to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed:\n{e}")

    def _export_html(self):
        """Export results as HTML."""
        if not self.parser.results:
            messagebox.showwarning("Warning", "No results to export!")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
            initialfile="test_report.html"
        )

        if filepath:
            try:
                html = self.parser.export_html()
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html)

                messagebox.showinfo("Success", f"Report exported to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Export failed:\n{e}")

    def _update_buttons(self):
        """Update button states based on running status."""
        if self.is_running:
            self.run_all_btn.config(state=tk.DISABLED)
            self.run_selected_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.refresh_btn.config(state=tk.DISABLED)
        else:
            self.run_all_btn.config(state=tk.NORMAL)
            self.run_selected_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.refresh_btn.config(state=tk.NORMAL)

    def _show_about(self):
        """Show about dialog."""
        about_text = """
🦙 CrawlLama Health Dashboard
Version 1.0.0

A comprehensive test management dashboard for CrawlLama.

Features:
• Discover all test files automatically
• Run tests individually or all at once
• Real-time progress tracking
• Detailed error logs
• Export results (JSON/HTML)

© 2025 CrawlLama Project
        """
        messagebox.showinfo("About", about_text)

    def _on_close(self):
        """Handle window close event."""
        if self.is_running:
            response = messagebox.askyesno(
                "Confirm Exit",
                "Tests are still running. Exit anyway?"
            )

            if not response:
                return

            self.runner.stop()

        self.root.destroy()

    def run(self):
        """Start the GUI main loop and bring window to foreground."""
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(500, lambda: self.root.attributes('-topmost', False))
        self.root.focus_force()
        self.root.mainloop()


if __name__ == "__main__":
    # Run the dashboard
    dashboard = HealthDashboard()
    dashboard.run()
