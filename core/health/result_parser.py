"""Result Parser - Parses and aggregates test results."""

from typing import Dict, Any, List
from datetime import datetime


class ResultParser:
    """Parses and aggregates test execution results."""

    def __init__(self):
        """Initialize ResultParser."""
        self.results = []
        self.start_time = None
        self.end_time = None

    def add_result(self, result: Dict[str, Any]):
        """
        Add a test result.

        Args:
            result: Test result dictionary
        """
        if self.start_time is None:
            self.start_time = datetime.now()

        self.results.append(result)
        self.end_time = datetime.now()

    def clear(self):
        """Clear all results."""
        self.results = []
        self.start_time = None
        self.end_time = None

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics of all results.

        Returns:
            Dictionary with summary statistics
        """
        if not self.results:
            return {
                'total_files': 0,
                'total_tests': 0,
                'passed': 0,
                'failed': 0,
                'skipped': 0,
                'errors': 0,
                'timeout': 0,
                'duration': 0,
                'pass_rate': 0,  # nosec B105 - default summary metric, not credentials
                'status': 'idle'
            }

        total_passed = sum(r.get('passed', 0) for r in self.results)
        total_failed = sum(r.get('failed', 0) for r in self.results)
        total_skipped = sum(r.get('skipped', 0) for r in self.results)
        total_tests = sum(r.get('total', 0) for r in self.results)
        total_duration = sum(r.get('duration', 0) for r in self.results)

        # Count errors and timeouts (also count them as failed)
        errors = sum(1 for r in self.results if r.get('status') == 'error')
        timeout = sum(1 for r in self.results if r.get('status') == 'timeout')
        
        # Add error and timeout files to failed count
        # (if they don't have explicit failed tests, count the whole file as failed)
        for r in self.results:
            if r.get('status') in ['error', 'timeout'] and r.get('failed', 0) == 0:
                # Count the total tests in this file as failed
                total_failed += r.get('total', 1)  # At least 1 if total not set

        # Calculate pass rate
        pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

        # Determine overall status
        if total_failed > 0 or errors > 0:
            status = 'failed'
        elif timeout > 0:
            status = 'timeout'
        elif total_passed > 0:
            status = 'passed'
        elif total_skipped > 0:
            status = 'skipped'
        else:
            status = 'idle'

        return {
            'total_files': len(self.results),
            'total_tests': total_tests,
            'passed': total_passed,
            'failed': total_failed,
            'skipped': total_skipped,
            'errors': errors,
            'timeout': timeout,
            'duration': total_duration,
            'pass_rate': pass_rate,
            'status': status
        }

    def get_failed_tests(self) -> List[Dict[str, Any]]:
        """
        Get all failed test results.

        Returns:
            List of failed test results
        """
        failed = []

        for result in self.results:
            if result.get('status') == 'failed' or result.get('failed', 0) > 0:
                # Extract failed test details
                for detail in result.get('details', []):
                    if detail.get('outcome') == 'failed':
                        failed.append({
                            'file': result['test_file']['filename'],
                            'test': detail['name'],
                            'error': detail.get('error_message', 'Unknown error'),
                            'duration': detail.get('duration', 0)
                        })

        return failed

    def get_category_summary(self) -> Dict[str, Dict[str, int]]:
        """
        Get summary by category.

        Returns:
            Dictionary with category summaries
        """
        categories = {}

        for result in self.results:
            category = result['test_file'].get('category', 'other')

            if category not in categories:
                categories[category] = {
                    'files': 0,
                    'tests': 0,
                    'passed': 0,
                    'failed': 0,
                    'skipped': 0
                }

            categories[category]['files'] += 1
            categories[category]['tests'] += result.get('total', 0)
            categories[category]['passed'] += result.get('passed', 0)
            categories[category]['failed'] += result.get('failed', 0)
            categories[category]['skipped'] += result.get('skipped', 0)

        return categories

    def get_slowest_tests(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get the slowest tests.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of slowest tests
        """
        all_tests = []

        for result in self.results:
            for detail in result.get('details', []):
                all_tests.append({
                    'file': result['test_file']['filename'],
                    'test': detail['name'],
                    'duration': detail.get('duration', 0),
                    'status': detail.get('outcome', 'unknown')
                })

        # Sort by duration
        all_tests.sort(key=lambda x: x['duration'], reverse=True)

        return all_tests[:limit]

    def export_json(self) -> Dict[str, Any]:
        """
        Export results as JSON.

        Returns:
            Dictionary with all results and summary
        """
        return {
            'summary': self.get_summary(),
            'results': self.results,
            'failed_tests': self.get_failed_tests(),
            'category_summary': self.get_category_summary(),
            'slowest_tests': self.get_slowest_tests(),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None
        }

    def export_html(self) -> str:
        """
        Export results as HTML report.

        Returns:
            HTML string
        """
        summary = self.get_summary()

        # Status color
        status_colors = {
            'passed': '#10b981',
            'failed': '#ef4444',
            'skipped': '#6b7280',
            'timeout': '#f59e0b',
            'error': '#dc2626'
        }

        status_color = status_colors.get(summary['status'], '#6b7280')

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>CrawlLama Test Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background: #f3f4f6;
        }}
        .header {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            color: #111827;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .card h3 {{
            margin: 0 0 10px 0;
            color: #6b7280;
            font-size: 14px;
            text-transform: uppercase;
        }}
        .card .value {{
            font-size: 32px;
            font-weight: bold;
            color: #111827;
        }}
        .status-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            color: white;
            background: {status_color};
            font-weight: bold;
        }}
        .test-list {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .test-item {{
            padding: 10px;
            border-bottom: 1px solid #e5e7eb;
        }}
        .test-item:last-child {{
            border-bottom: none;
        }}
        .passed {{ color: #10b981; }}
        .failed {{ color: #ef4444; }}
        .skipped {{ color: #6b7280; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🦙 CrawlLama Test Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Status: <span class="status-badge">{summary['status'].upper()}</span></p>
    </div>

    <div class="summary">
        <div class="card">
            <h3>Total Tests</h3>
            <div class="value">{summary['total_tests']}</div>
        </div>
        <div class="card">
            <h3>Passed</h3>
            <div class="value passed">{summary['passed']}</div>
        </div>
        <div class="card">
            <h3>Failed</h3>
            <div class="value failed">{summary['failed']}</div>
        </div>
        <div class="card">
            <h3>Skipped</h3>
            <div class="value skipped">{summary['skipped']}</div>
        </div>
        <div class="card">
            <h3>Pass Rate</h3>
            <div class="value">{summary['pass_rate']:.1f}%</div>
        </div>
        <div class="card">
            <h3>Duration</h3>
            <div class="value">{summary['duration']:.1f}s</div>
        </div>
    </div>

    <div class="test-list">
        <h2>Test Results</h2>
"""

        for result in self.results:
            status = result.get('status', 'unknown')
            filename = result['test_file']['filename']
            passed = result.get('passed', 0)
            failed = result.get('failed', 0)
            skipped = result.get('skipped', 0)
            duration = result.get('duration', 0)

            status_class = 'passed' if status == 'passed' else 'failed' if status == 'failed' else 'skipped'

            html += f"""
        <div class="test-item">
            <strong class="{status_class}">{filename}</strong> -
            Passed: {passed}, Failed: {failed}, Skipped: {skipped}
            ({duration:.2f}s)
        </div>
"""

        html += """
    </div>
</body>
</html>
"""
        return html


if __name__ == "__main__":
    # Test the parser
    parser = ResultParser()

    # Add some dummy results
    parser.add_result({
        'test_file': {'filename': 'test_example.py', 'category': 'unit'},
        'status': 'passed',
        'duration': 1.5,
        'passed': 3,
        'failed': 0,
        'skipped': 0,
        'total': 3,
        'details': []
    })

    summary = parser.get_summary()
    print(f"Summary: {summary}")
