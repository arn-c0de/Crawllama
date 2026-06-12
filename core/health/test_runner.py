"""Test Runner - Executes pytest tests and provides results."""

import subprocess
import json
import re
import time
import tempfile
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock


class TestRunner:
    """Executes tests using pytest and provides real-time results."""

    # Per-file execution timeout. Network-dependent OSINT integration tests
    # (DNS/MX/geolocation/SSL lookups) routinely need 40s+, so the cap has to
    # leave headroom above that while still bounding a genuinely hung test.
    DEFAULT_TIMEOUT = 120

    def __init__(self, max_workers: int = 4, use_json_report: bool = True,
                 timeout: Optional[int] = None):
        """
        Initialize TestRunner.

        Args:
            max_workers: Maximum number of parallel test executions
            use_json_report: Whether to use pytest-json-report (requires plugin)
            timeout: Per-file execution timeout in seconds. Falls back to the
                CRAWLLAMA_TEST_TIMEOUT env var, then DEFAULT_TIMEOUT.
        """
        self.max_workers = max_workers
        self.running_tests = {}
        self.lock = Lock()
        self.stop_requested = False
        self.use_json_report = use_json_report
        self.timeout = self._resolve_timeout(timeout)
        self.venv_python = self._get_venv_python()

        # Print debug info
        print(f"[TestRunner] Using Python: {self.venv_python or 'system python'}")
        print(f"[TestRunner] JSON Report: {'enabled' if use_json_report else 'disabled'}")
        print(f"[TestRunner] Per-file timeout: {self.timeout}s")

    def _resolve_timeout(self, timeout: Optional[int]) -> int:
        """Resolve the per-file timeout from arg, env var, or default."""
        if timeout is not None:
            return timeout
        env_timeout = os.environ.get("CRAWLLAMA_TEST_TIMEOUT")
        if env_timeout:
            try:
                return int(env_timeout)
            except ValueError:
                print(f"[TestRunner] Invalid CRAWLLAMA_TEST_TIMEOUT={env_timeout!r}, using default")
        return self.DEFAULT_TIMEOUT

    def _get_venv_python(self) -> Optional[str]:
        """
        Detect virtual environment Python interpreter.

        Returns:
            Path to venv Python or None
        """
        project_root = Path(__file__).parent.parent.parent

        # Check for venv directory. Prefer the uv-managed .venv; fall back to a
        # legacy venv/ for environments created before the uv migration.
        venv_paths = [
            project_root / ".venv" / "Scripts" / "python.exe",  # Windows (uv)
            project_root / ".venv" / "bin" / "python",  # Unix (uv)
            project_root / "venv" / "Scripts" / "python.exe",  # Windows (legacy)
            project_root / "venv" / "bin" / "python",  # Unix (legacy)
        ]

        for venv_path in venv_paths:
            if venv_path.exists():
                return str(venv_path)

        # Check if we're already running in a venv
        if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
            return sys.executable

        return None

    def run_all_tests(self, test_files: List[Dict[str, Any]],
                     callback: Optional[Callable] = None,
                     parallel: bool = False) -> List[Dict[str, Any]]:
        """
        Run all test files.

        Args:
            test_files: List of test file information
            callback: Optional callback for progress updates
            parallel: Whether to run tests in parallel

        Returns:
            List of test results
        """
        self.stop_requested = False
        results = []

        if parallel:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_test = {
                    executor.submit(self._run_test_file, test): test
                    for test in test_files
                }

                for future in as_completed(future_to_test):
                    if self.stop_requested:
                        break

                    test = future_to_test[future]
                    try:
                        result = future.result()
                        results.append(result)

                        if callback:
                            callback(result)
                    except Exception as e:
                        error_result = self._create_error_result(test, str(e))
                        results.append(error_result)

                        if callback:
                            callback(error_result)
        else:
            for test in test_files:
                if self.stop_requested:
                    break

                result = self._run_test_file(test)
                results.append(result)

                if callback:
                    callback(result)

        return results

    def run_single_test(self, test_file: Dict[str, Any],
                       test_function: Optional[str] = None,
                       callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Run a single test file or specific test function.

        Args:
            test_file: Test file information
            test_function: Optional specific test function to run
            callback: Optional callback for progress updates

        Returns:
            Test result dictionary
        """
        result = self._run_test_file(test_file, test_function)

        if callback:
            callback(result)

        return result

    def _run_test_file(self, test_file: Dict[str, Any],
                      test_function: Optional[str] = None) -> Dict[str, Any]:
        """
        Run a single test file using pytest.

        Args:
            test_file: Test file information
            test_function: Optional specific test function

        Returns:
            Test result dictionary
        """
        filepath = test_file['file']

        # Mark as running
        with self.lock:
            self.running_tests[filepath] = True

        # Create temporary file for JSON report
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json',
                                        delete=False) as tmp:
            json_file = tmp.name

        cmd = self._build_pytest_command(filepath, json_file, test_function)
        print(f"[TestRunner] Running command: {' '.join(cmd)}")

        start_time = time.time()

        try:
            result = self._execute_pytest(cmd, filepath)
            duration = time.time() - start_time
            test_result = self._parse_run_result(
                test_file, result, duration, json_file, cmd
            )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"[TestRunner] Test timeout after {duration:.2f}s for {filepath}")
            test_result = self._create_timeout_result(test_file, duration)

        except Exception as e:
            duration = time.time() - start_time
            test_result = self._create_error_result(test_file, str(e), duration)

        finally:
            self._cleanup_after_run(filepath, json_file)

        return test_result

    def _execute_pytest(self, cmd: List[str],
                        filepath: str) -> subprocess.CompletedProcess:
        """Run the pytest subprocess from the project root."""
        print(f"[TestRunner] Starting test execution for {filepath}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=Path(__file__).parent.parent.parent  # Project root
        )
        print(f"[TestRunner] Test completed with return code: {result.returncode}")
        return result

    def _build_pytest_command(self, filepath: str, json_file: str,
                              test_function: Optional[str]) -> List[str]:
        """Build the pytest command line for a test file."""
        cmd = [
            self.venv_python if self.venv_python else "python",
            "-m", "pytest",
            filepath,
            "-v",
            "--tb=short"
        ]

        if self.use_json_report:
            cmd.extend([
                "--json-report",
                f"--json-report-file={json_file}",
                "--json-report-omit=log"
            ])

        if test_function:
            cmd[3] = f"{filepath}::{test_function}"

        return cmd

    def _parse_run_result(self, test_file: Dict[str, Any],
                          result: subprocess.CompletedProcess,
                          duration: float, json_file: str,
                          cmd: List[str]) -> Dict[str, Any]:
        """Parse a completed pytest run, preferring the JSON report."""
        if not self.use_json_report:
            # Text-only mode - just parse text output
            print(f"[TestRunner] Parsing text output (JSON report disabled)")
            return self._parse_text_output(
                test_file, result.stdout, result.stderr,
                duration, result.returncode
            )

        if os.path.exists(json_file) and os.path.getsize(json_file) > 0:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)

                os.unlink(json_file)

                return self._parse_json_report(
                    test_file, json_data, duration, result.returncode
                )
            except json.JSONDecodeError as e:
                print(f"[TestRunner] JSON parsing failed: {e}")
                # JSON parsing failed, use text fallback
                test_result = self._parse_text_output(
                    test_file, result.stdout, result.stderr,
                    duration, result.returncode
                )
                test_result['error'] = f"JSON parsing failed: {str(e)}"
                return test_result

        # JSON file missing or empty - parse text and attach diagnostics
        test_result = self._parse_text_output(
            test_file, result.stdout, result.stderr,
            duration, result.returncode
        )
        test_result['error'] = self._build_missing_report_diagnostics(
            json_file, cmd, result
        )
        return test_result

    @staticmethod
    def _build_missing_report_diagnostics(
            json_file: str, cmd: List[str],
            result: subprocess.CompletedProcess) -> str:
        """Build diagnostic info for a missing or empty JSON report."""
        error_details = []
        if not os.path.exists(json_file):
            error_details.append("JSON report not created by pytest")
        elif os.path.getsize(json_file) == 0:
            error_details.append("JSON report is empty")

        error_details.append(f"\nCommand: {' '.join(cmd)}")
        error_details.append(f"Return code: {result.returncode}")

        if result.stderr:
            error_details.append(f"\nSTDERR:\n{result.stderr[:2000]}")
        if result.stdout:
            error_details.append(f"\nSTDOUT:\n{result.stdout[:5000]}")

        return '\n'.join(error_details)

    @staticmethod
    def _create_timeout_result(test_file: Dict[str, Any],
                               duration: float) -> Dict[str, Any]:
        """Create a result dictionary for a timed-out test file."""
        return {
            'test_file': test_file,
            'status': 'timeout',
            'duration': duration,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'total': test_file['function_count'],
            'error': f'Test execution timeout (>{duration:.1f}s)',
            'details': []
        }

    def _cleanup_after_run(self, filepath: str, json_file: str):
        """Unregister the running test and remove the temp JSON report."""
        with self.lock:
            if filepath in self.running_tests:
                del self.running_tests[filepath]

        if os.path.exists(json_file):
            try:
                os.unlink(json_file)
            except (OSError, PermissionError):
                pass

    def _parse_json_report(self, test_file: Dict[str, Any],
                          json_data: Dict[str, Any],
                          duration: float,
                          returncode: int) -> Dict[str, Any]:
        """Parse pytest JSON report."""
        summary = json_data.get('summary', {})
        tests = json_data.get('tests', [])

        # Determine overall status
        if summary.get('failed', 0) > 0:
            status = 'failed'
        elif summary.get('passed', 0) > 0:
            status = 'passed'
        elif summary.get('skipped', 0) > 0:
            status = 'skipped'
        else:
            status = 'error'

        # Parse individual test details
        details = []
        for test in tests:
            test_detail = {
                'name': test.get('nodeid', '').split('::')[-1],
                'outcome': test.get('outcome', 'unknown'),
                'duration': test.get('duration', 0),
                'call': test.get('call', {}),
            }

            # Add failure info if available
            if test_detail['outcome'] == 'failed':
                call = test.get('call', {})
                test_detail['error_message'] = call.get('longrepr', 'Unknown error')
                test_detail['traceback'] = call.get('crash', {}).get('message', '')

            details.append(test_detail)

        return {
            'test_file': test_file,
            'status': status,
            'duration': duration,
            'passed': summary.get('passed', 0),
            'failed': summary.get('failed', 0),
            'skipped': summary.get('skipped', 0),
            'total': summary.get('total', 0),
            'details': details
        }

    def _parse_text_output(self, test_file: Dict[str, Any],
                          stdout: str, stderr: str,
                          duration: float, returncode: int) -> Dict[str, Any]:
        """Fallback parser for text output."""
        passed, failed, skipped, errors = self._count_text_outcomes(stdout)
        details = self._extract_text_details(stdout)
        status = self._determine_text_status(returncode, stderr,
                                             passed, failed, errors)
        error_lines = self._collect_error_lines(stdout, stderr)

        result = {
            'test_file': test_file,
            'status': status,
            'duration': duration,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'total': passed + failed + skipped,
            'stdout': stdout,
            'stderr': stderr,
            'details': details
        }

        # Add error summary
        if error_lines:
            result['error'] = '\n'.join(error_lines[:30])  # Limit to 30 lines

        return result

    @staticmethod
    def _count_text_outcomes(stdout: str) -> tuple:
        """Count passed/failed/skipped/error outcomes in pytest text output."""
        passed = stdout.count(' PASSED')
        failed = stdout.count(' FAILED')
        skipped = stdout.count(' SKIPPED')
        errors = stdout.count(' ERROR')

        # Also check for percentage indicators (e.g., "PASSED [ 5%]")
        # This helps when output is truncated
        if passed == 0 and 'PASSED' in stdout:
            passed = len(re.findall(r'PASSED\s+\[\s*\d+%\]', stdout))
        if failed == 0 and 'FAILED' in stdout:
            failed = len(re.findall(r'FAILED\s+\[\s*\d+%\]', stdout))
        if skipped == 0 and 'SKIPPED' in stdout:
            skipped = len(re.findall(r'SKIPPED\s+\[\s*\d+%\]', stdout))

        return passed, failed, skipped, errors

    @staticmethod
    def _extract_text_details(stdout: str) -> List[Dict[str, Any]]:
        """Extract per-test detail entries from pytest text output."""
        test_pattern = re.compile(
            r'([\w/]+\.py)::(test_\w+)\s+(PASSED|FAILED|SKIPPED|ERROR)',
            re.MULTILINE
        )

        details = []
        for match in test_pattern.finditer(stdout):
            _file_part, test_name, outcome = match.groups()
            details.append({
                'name': test_name,
                'outcome': outcome.lower(),
                'duration': 0,  # Not available in text output
                'call': {}
            })
        return details

    @staticmethod
    def _determine_text_status(returncode: int, stderr: str,
                               passed: int, failed: int, errors: int) -> str:
        """Derive the overall status from counts and return code."""
        if returncode != 0:
            if errors > 0 or 'ERROR' in stderr:
                return 'error'
            if failed > 0:
                return 'failed'
            return 'error'
        return 'passed' if passed > 0 else 'skipped'

    @staticmethod
    def _collect_error_lines(stdout: str, stderr: str) -> List[str]:
        """Collect human-readable error lines from pytest output."""
        error_lines = []

        # Look for pytest-json-report missing error
        if 'pytest: error: unrecognized arguments: --json-report' in stderr:
            error_lines.append("pytest-json-report plugin not installed!")
            error_lines.append("Install with: pip install pytest-json-report")

        # Look for import errors
        if 'ImportError' in stderr or 'ModuleNotFoundError' in stderr:
            error_lines.append("Module Import Error:")
            for line in stderr.split('\n'):
                if 'Error' in line or 'import' in line.lower():
                    error_lines.append(line.strip())

        # Look for other errors in stderr
        elif stderr.strip():
            error_lines.append("STDERR:")
            error_lines.extend(stderr.strip().split('\n')[:15])  # First 15 lines

        # Look for assertion errors or exceptions in stdout
        if 'AssertionError' in stdout or 'Error' in stdout or 'FAILED' in stdout:
            failed_section = False
            for line in stdout.split('\n'):
                if 'FAILED' in line:
                    failed_section = True
                    error_lines.append(line.strip())
                elif failed_section and ('AssertionError' in line or 'Error:' in line or line.strip().startswith('>')):
                    error_lines.append(line.strip())
                    if len(error_lines) > 30:
                        break

        return error_lines

    def _create_error_result(self, test_file: Dict[str, Any],
                            error: str, duration: float = 0) -> Dict[str, Any]:
        """Create an error result."""
        return {
            'test_file': test_file,
            'status': 'error',
            'duration': duration,
            'passed': 0,
            'failed': test_file['function_count'],
            'skipped': 0,
            'total': test_file['function_count'],
            'error': error,
            'details': []
        }

    def stop(self):
        """Request to stop running tests."""
        self.stop_requested = True

    def is_running(self, filepath: str) -> bool:
        """Check if a test is currently running."""
        with self.lock:
            return filepath in self.running_tests

    def get_running_tests(self) -> List[str]:
        """Get list of currently running test files."""
        with self.lock:
            return list(self.running_tests.keys())


if __name__ == "__main__":
    # Test the runner
    from test_collector import TestCollector

    collector = TestCollector()
    tests = collector.discover_tests()

    if tests:
        runner = TestRunner()
        print(f"Running test: {tests[0]['filename']}")

        result = runner.run_single_test(tests[0])
        print(f"Status: {result['status']}")
        print(f"Duration: {result['duration']:.2f}s")
        print(f"Passed: {result['passed']}, Failed: {result['failed']}, Skipped: {result['skipped']}")
