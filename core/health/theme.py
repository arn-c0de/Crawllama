"""Dark Mode Theme Configuration for Health Dashboard."""

import tkinter as tk
from tkinter import ttk


class DarkTheme:
    """Dark mode color scheme and styling."""

    # Background colors
    BG_DARK = '#1e1e1e'
    BG_MEDIUM = '#252526'
    BG_LIGHT = '#2d2d30'
    BG_LIGHTER = '#3e3e42'

    # Text colors
    TEXT_PRIMARY = '#e4e4e4'
    TEXT_SECONDARY = '#cccccc'
    TEXT_DIM = '#858585'

    # Accent colors
    ACCENT_BLUE = '#007acc'
    ACCENT_GREEN = '#4ec9b0'
    ACCENT_RED = '#f48771'
    ACCENT_YELLOW = '#dcdcaa'
    ACCENT_ORANGE = '#ce9178'

    # Status colors
    STATUS_PASSED = '#4ec9b0'
    STATUS_FAILED = '#f48771'
    STATUS_SKIPPED = '#858585'
    STATUS_RUNNING = '#569cd6'
    STATUS_ERROR = '#f48771'
    STATUS_TIMEOUT = '#dcdcaa'

    # Border colors
    BORDER = '#3e3e42'
    BORDER_LIGHT = '#555555'

    # Widget colors
    BUTTON_BG = '#3e3e42'
    BUTTON_FG = '#cccccc'
    BUTTON_HOVER = '#505050'
    BUTTON_ACTIVE = '#569cd6'

    ENTRY_BG = '#3c3c3c'
    ENTRY_FG = '#cccccc'

    TREEVIEW_BG = '#252526'
    TREEVIEW_FG = '#cccccc'
    TREEVIEW_SELECT = '#094771'

    @classmethod
    def apply_to_root(cls, root: tk.Tk):
        """
        Apply dark theme to root window.

        Args:
            root: Root Tk window
        """
        root.configure(bg=cls.BG_DARK)

        style = ttk.Style()
        style.theme_use('clam')

        cls._style_frames_and_labels(style)
        cls._style_buttons(style)
        cls._style_treeview(style)
        cls._style_inputs(style)
        cls._style_containers_and_bars(style)
        cls._configure_menu_colors(root)

    @classmethod
    def _style_frames_and_labels(cls, style: ttk.Style):
        """Style frames, labels, and label frames."""
        style.configure('TFrame', background=cls.BG_DARK)

        style.configure('TLabel',
                       background=cls.BG_DARK,
                       foreground=cls.TEXT_PRIMARY)

        style.configure('TLabelframe',
                       background=cls.BG_DARK,
                       foreground=cls.TEXT_PRIMARY,
                       bordercolor=cls.BORDER,
                       lightcolor=cls.BG_DARK,
                       darkcolor=cls.BG_DARK)

        style.configure('TLabelframe.Label',
                       background=cls.BG_DARK,
                       foreground=cls.TEXT_PRIMARY)

    @classmethod
    def _style_buttons(cls, style: ttk.Style):
        """Style standard and accent buttons."""
        style.configure('TButton',
                       background=cls.BUTTON_BG,
                       foreground=cls.BUTTON_FG,
                       bordercolor=cls.BORDER,
                       lightcolor=cls.BUTTON_BG,
                       darkcolor=cls.BUTTON_BG,
                       borderwidth=1,
                       focuscolor=cls.ACCENT_BLUE,
                       relief=tk.FLAT)

        style.map('TButton',
                 background=[('active', cls.BUTTON_HOVER),
                           ('pressed', cls.BUTTON_ACTIVE)],
                 foreground=[('active', cls.TEXT_PRIMARY)])

        style.configure('Accent.TButton',
                       background=cls.ACCENT_BLUE,
                       foreground='white',
                       bordercolor=cls.ACCENT_BLUE)

        style.map('Accent.TButton',
                 background=[('active', '#005a9e'),
                           ('pressed', '#004578')],
                 foreground=[('active', 'white')])

    @classmethod
    def _style_treeview(cls, style: ttk.Style):
        """Style the treeview and its headings."""
        style.configure('Treeview',
                       background=cls.TREEVIEW_BG,
                       foreground=cls.TREEVIEW_FG,
                       fieldbackground=cls.TREEVIEW_BG,
                       bordercolor=cls.BORDER,
                       borderwidth=1)

        style.configure('Treeview.Heading',
                       background=cls.BG_LIGHTER,
                       foreground=cls.TEXT_PRIMARY,
                       bordercolor=cls.BORDER,
                       relief=tk.FLAT)

        style.map('Treeview',
                 background=[('selected', cls.TREEVIEW_SELECT)],
                 foreground=[('selected', cls.TEXT_PRIMARY)])

        style.map('Treeview.Heading',
                 background=[('active', cls.BG_LIGHT)])

    @classmethod
    def _style_inputs(cls, style: ttk.Style):
        """Style checkbuttons and entry fields."""
        style.configure('TCheckbutton',
                       background=cls.BG_DARK,
                       foreground=cls.TEXT_PRIMARY)

        style.configure('TEntry',
                       fieldbackground=cls.ENTRY_BG,
                       foreground=cls.ENTRY_FG,
                       bordercolor=cls.BORDER,
                       insertcolor=cls.TEXT_PRIMARY)

    @classmethod
    def _style_containers_and_bars(cls, style: ttk.Style):
        """Style paned windows, progress bars, and scrollbars."""
        style.configure('TPanedwindow',
                       background=cls.BG_DARK)

        style.configure('Sash',
                       sashthickness=4,
                       background=cls.BORDER)

        style.configure('TProgressbar',
                       background=cls.ACCENT_BLUE,
                       troughcolor=cls.BG_LIGHTER,
                       bordercolor=cls.BORDER,
                       lightcolor=cls.ACCENT_BLUE,
                       darkcolor=cls.ACCENT_BLUE)

        style.configure('TScrollbar',
                       background=cls.BG_LIGHTER,
                       troughcolor=cls.BG_DARK,
                       bordercolor=cls.BORDER,
                       arrowcolor=cls.TEXT_PRIMARY)

        style.map('TScrollbar',
                 background=[('active', cls.BG_LIGHT)])

    @classmethod
    def _configure_menu_colors(cls, root: tk.Tk):
        """Set default colors for tk.Menu widgets."""
        root.option_add('*Menu.background', cls.BG_MEDIUM)
        root.option_add('*Menu.foreground', cls.TEXT_PRIMARY)
        root.option_add('*Menu.activeBackground', cls.TREEVIEW_SELECT)
        root.option_add('*Menu.activeForeground', cls.TEXT_PRIMARY)

    @classmethod
    def create_card_frame(cls, parent, **kwargs) -> tk.Frame:
        """
        Create a styled card frame.

        Args:
            parent: Parent widget
            **kwargs: Additional frame options

        Returns:
            Styled frame
        """
        default_options = {
            'bg': cls.BG_MEDIUM,
            'relief': tk.FLAT,
            'borderwidth': 1,
            'highlightbackground': cls.BORDER,
            'highlightthickness': 1
        }
        default_options.update(kwargs)

        return tk.Frame(parent, **default_options)

    @classmethod
    def create_text_widget(cls, parent, **kwargs) -> tk.Text:
        """
        Create a styled text widget.

        Args:
            parent: Parent widget
            **kwargs: Additional text options

        Returns:
            Styled text widget
        """
        default_options = {
            'bg': cls.BG_MEDIUM,
            'fg': cls.TEXT_PRIMARY,
            'insertbackground': cls.TEXT_PRIMARY,
            'selectbackground': cls.TREEVIEW_SELECT,
            'selectforeground': cls.TEXT_PRIMARY,
            'relief': tk.FLAT,
            'borderwidth': 0
        }
        default_options.update(kwargs)

        return tk.Text(parent, **default_options)


# Icon mappings with colors
ICONS = {
    'pending': ('⏸️', DarkTheme.TEXT_DIM),
    'running': ('🔄', DarkTheme.STATUS_RUNNING),
    'passed': ('✅', DarkTheme.STATUS_PASSED),
    'failed': ('❌', DarkTheme.STATUS_FAILED),
    'skipped': ('⏭️', DarkTheme.STATUS_SKIPPED),
    'timeout': ('⏱️', DarkTheme.STATUS_TIMEOUT),
    'error': ('⚠️', DarkTheme.STATUS_ERROR),
    'folder': ('📁', DarkTheme.TEXT_SECONDARY)
}
