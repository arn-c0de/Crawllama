"""Test Tree Widget - Hierarchical display of test files and functions."""

import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from typing import Any

# Add parent directory to path for theme import
sys.path.insert(0, str(Path(__file__).parent.parent))
from theme import DarkTheme


class TestTreeWidget(ttk.Frame):
    """TreeView widget for displaying test hierarchy."""

    # Status icons
    ICONS = {
        'pending': '⏸️',
        'running': '🔄',
        'passed': '✅',
        'failed': '❌',
        'skipped': '⏭️',
        'timeout': '⏱️',
        'error': '⚠️',
        'folder': '📁'
    }

    def __init__(self, parent, on_select: Callable | None = None,
                 on_double_click: Callable | None = None):
        """
        Initialize TestTreeWidget.

        Args:
            parent: Parent widget
            on_select: Callback when item is selected
            on_double_click: Callback when item is double-clicked
        """
        super().__init__(parent)

        self.on_select = on_select
        self.on_double_click = on_double_click
        self.test_items = {}  # Maps test IDs to tree items

        self._create_widgets()

    def _create_widgets(self):
        """Create tree view and scrollbars."""
        # Create tree view
        columns = ('status', 'time', 'category')
        self.tree = ttk.Treeview(
            self,
            columns=columns,
            show='tree headings',
            selectmode='browse'
        )

        # Configure columns
        self.tree.heading('#0', text='Test', anchor=tk.W)
        self.tree.heading('status', text='Status', anchor=tk.CENTER)
        self.tree.heading('time', text='Time', anchor=tk.E)
        self.tree.heading('category', text='Category', anchor=tk.CENTER)

        self.tree.column('#0', width=400, minwidth=200)
        self.tree.column('status', width=120, minwidth=80)
        self.tree.column('time', width=80, minwidth=60)
        self.tree.column('category', width=100, minwidth=80)

        # Scrollbars
        vsb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Layout
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Bindings
        self.tree.bind('<<TreeviewSelect>>', self._on_select)
        self.tree.bind('<Double-1>', self._on_double_click)

        # Configure tags for colors
        self.tree.tag_configure('passed', foreground=DarkTheme.STATUS_PASSED)
        self.tree.tag_configure('failed', foreground=DarkTheme.STATUS_FAILED)
        self.tree.tag_configure('running', foreground=DarkTheme.STATUS_RUNNING)
        self.tree.tag_configure('skipped', foreground=DarkTheme.STATUS_SKIPPED)
        self.tree.tag_configure('error', foreground=DarkTheme.STATUS_ERROR)
        self.tree.tag_configure('timeout', foreground=DarkTheme.STATUS_TIMEOUT)

    def populate(self, test_files: list[dict[str, Any]]):
        """
        Populate tree with test files.

        Args:
            test_files: List of test file information
        """
        # Clear existing items
        self.tree.delete(*self.tree.get_children())
        self.test_items = {}

        # Group by category
        categories = {}
        for test_file in test_files:
            category = test_file.get('category', 'other')
            if category not in categories:
                categories[category] = []
            categories[category].append(test_file)

        # Add category folders and test files
        for category, files in sorted(categories.items()):
            # Add category folder
            category_id = self.tree.insert(
                '',
                'end',
                text=f"{self.ICONS['folder']} {category.upper()}",
                values=('', '', category),
                tags=(category,)
            )

            # Add test files
            for test_file in files:
                self._add_test_file(category_id, test_file)

    def _add_test_file(self, parent: str, test_file: dict[str, Any]) -> str:
        """Add a test file to the tree."""
        filename = test_file['filename']
        file_id = self.tree.insert(
            parent,
            'end',
            text=f"{self.ICONS['pending']} {filename}",
            values=(f"{self.ICONS['pending']} Pending", '---', test_file.get('category', '')),
            tags=('pending',)
        )

        # Store mapping
        self.test_items[test_file['file']] = {
            'tree_id': file_id,
            'test_file': test_file,
            'function_items': {}
        }

        # Add test functions
        for func in test_file.get('functions', []):
            func_id = self.tree.insert(
                file_id,
                'end',
                text=f"  {self.ICONS['pending']} {func['name']}",
                values=(f"{self.ICONS['pending']} Pending", '---', ''),
                tags=('pending',)
            )

            self.test_items[test_file['file']]['function_items'][func['name']] = func_id

        return file_id

    def update_test_status(self, result: dict[str, Any]):
        """
        Update status of a test file.

        Args:
            result: Test result dictionary
        """
        filepath = result['test_file']['file']

        if filepath not in self.test_items:
            return

        item = self.test_items[filepath]
        tree_id = item['tree_id']
        status = result['status']
        duration = result.get('duration', 0)

        # Update file item
        icon = self.ICONS.get(status, '❓')
        self.tree.item(
            tree_id,
            text=f"{icon} {result['test_file']['filename']}",
            values=(
                f"{icon} {status.upper()}",
                f"{duration:.1f}s",
                result['test_file'].get('category', '')
            ),
            tags=(status,)
        )

        # Update function items
        for detail in result.get('details', []):
            func_name = detail['name']
            if func_name in item['function_items']:
                func_id = item['function_items'][func_name]
                func_status = detail['outcome']
                func_duration = detail.get('duration', 0)
                func_icon = self.ICONS.get(func_status, '❓')

                self.tree.item(
                    func_id,
                    text=f"  {func_icon} {func_name}",
                    values=(
                        f"{func_icon} {func_status.upper()}",
                        f"{func_duration:.2f}s",
                        ''
                    ),
                    tags=(func_status,)
                )

        # Expand file item to show functions
        self.tree.item(tree_id, open=True)

    def update_test_running(self, filepath: str):
        """
        Mark a test as currently running.

        Args:
            filepath: Path to test file
        """
        if filepath not in self.test_items:
            return

        item = self.test_items[filepath]
        tree_id = item['tree_id']

        icon = self.ICONS['running']
        self.tree.item(
            tree_id,
            text=f"{icon} {item['test_file']['filename']}",
            values=(f"{icon} RUNNING", '...', item['test_file'].get('category', '')),
            tags=('running',)
        )

    def get_selected_item(self) -> dict[str, Any] | None:
        """
        Get the currently selected item.

        Returns:
            Dictionary with item information or None
        """
        selection = self.tree.selection()
        if not selection:
            return None

        item_id = selection[0]

        # Check if it's a test file
        for filepath, item in self.test_items.items():
            if item['tree_id'] == item_id:
                return {
                    'type': 'file',
                    'filepath': filepath,
                    'test_file': item['test_file']
                }

            # Check if it's a function
            for func_name, func_id in item['function_items'].items():
                if func_id == item_id:
                    return {
                        'type': 'function',
                        'filepath': filepath,
                        'function': func_name,
                        'test_file': item['test_file']
                    }

        return None

    def expand_all(self):
        """Expand all tree items."""
        def expand_children(item):
            self.tree.item(item, open=True)
            for child in self.tree.get_children(item):
                expand_children(child)

        for item in self.tree.get_children():
            expand_children(item)

    def collapse_all(self):
        """Collapse all tree items."""
        def collapse_children(item):
            self.tree.item(item, open=False)
            for child in self.tree.get_children(item):
                collapse_children(child)

        for item in self.tree.get_children():
            collapse_children(item)

    def _on_select(self, event):
        """Handle selection event."""
        if self.on_select:
            item = self.get_selected_item()
            if item:
                self.on_select(item)

    def _on_double_click(self, event):
        """Handle double-click event."""
        if self.on_double_click:
            item = self.get_selected_item()
            if item:
                self.on_double_click(item)

    def clear(self):
        """Clear all items from tree."""
        self.tree.delete(*self.tree.get_children())
        self.test_items = {}


if __name__ == "__main__":
    # Test the widget
    root = tk.Tk()
    root.title("Test Tree Widget")
    root.geometry("800x600")

    tree = TestTreeWidget(root)
    tree.pack(fill=tk.BOTH, expand=True)

    # Add some test data
    test_files = [
        {
            'file': '/path/to/test_example.py',
            'filename': 'test_example.py',
            'category': 'unit',
            'functions': [
                {'name': 'test_function_1', 'docstring': 'Test 1'},
                {'name': 'test_function_2', 'docstring': 'Test 2'}
            ]
        }
    ]

    tree.populate(test_files)

    root.mainloop()
