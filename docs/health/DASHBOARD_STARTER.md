# Health Dashboard - Quick Start Guide

---

 **Navigation:** [Home](../../README.md) | [Docs](../README.md) | [Health Monitoring](HEALTH_MONITORING.md) | [Dashboard](HEALTH_DASHBOARD.md) | [Features](HEALTH_FEATURES.md)

---

Simple starter scripts for the Health Dashboard.

## Quick Start

### Windows
Double-click on:
```
health-dashboard.bat
```

Or in PowerShell/CMD:
```cmd
.\health-dashboard.bat
```

### Linux/Mac
```bash
chmod +x health-dashboard.sh # Make executable (once)
./health-dashboard.sh
```

---

## What the Scripts Do

1. Check that `uv` is installed
2. Sync/provision the `.venv` via `uv run`
3. Start Health Dashboard
4. Error handling if something goes wrong

---

## Initial Setup

If the environment doesn't exist yet, run the setup script (it provisions the `.venv` with `uv`):

### Windows
```cmd
setup.bat
```

### Linux/Mac
```bash
./setup.sh
```

---

## Manual Execution

If you don't want to use the scripts:

### Windows (PowerShell/CMD)
```cmd
cd C:\path\to\Crawllama
uv run python health-dashboard.py
```

### Linux/Mac (Bash)
```bash
cd /path/to/Crawllama
uv run python health-dashboard.py
```

---

## Available Dashboard Versions

### Standard Dashboard
```bash
python health-dashboard.py
```
- Automatic detection of pytest-json-report
- Fallback to text parsing if plugin missing
- Dark mode
- All features

---

## Troubleshooting

### "Virtual environment not found"
```bash
# Re-provision the .venv with uv

# Windows
setup.bat

# Linux/Mac
./setup.sh
```

### "tkinter not found"
**Windows/macOS:**
- Reinstall Python with tcl/tk support

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

### Dashboard won't start
```bash
# Check dependencies
# Windows (PowerShell)
pip show pytest

# Linux/Mac
pip list | grep pytest

# Test tkinter
python -c "import tkinter; print('tkinter OK')"
```

### Tests not found
```bash
# Windows (PowerShell)
Get-ChildItem tests\

# Check if test_*.py files exist (tests live in subdirectories like tests/unit/)
Get-ChildItem tests\ -Recurse -Filter test_*.py

# Linux/Mac
ls tests/
ls tests/*/test_*.py
```

---

## After Starting

The dashboard shows:
- All test_*.py files in `tests/` folder
- Status: PASSED, FAILED, SKIPPED, ERROR
- Execution time per test
- Detailed error logs
- Export as JSON/HTML

### Controls

1. **Load tests:** Automatic on start
2. **Run all tests:** Button " Run All Tests"
3. **Single test:** Double-click on test in TreeView
4. **Parallel execution:** Enable checkbox "Parallel Execution"
5. **Export:** Button " Export" → JSON or HTML

---

## Dark Mode

The dashboard automatically uses a VS Code-inspired dark theme:
- Dark background (#1e1e1e)
- Green PASSED tests (#4ec9b0)
- Red FAILED tests (#f48771)
- Blue RUNNING tests (#569cd6)

---

## Updates

After git pull:
```bash
# Windows
.\health-dashboard.bat

# Linux/Mac
./health-dashboard.sh
```

The scripts automatically sync the `.venv` via `uv`!

---

## Tips

### Quick Workflow
1. After code changes
2. Open dashboard (`health-dashboard.bat`)
3. Click "Run All Tests"
4. Check errors in log viewer
5. Fix code, dashboard stays open
6. Click "Run All Tests" again

### Keyboard Shortcuts
- **Double-click** on test → Run
- **Ctrl+C** in terminal → Close dashboard

---

## Further Help

- **Full docs:** `HEALTH_DASHBOARD.md`

---

## Checklist

After project setup:
- [] venv created and activated
- [] pytest installed (`pip install pytest`)
- [] health-dashboard.bat/.sh executable
- [] Dashboard starts without errors
- [] Tests are found
- [] Tests run successfully

Everything green? Then you're ready! 
