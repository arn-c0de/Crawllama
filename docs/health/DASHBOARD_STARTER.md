# 🦙 Health Dashboard - Quick Start Guide

---

📚 **Navigation:** [🏠 Home](../../README.md) | [📖 Docs](../README.md) | [🏥 Health Monitoring](HEALTH_MONITORING.md) | [📊 Dashboard](HEALTH_DASHBOARD.md) | [⚙️ Features](HEALTH_FEATURES.md)

---

Simple starter scripts for the Health Dashboard.

## 🚀 Quick Start

### Windows
Double-click on:
```
start-dashboard.bat
```

Or in PowerShell/CMD:
```cmd
.\start-dashboard.bat
```

### Linux/Mac
```bash
chmod +x start-dashboard.sh  # Make executable (once)
./start-dashboard.sh
```

---

## 📋 What the Scripts Do

1. ✅ Check if venv exists
2. ✅ Automatically activate venv
3. ✅ Start Health Dashboard
4. ✅ Error handling if something goes wrong

---

## 🔧 Initial Setup

If venv doesn't exist yet:

### Windows
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Linux/Mac
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 📝 Manual Execution

If you don't want to use the scripts:

### Windows (PowerShell/CMD)
```cmd
cd C:\Artificial-Intelligent\Crawllama
venv\Scripts\activate
python health-dashboard.py
```

### Linux/Mac (Bash)
```bash
cd /path/to/Crawllama
source venv/bin/activate
python health-dashboard.py
```

---

## ⚙️ Available Dashboard Versions

### 1. Standard Dashboard (recommended)
```bash
python health-dashboard.py
```
- Automatic detection of pytest-json-report
- Fallback to text parsing if plugin missing
- Dark mode
- All features

### 2. Simple Dashboard (Text-Only)
```bash
python test-dash-simple.py
```
- Text parsing only (no pytest-json-report needed)
- Same features
- Dark mode
- For when JSON report causes issues

---

## 🐛 Troubleshooting

### "Virtual environment not found"
```bash
# Recreate venv
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
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
# Debug mode
python health-dashboard.py --verbose

# Or check dependencies
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

# Check if test_*.py files exist
Get-ChildItem tests\test_*.py

# Linux/Mac
ls tests/
ls tests/test_*.py
```

---

## 📊 After Starting

The dashboard shows:
- 📁 All test_*.py files in `tests/` folder
- ✅ Status: PASSED, FAILED, SKIPPED, ERROR
- ⏱️ Execution time per test
- 📝 Detailed error logs
- 📊 Export as JSON/HTML

### Controls

1. **Load tests:** Automatic on start
2. **Run all tests:** Button "▶️ Run All Tests"
3. **Single test:** Double-click on test in TreeView
4. **Parallel execution:** Enable checkbox "Parallel Execution"
5. **Export:** Button "📊 Export" → JSON or HTML

---

## 🎨 Dark Mode

The dashboard automatically uses a VS Code-inspired dark theme:
- Dark background (#1e1e1e)
- Green PASSED tests (#4ec9b0)
- Red FAILED tests (#f48771)
- Blue RUNNING tests (#569cd6)

---

## 🔄 Updates

After git pull:
```bash
# Windows
.\start-dashboard.bat

# Linux/Mac
./start-dashboard.sh
```

The scripts automatically activate the venv!

---

## 💡 Tips

### Quick Workflow
1. After code changes
2. Open dashboard (`start-dashboard.bat`)
3. Click "Run All Tests"
4. Check errors in log viewer
5. Fix code, dashboard stays open
6. Click "Run All Tests" again

### Test Cleanup
```bash
# Remove old/broken tests
python cleanup_old_tests.py
```

### Keyboard Shortcuts
- **Double-click** on test → Run
- **Ctrl+C** in terminal → Close dashboard

---

## 📚 Further Help

- **Full docs:** `HEALTH_DASHBOARD.md`
- **Troubleshooting:** `core/health/TROUBLESHOOTING.md`
- **Test cleanup:** `TEST_CLEANUP_RECOMMENDATIONS.md`

---

## ✅ Checklist

After project setup:
- [ ] venv created and activated
- [ ] pytest installed (`pip install pytest`)
- [ ] start-dashboard.bat/.sh executable
- [ ] Dashboard starts without errors
- [ ] Tests are found
- [ ] Tests run successfully

Everything green? Then you're ready! 🎉
