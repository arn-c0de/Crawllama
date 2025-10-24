"""Health Dashboard Entry Point - CrawlLama Test Management.

This script launches the Health Dashboard GUI for managing and running
all tests in the CrawlLama project.

Usage:
    python test-dash.py

Features:
    - Automatic test discovery
    - Run individual or all tests
    - Real-time progress tracking
    - Detailed error logs
    - Export results (JSON/HTML)

Requirements:
    - Python 3.8+
    - tkinter (usually included with Python)
    - pytest with pytest-json-report plugin
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.health import HealthDashboard


def check_dependencies():
    """Check if required dependencies are installed."""
    missing = []

    try:
        import tkinter
    except ImportError:
        missing.append("tkinter")

    try:
        import pytest
    except ImportError:
        missing.append("pytest")

    if missing:
        print("❌ Missing dependencies:")
        for dep in missing:
            print(f"   - {dep}")
        print("\nPlease install missing dependencies:")
        print("   pip install pytest pytest-json-report")
        print("\nNote: tkinter usually comes with Python.")
        print("      If missing, install python3-tk (Linux) or reinstall Python with tcl/tk support.")
        return False

    return True


def main():
    """Main entry point."""
    print("=" * 60)
    print("🦙 CrawlLama Health Dashboard")
    print("=" * 60)
    print()

    # Check dependencies
    print("Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)

    print("✅ All dependencies available")
    print()

    # Check if tests directory exists
    tests_dir = project_root / "tests"
    if not tests_dir.exists():
        print("⚠️  Warning: 'tests' directory not found!")
        print(f"   Expected location: {tests_dir}")
        print()

    # Launch dashboard
    print("Launching Health Dashboard...")
    print("Close the window or press Ctrl+C to exit")
    print()

    try:
        dashboard = HealthDashboard()
        dashboard.run()
    except KeyboardInterrupt:
        print("\n\nDashboard closed by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\nThank you for using CrawlLama Health Dashboard!")


if __name__ == "__main__":
    main()
