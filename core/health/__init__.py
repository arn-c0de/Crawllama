"""Health Dashboard Module for CrawlLama Test Management.

This module provides a Tkinter-based GUI for running and monitoring all tests
in the CrawlLama project. It allows users to:
- Discover all test files automatically
- Run all tests or individual tests
- View live test execution status
- See detailed error logs
- Export test results
"""

from .dashboard import HealthDashboard
from .test_runner import TestRunner
from .test_collector import TestCollector
from .result_parser import ResultParser
from .theme import DarkTheme

__all__ = [
    'HealthDashboard',
    'TestRunner',
    'TestCollector',
    'ResultParser',
    'DarkTheme'
]

__version__ = '1.0.0'
