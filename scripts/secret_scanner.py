#!/usr/bin/env python3
"""
Secret Scanner for the Crawllama project.
Scans for API keys, tokens, and other secrets in project files (excluding venv).
"""

import os
import re
import sys
from pathlib import Path

# Dangerous patterns indicating secrets
SECRET_PATTERNS = [
    r'sk-[a-zA-Z0-9]{20,}',  # OpenAI API Keys
    r'pk_[a-zA-Z0-9]{20,}',  # Stripe Keys
    r'api_key\s*[=:]\s*["\']?[a-zA-Z0-9_-]{10,}["\']?',  # API Keys
    r'secret_key\s*[=:]\s*["\']?[a-zA-Z0-9_-]{10,}["\']?',  # Secret Keys
    r'access_token\s*[=:]\s*["\']?[a-zA-Z0-9_-]{10,}["\']?',  # Access Tokens
    r'private_key\s*[=:]\s*["\']?[a-zA-Z0-9_/-]{20,}["\']?',  # Private Keys
    r'client_secret\s*[=:]\s*["\']?[a-zA-Z0-9_-]{10,}["\']?',  # Client Secrets
    r'bearer_token\s*[=:]\s*["\']?[a-zA-Z0-9_-]{10,}["\']?',  # Bearer Tokens
    r'AKIA[0-9A-Z]{16}',  # AWS Access Keys
    r'AIza[0-9A-Za-z_-]{35}',  # Google API Keys
    r'ghp_[A-Za-z0-9]{36}',  # GitHub Personal Access Tokens
    r'xox[baprs]-[A-Za-z0-9-]{10,}',  # Slack Tokens
    r'-----BEGIN (PRIVATE|RSA) KEY-----',  # Private Key Headers
]

# File extensions to scan
SCAN_EXTENSIONS = {'.py', '.txt', '.md', '.json', '.yaml', '.yml', '.env', '.config', '.ini', '.sh', '.bat'}

# Folders to exclude
EXCLUDE_DIRS = {'venv', '__pycache__', '.git', 'node_modules', '.pytest_cache'}

# Example values to ignore (placeholders)
IGNORE_VALUES = {
    'your_key_here', 'your_api_key', 'your_secret', 'example_key',
    'placeholder', 'dummy_key', 'test_key', 'fake_key', 'xxx',
    'your_brave_api_key', 'your_serper_api_key', 'your_github_token',
    'your_twitter_api_key', 'your_access_token', 'your_instagram_token'
}

class SecretScanner:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in SECRET_PATTERNS]
        self.findings: list[dict[str, str]] = []
    
    def is_excluded_dir(self, path: Path) -> bool:
        """Check if a directory should be excluded."""
        return any(exclude in path.parts for exclude in EXCLUDE_DIRS)
    
    def is_scannable_file(self, path: Path) -> bool:
        """Check if a file should be scanned."""
        return path.suffix.lower() in SCAN_EXTENSIONS
    
    def is_placeholder_value(self, match: str) -> bool:
        """Check if a match is just a placeholder."""
        match_lower = match.lower()
        return any(placeholder in match_lower for placeholder in IGNORE_VALUES)
    
    def scan_file(self, file_path: Path) -> list[dict[str, str]]:
        """Scans a single file for secrets."""
        findings = []
        
        try:
            with open(file_path, encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                for pattern in self.patterns:
                    matches = pattern.finditer(line)
                    for match in matches:
                        secret_value = match.group(0)
                        
                        # Ignore placeholder values
                        if self.is_placeholder_value(secret_value):
                            continue
                        
                        findings.append({
                            'file': str(file_path.relative_to(self.project_root)),
                            'line': line_num,
                            'pattern': pattern.pattern,
                            'match': secret_value,
                            'context': line.strip()
                        })
        
        except Exception as e:
            print(f"⚠️  Error scanning {file_path}: {e}")
        
        return findings
    
    def scan_project(self) -> list[dict[str, str]]:
        """Scans entire project for secrets."""
        print(f"🔍 Scanning project: {self.project_root}")
        print(f"📁 Excluded folders: {', '.join(EXCLUDE_DIRS)}")
        print(f"📄 Scanned file types: {', '.join(SCAN_EXTENSIONS)}")
        print("=" * 60)
        
        all_findings = []
        scanned_files = 0
        
        for file_path in self.project_root.rglob('*'):
            if file_path.is_file() and not self.is_excluded_dir(file_path) and self.is_scannable_file(file_path):
                scanned_files += 1
                findings = self.scan_file(file_path)
                all_findings.extend(findings)
        
        print(f"📊 {scanned_files} files scanned")
        return all_findings
    
    def print_results(self, findings: list[dict[str, str]]):
        """Prints scan results."""
        if not findings:
            print("✅ No secrets found!")
            return
        
        print(f"\n🚨 {len(findings)} potential secrets found:")
        print("=" * 60)
        
        for finding in findings:
            print(f"📁 File: {finding['file']}")
            print(f"📍 Line: {finding['line']}")
            print(f"🔍 Pattern: {finding['pattern']}")
            print(f"⚠️  Match: {finding['match']}")
            print(f"📝 Context: {finding['context']}")
            print("-" * 40)
    
    def generate_report(self, findings: list[dict[str, str]], output_file: str = None):
        """Generates a report."""
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Secret Scanner Report - {len(findings)} Findings\n")
                f.write("=" * 60 + "\n\n")
                
                for finding in findings:
                    f.write(f"File: {finding['file']}\n")
                    f.write(f"Line: {finding['line']}\n")
                    f.write(f"Pattern: {finding['pattern']}\n")
                    f.write(f"Match: {finding['match']}\n")
                    f.write(f"Context: {finding['context']}\n")
                    f.write("-" * 40 + "\n")
            
            print(f"📄 Report saved: {output_file}")

def main():
    """Main entry point for the Secret Scanner."""
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = os.getcwd()
    
    # Check if project root exists
    if not os.path.exists(project_root):
        print(f"❌ Project folder not found: {project_root}")
        sys.exit(1)
    
    # Start scan
    scanner = SecretScanner(project_root)
    findings = scanner.scan_project()
    
    # Show results
    scanner.print_results(findings)
    
    # Generate report
    report_file = os.path.join(project_root, "secret_scan_report.txt")
    scanner.generate_report(findings, report_file)
    
    # Set exit code
    if findings:
        print(f"\n❌ Secret Scanner completed with {len(findings)} findings")
        sys.exit(1)
    else:
        print("\n✅ Secret Scanner successful - no secrets found")
        sys.exit(0)

if __name__ == "__main__":
    main()