# CrawlLama Health Dashboard

---

 **Navigation:** [Home](../../README.md) | [Docs](../README.md) | [Health Monitoring](HEALTH_MONITORING.md) | [Features](HEALTH_FEATURES.md)

---

A comprehensive Tkinter-based test management dashboard for CrawlLama.

## Features

 **Automatic Test Discovery** - Finds all `test_*.py` files in the `tests/` folder
 **Single & Batch Execution** - Run tests individually or all at once
 **Live Progress Tracking** - Real-time status during execution
 **Detailed Error Logs** - Complete tracebacks and error details
 **Categorization** - Tests grouped by type (Unit, Integration, OSINT, etc.)
 **Export Functions** - Export results as JSON or HTML
 **Parallel Execution** - Optionally run tests in parallel

## Installation

### Requirements

```bash
# Basic requirements
pip install pytest pytest-json-report pytest-timeout

# Optional for clipboard support
pip install pyperclip
```

### Tkinter Installation

**Windows & macOS:** Tkinter is usually already installed with Python.

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# Fedora
sudo dnf install python3-tkinter

# Arch
sudo pacman -S tk
```

## Usage

### Starting the Dashboard

```bash
python health-dashboard.py
```

This opens the Health Dashboard GUI.

### Controls

#### 1. **Test Overview**
- Left side: Hierarchical view of all tests
- Tests are grouped by categories:
 - UNIT - Unit tests
 - INTEGRATION - Integration tests
 - OSINT - OSINT tests
 - ROBUSTNESS - Robustness tests
 - MULTIHOP - Multi-hop reasoning tests

#### 2. **Status Cards** (Top)
- **Passed** - Number of passed tests
- **Failed** - Number of failed tests
- **Skipped** - Number of skipped tests
- **Duration** - Total duration

#### 3. **Control Buttons**
- ** Run All Tests** - Run all tests
- ** Run Selected** - Run selected test
- ** Stop** - Stop running tests
- ** Refresh** - Reload test list
- ** Clear** - Clear results
- ** Export** - Export results

#### 4. **Progress Panel**
Shows live updates during test execution:
- Progress bar
- Current test
- Passed/Failed/Skipped counts

#### 5. **Error Log Viewer** (Bottom)
Shows detailed error information:
- Test file and function
- Error messages
- Tracebacks
- ** Copy** - Copy to clipboard
- ** Export** - Save as text file

### Keyboard Shortcuts

- **Double-click on test** → Run test
- **Menu → Tests → Run All** → Run all tests

### Export Functions

#### JSON Export
```
File → Export Results (JSON)
```
Exports complete test results in JSON format:
```json
{
 "summary": {
 "total_tests": 15,
 "passed": 12,
 "failed": 2,
 "skipped": 1,
 "pass_rate": 80.0,
 "duration": 15.8
 },
 "results": [...],
 "failed_tests": [...],
 "category_summary": {...}
}
```

#### HTML Report
```
File → Export Results (HTML)
```
Generates a clear HTML report with:
- Summary
- Status cards
- Detailed test list

## Architecture

```
core/health/
├── __init__.py # Module init
├── dashboard.py # Main GUI
├── test_collector.py # Test discovery
├── test_runner.py # Test execution
├── result_parser.py # Result parsing
└── widgets/ # Custom widgets
 ├── test_tree.py # TreeView for tests
 ├── status_card.py # Status cards
 ├── progress_panel.py # Progress bar
 └── log_viewer.py # Error log viewer
```

## Workflow

1. **Test Discovery**
 ```
 TestCollector → Finds all test_*.py → Parses functions
 ```

2. **Test Execution**
 ```
 TestRunner → pytest subprocess → JSON Report → Result Parsing
 ```

3. **UI Updates**
 ```
 Callback → Update TreeView → Update Status Cards → Update Logs
 ```

## Categorization

Tests are automatically categorized based on filenames: | Category | Keywords | Examples |
|-----------|----------|-----------|
| Unit | cache, llm_client, rate_limiter | test_cache.py |
| Integration | integration, web_search | test_integration.py |
| OSINT | osint, ddgs | test_osint.py |
| Robustness | robustness, error_simulation | test_robustness_simple.py |
| Multihop | multihop_reasoning | test_multihop_reasoning.py |

## Parallel Execution

Enable "Parallel Execution" checkbox for faster test execution:
- Default: 4 parallel workers
- Note: Some tests might have resource conflicts

## Troubleshooting

### "No tests found"
```bash
# Ensure tests/ directory exists
# Windows (PowerShell)
Get-ChildItem tests\

# Linux/Mac
ls tests/

# Test discovery manually
python -c "from core.health import TestCollector; print(TestCollector().discover_tests())"
```

### "pytest not found"
```bash
pip install pytest pytest-json-report
```

### Tkinter ImportError
```bash
# Windows/macOS: Reinstall Python with tcl/tk support
# Linux: Install python3-tk (see Installation above)
```

### Tests hang
- Press **Stop** button
- Check test code for infinite loops
- Enable timeout: Tests have automatic 5min timeout

## Best Practices

1. **After Each Patch**
 - Open dashboard
 - Run "Run All Tests"
 - Analyze errors in log viewer

2. **Before Commits**
 - Make all tests green
 - Export HTML report
 - Mention report in commit message

3. **CI/CD Integration**
 ```bash
 # Use dashboard for CI/CD reports too
 pytest --json-report --json-report-file=results.json
 # Load results.json into dashboard
 ```

## Example Output

```
═══════════════════════════════════════════════
 CrawlLama Health Dashboard
═══════════════════════════════════════════════

 Checking dependencies...
 All dependencies available

Launching Health Dashboard...
Close the window or press Ctrl+C to exit

[Dashboard GUI opens]

═══════════════════════════════════════════════
Test Results
═══════════════════════════════════════════════
Total Tests: 15
Passed: 12
Failed: 2
Skipped: 1
Pass Rate: 80.0%
Duration: 15.8s
═══════════════════════════════════════════════
```

## Extensions

The dashboard can be easily extended:

1. **New Categories** → Adjust `test_collector.py`
2. **Custom Reports** → Extend `result_parser.py`
3. **New Widgets** → Add to `widgets/`
4. **CI/CD Integration** → Use JSON export

## Support

If you have problems:
1. Check `pytest --version`
2. Test manual execution: `pytest tests/test_example.py -v`
3. Check dashboard logs for errors
4. **GitHub Issues:** [Crawllama Issues](https://github.com/arn-c0de/Crawllama/issues)
5. **Support Email:** [crawllama.support@protonmail.com](mailto:crawllama.support@protonmail.com)

## License

Part of the CrawlLama project © 2025
