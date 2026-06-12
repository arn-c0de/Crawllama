"""Health Dashboard Entry Point - CrawlLama Health Monitoring System.

This script provides access to both health monitoring dashboards:
1. Live System Monitor - Real-time system metrics, alerts, and performance
2. Test Dashboard - GUI for running and managing tests

Usage:
    python health-dashboard.py              # Interactive menu
    python health-dashboard.py --monitor    # Live system monitoring
    python health-dashboard.py --tests      # Test management GUI

Live Monitor Features:
    📊 Live System Metrics - CPU, RAM, Disk, Network
    🔍 Component Health Checks - LLM, Cache, RAG, Tools
    🧠 Context Usage Tracking - Token usage, conversation history
    📈 Performance Tracking - Response Times, Throughput
    🚨 Alert System - Automatic warnings
    🎨 Rich Terminal UI - Color-coded status displays

Test Dashboard Features:
    - Automatic test discovery
    - Run individual or all tests
    - Real-time progress tracking
    - Detailed error logs
    - Export results (JSON/HTML)

Requirements:
    - Python 3.8+
    - rich, psutil (for live monitor)
    - tkinter, pytest (for test dashboard)
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Fix Windows console encoding for emoji support
EMOJI_SUPPORT = True
if sys.platform == 'win32':
    try:
        # Try to set UTF-8 encoding for Windows console
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        else:
            # Fallback for older Python versions
            import codecs
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    except Exception:
        # If encoding fix fails, disable emojis
        EMOJI_SUPPORT = False

# Emoji replacements for Windows systems without UTF-8 support
def safe_print(text):
    """Print with emoji fallback for Windows."""
    if not EMOJI_SUPPORT and sys.platform == 'win32':
        # Replace emojis with ASCII equivalents
        replacements = {
            '🚀': '[START]',
            '📊': '[MONITOR]',
            '🧪': '[TEST]',
            '❌': '[X]',
            '✅': '[OK]',
            '⚠️': '[!]',
            '🏥': '[HEALTH]',
            '👋': '[BYE]',
            '🔍': '[SEARCH]',
            '🧠': '[BRAIN]',
            '📈': '[CHART]',
            '🚨': '[ALERT]',
            '🎨': '[UI]',
        }
        for emoji, replacement in replacements.items():
            text = text.replace(emoji, replacement)
    print(text)


def check_monitor_dependencies():
    """Check if live monitor dependencies are installed."""
    missing = []

    try:
        import rich  # noqa: F401 - availability probe
    except ImportError:
        missing.append("rich")

    try:
        import psutil  # noqa: F401 - availability probe
    except ImportError:
        missing.append("psutil")

    if missing:
        safe_print("❌ Missing dependencies for Live Monitor:")
        for dep in missing:
            print(f"   - {dep}")
        print("\nInstall with: pip install rich psutil")
        return False

    return True


def check_test_dependencies():
    """Check if test dashboard dependencies are installed."""
    missing = []

    try:
        import tkinter  # noqa: F401 - availability probe
    except ImportError:
        missing.append("tkinter")

    try:
        import pytest  # noqa: F401 - availability probe
    except ImportError:
        missing.append("pytest")

    if missing:
        safe_print("❌ Missing dependencies for Test Dashboard:")
        for dep in missing:
            print(f"   - {dep}")

        # tkinter is NOT a pip package — it ships with the OS Python build and
        # must be installed via the system package manager. pytest IS a pip
        # package. Print the right instructions for whatever is actually missing.
        if "tkinter" in missing:
            print("\ntkinter is a system package (it cannot be installed with pip):")
            if sys.platform.startswith("linux"):
                print("   Debian/Ubuntu: sudo apt install python3-tk")
                print("   Fedora/RHEL:   sudo dnf install python3-tkinter")
                print("   Arch:          sudo pacman -S tk")
            elif sys.platform == "darwin":
                print("   macOS (Homebrew): brew install python-tk")
            else:
                print("   Install the Tk/tkinter package for your OS Python.")
            print("   Note: after installing, recreate the venv so it picks up tkinter:")
            print("         rm -rf venv && ./setup.sh")

        pip_missing = [d for d in missing if d != "tkinter"]
        if pip_missing:
            print(f"\nInstall with: pip install {' '.join(pip_missing)}")
        return False

    return True


def launch_live_monitor():
    """Launch the live system monitoring dashboard."""
    safe_print("\n🚀 Launching Live System Monitor...")
    print("Press Ctrl+C to exit\n")

    try:
        from core.health import RichHealthDashboard

        dashboard = RichHealthDashboard(project_root=project_root)
        dashboard.start()

    except KeyboardInterrupt:
        safe_print("\n\n✅ Monitor stopped by user")
    except Exception as e:
        safe_print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


def launch_test_dashboard():
    """Launch the test management GUI."""
    safe_print("\n🚀 Launching Test Dashboard...")
    print("Close the window or press Ctrl+C to exit\n")

    try:
        from core.health import HealthDashboard

        # Check if tests directory exists
        tests_dir = project_root / "tests"
        if not tests_dir.exists():
            safe_print("⚠️  Warning: 'tests' directory not found!")
            print(f"   Expected location: {tests_dir}\n")

        dashboard = HealthDashboard()
        dashboard.run()

    except KeyboardInterrupt:
        print("\n\nDashboard closed by user")
    except Exception as e:
        safe_print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


def show_menu():
    """Show interactive menu for dashboard selection."""
    print("\n" + "=" * 60)
    safe_print("🏥 CrawlLama Health Monitoring System")
    print("=" * 60)
    print("\nAvailable Dashboards:\n")
    safe_print("  1. 📊 Live System Monitor")
    print("     Real-time monitoring with system metrics, alerts,")
    print("     component health checks, and performance tracking\n")
    safe_print("  2. 🧪 Test Dashboard")
    print("     GUI for running and managing project tests\n")
    safe_print("  3. ❌ Exit\n")

    while True:
        try:
            safe_print("Select dashboard (1-3): ")
            choice = sys.stdin.readline().strip()

            if choice == "1":
                if not check_monitor_dependencies():
                    safe_print("\n❌ Cannot launch Live Monitor - missing dependencies")
                    return 1
                return launch_live_monitor()

            elif choice == "2":
                if not check_test_dependencies():
                    safe_print("\n❌ Cannot launch Test Dashboard - missing dependencies")
                    return 1
                return launch_test_dashboard()

            elif choice == "3":
                safe_print("\n👋 Goodbye!")
                return 0

            else:
                safe_print("⚠️  Invalid choice. Please enter 1, 2, or 3.")

        except KeyboardInterrupt:
            safe_print("\n\n👋 Goodbye!")
            return 0
        except EOFError:
            safe_print("\n\n👋 Goodbye!")
            return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="CrawlLama Health Monitoring System",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--monitor", "-m",
        action="store_true",
        help="Launch live system monitoring dashboard"
    )
    parser.add_argument(
        "--tests", "-t",
        action="store_true",
        help="Launch test management GUI"
    )
    
    args = parser.parse_args()
    
    # Direct launch modes
    if args.monitor:
        if not check_monitor_dependencies():
            return 1
        return launch_live_monitor()
    
    if args.tests:
        if not check_test_dependencies():
            return 1
        return launch_test_dashboard()
    
    # Interactive menu
    return show_menu()



if __name__ == "__main__":
    sys.exit(main())

