#!/usr/bin/env python3
"""
Secret Scanner for the Crawllama project.
Scans for API keys, tokens, and other secrets in project files (excluding venv).
"""

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

# Detection rules: regexes that indicate a credential. These are the scanner's
# own rule set, not secret material — the name avoids "secret" so static
# analysis does not classify the regex strings themselves as sensitive data.
DETECTION_PATTERNS = [
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

def redact(value: str) -> str:
    """Replaces a raw match with a non-reversible fingerprint.

    Findings must never carry the matched value itself: they are printed to
    stdout (CI logs) and written to a report file. A truncated SHA-256 digest
    keeps findings comparable across runs without exposing the credential.
    """
    digest = hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]
    return f"<redacted len={len(value)} sha256:{digest}>"


class SecretScanner:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in DETECTION_PATTERNS]
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
    
    def redact_line(self, line: str) -> str:
        """Returns the source line with every pattern hit fingerprinted."""
        for pattern in self.patterns:
            line = pattern.sub(lambda m: redact(m.group(0)), line)
        return line

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
                        raw = match.group(0)

                        # Ignore placeholder values
                        if self.is_placeholder_value(raw):
                            continue

                        findings.append({
                            'file': str(file_path.relative_to(self.project_root)),
                            'line': line_num,
                            'pattern': pattern.pattern,
                            'redacted': redact(raw),
                            'context': self.redact_line(line.strip())
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
            print(f"⚠️  Match: {finding['redacted']}")
            print(f"📝 Context: {finding['context']}")
            print("-" * 40)

    def generate_report(self, findings: list[dict[str, str]], output_file: str = None):
        """Generates a report. Findings are already redacted by scan_file."""
        if output_file:
            # Owner-only from creation: the report names files and line numbers
            # of credential hits, which is enough to point an attacker at them.
            fd = os.open(output_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(f"Secret Scanner Report - {len(findings)} Findings\n")
                f.write("=" * 60 + "\n\n")

                for finding in findings:
                    f.write(f"File: {finding['file']}\n")
                    f.write(f"Line: {finding['line']}\n")
                    f.write(f"Pattern: {finding['pattern']}\n")
                    f.write(f"Match: {finding['redacted']}\n")
                    f.write(f"Context: {finding['context']}\n")
                    f.write("-" * 40 + "\n")

            print(f"📄 Report saved: {output_file}")

def main():
    """Main entry point for the Secret Scanner."""
    parser = argparse.ArgumentParser(description="Scan the project for secrets.")
    parser.add_argument('project_root', nargs='?', default=os.getcwd(),
                        help="Folder to scan (default: current directory)")
    parser.add_argument('--report', nargs='?', const='secret_scan_report.txt',
                        metavar='PATH',
                        help="Also write a report file (off by default)")
    args = parser.parse_args()
    project_root = args.project_root

    # Check if project root exists
    if not os.path.exists(project_root):
        print(f"❌ Project folder not found: {project_root}")
        sys.exit(1)

    # Start scan
    scanner = SecretScanner(project_root)
    findings = scanner.scan_project()

    # Show results
    scanner.print_results(findings)

    # Generate report only when explicitly requested
    if args.report:
        scanner.generate_report(findings, args.report)


    # Set exit code
    if findings:
        print(f"\n❌ Secret Scanner completed with {len(findings)} findings")
        sys.exit(1)
    else:
        print("\n✅ Secret Scanner successful - no secrets found")
        sys.exit(0)

if __name__ == "__main__":
    main()