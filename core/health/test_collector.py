"""Test Collector - Discovers and parses test files."""

import ast
import glob
import os
from pathlib import Path
from typing import Any


class TestCollector:
    """Discovers and collects all test files in the project."""

    def __init__(self, test_dir: str = "tests"):
        """
        Initialize TestCollector.

        Args:
            test_dir: Directory containing test files (default: "tests")
        """
        self.test_dir = Path(test_dir)
        self.categories = {
            'unit': ['cache', 'llm_client', 'rate_limiter', 'domain_blacklist', 'safe_fetch'],
            'integration': ['integration', 'web_search'],
            'osint': ['osint', 'ddgs', 'social_intel', 'social'],
            'quality': ['hallucination', 'hallu', 'quality', 'scoring'],
            'robustness': ['robustness', 'error_simulation', 'fallback_manager'],
            'multihop': ['multihop_reasoning'],
            'security': ['security', 'ssrf', 'xss', 'prompt_injection', 'path_traversal', 'api_key']
        }

    def discover_tests(self) -> list[dict[str, Any]]:
        """
        Discover all test files in the test directory and subdirectories.

        Returns:
            List of test file information dictionaries
        """
        if not self.test_dir.exists():
            return []

        test_files = []
        
        # Search in main test directory
        main_pattern = str(self.test_dir / "test_*.py")
        for filepath in glob.glob(main_pattern):
            if 'Kopie' in filepath or filepath.endswith('~'):
                continue
            try:
                test_info = self._parse_test_file(filepath)
                if test_info:
                    test_files.append(test_info)
            except Exception as e:
                print(f"Error parsing {filepath}: {e}")
                continue
        
        # Search in subdirectories (category folders)
        subdirs = ['unit', 'integration', 'osint', 'quality', 'robustness', 'multihop', 'security', 'other']
        for subdir in subdirs:
            subdir_path = self.test_dir / subdir
            if subdir_path.exists():
                sub_pattern = str(subdir_path / "test_*.py")
                for filepath in glob.glob(sub_pattern):
                    if 'Kopie' in filepath or filepath.endswith('~'):
                        continue
                    try:
                        test_info = self._parse_test_file(filepath)
                        if test_info:
                            test_files.append(test_info)
                    except Exception as e:
                        print(f"Error parsing {filepath}: {e}")
                        continue

        return sorted(test_files, key=lambda x: x['category'])

    def _parse_test_file(self, filepath: str) -> dict[str, Any]:
        """
        Parse a test file and extract test functions.

        Args:
            filepath: Path to test file

        Returns:
            Dictionary with test file information
        """
        try:
            with open(filepath, encoding='utf-8') as f:
                content = f.read()
                tree = ast.parse(content)
        except Exception:
            return None

        # Extract test functions
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                # Extract docstring
                docstring = ast.get_docstring(node)
                functions.append({
                    'name': node.name,
                    'docstring': docstring or '',
                    'line': node.lineno
                })

        # Extract module docstring
        module_docstring = ast.get_docstring(tree)

        filename = os.path.basename(filepath)

        return {
            'file': filepath,
            'filename': filename,
            'module_name': filename.replace('.py', ''),
            'functions': functions,
            'category': self._categorize(filename, filepath),
            'docstring': module_docstring or '',
            'function_count': len(functions)
        }

    def _categorize(self, filename: str, filepath: str = None) -> str:
        """
        Categorize a test file based on its directory or name.

        Args:
            filename: Name of the test file
            filepath: Full path to the test file (optional)

        Returns:
            Category name
        """
        # First check if file is in a category subdirectory
        if filepath:
            path_parts = Path(filepath).parts
            # Check if any parent directory matches a category
            for category in ['unit', 'integration', 'osint', 'quality', 'robustness', 'multihop', 'security', 'other']:
                if category in path_parts:
                    return category
        
        # Fall back to filename-based categorization
        filename_lower = filename.lower()

        for category, keywords in self.categories.items():
            if any(keyword in filename_lower for keyword in keywords):
                return category

        return 'other'

    def get_category_summary(self, test_files: list[dict[str, Any]]) -> dict[str, int]:
        """
        Get summary of test files by category.

        Args:
            test_files: List of test file information

        Returns:
            Dictionary with category counts
        """
        summary = {}
        for test in test_files:
            category = test['category']
            summary[category] = summary.get(category, 0) + 1

        return summary

    def get_total_test_count(self, test_files: list[dict[str, Any]]) -> int:
        """
        Get total number of test functions across all files.

        Args:
            test_files: List of test file information

        Returns:
            Total number of test functions
        """
        return sum(test['function_count'] for test in test_files)

    def filter_by_category(self, test_files: list[dict[str, Any]],
                          category: str) -> list[dict[str, Any]]:
        """
        Filter test files by category.

        Args:
            test_files: List of test file information
            category: Category to filter by

        Returns:
            Filtered list of test files
        """
        if category.lower() == 'all':
            return test_files

        return [test for test in test_files if test['category'] == category]


if __name__ == "__main__":
    # Test the collector
    collector = TestCollector()
    tests = collector.discover_tests()

    print(f"Found {len(tests)} test files")
    print(f"Total test functions: {collector.get_total_test_count(tests)}")
    print("\nCategory summary:")
    for category, count in collector.get_category_summary(tests).items():
        print(f"  {category}: {count} files")

    print("\nTest files:")
    for test in tests:
        print(f"  {test['filename']} ({test['category']}) - {test['function_count']} tests")
