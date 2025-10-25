#!/usr/bin/env python3
"""
Secret Scanner für Crawllama Projekt
Scannt nach API Keys, Tokens und anderen Secrets in Projektdateien (ohne venv).
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Set

# Gefährliche Patterns die auf Secrets hinweisen
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

# Dateierweiterungen die gescannt werden sollen
SCAN_EXTENSIONS = {'.py', '.txt', '.md', '.json', '.yaml', '.yml', '.env', '.config', '.ini', '.sh', '.bat'}

# Ordner die ausgeschlossen werden sollen
EXCLUDE_DIRS = {'venv', '__pycache__', '.git', 'node_modules', '.pytest_cache'}

# Beispielwerte die ignoriert werden (Platzhalter)
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
        self.findings: List[Dict[str, str]] = []
    
    def is_excluded_dir(self, path: Path) -> bool:
        """Prüft ob ein Verzeichnis ausgeschlossen werden soll."""
        return any(exclude in path.parts for exclude in EXCLUDE_DIRS)
    
    def is_scannable_file(self, path: Path) -> bool:
        """Prüft ob eine Datei gescannt werden soll."""
        return path.suffix.lower() in SCAN_EXTENSIONS
    
    def is_placeholder_value(self, match: str) -> bool:
        """Prüft ob ein Match nur ein Platzhalter ist."""
        match_lower = match.lower()
        return any(placeholder in match_lower for placeholder in IGNORE_VALUES)
    
    def scan_file(self, file_path: Path) -> List[Dict[str, str]]:
        """Scannt eine einzelne Datei nach Secrets."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                for pattern in self.patterns:
                    matches = pattern.finditer(line)
                    for match in matches:
                        secret_value = match.group(0)
                        
                        # Ignoriere Platzhalter-Werte
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
            print(f"⚠️  Fehler beim Scannen von {file_path}: {e}")
        
        return findings
    
    def scan_project(self) -> List[Dict[str, str]]:
        """Scannt das gesamte Projekt nach Secrets."""
        print(f"🔍 Scanne Projekt: {self.project_root}")
        print(f"📁 Ausgeschlossene Ordner: {', '.join(EXCLUDE_DIRS)}")
        print(f"📄 Gescannte Dateitypen: {', '.join(SCAN_EXTENSIONS)}")
        print("=" * 60)
        
        all_findings = []
        scanned_files = 0
        
        for file_path in self.project_root.rglob('*'):
            if file_path.is_file() and not self.is_excluded_dir(file_path) and self.is_scannable_file(file_path):
                scanned_files += 1
                findings = self.scan_file(file_path)
                all_findings.extend(findings)
        
        print(f"📊 {scanned_files} Dateien gescannt")
        return all_findings
    
    def print_results(self, findings: List[Dict[str, str]]):
        """Gibt die Scan-Ergebnisse aus."""
        if not findings:
            print("✅ Keine Secrets gefunden!")
            return
        
        print(f"\n🚨 {len(findings)} potentielle Secrets gefunden:")
        print("=" * 60)
        
        for finding in findings:
            print(f"📁 Datei: {finding['file']}")
            print(f"📍 Zeile: {finding['line']}")
            print(f"🔍 Pattern: {finding['pattern']}")
            print(f"⚠️  Match: {finding['match']}")
            print(f"📝 Kontext: {finding['context']}")
            print("-" * 40)
    
    def generate_report(self, findings: List[Dict[str, str]], output_file: str = None):
        """Generiert einen Bericht."""
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
            
            print(f"📄 Bericht gespeichert: {output_file}")

def main():
    """Hauptfunktion des Secret Scanners."""
    if len(sys.argv) > 1:
        project_root = sys.argv[1]
    else:
        project_root = os.getcwd()
    
    # Prüfe ob Projekt-Root existiert
    if not os.path.exists(project_root):
        print(f"❌ Projekt-Ordner nicht gefunden: {project_root}")
        sys.exit(1)
    
    # Starte Scan
    scanner = SecretScanner(project_root)
    findings = scanner.scan_project()
    
    # Zeige Ergebnisse
    scanner.print_results(findings)
    
    # Generiere Bericht
    report_file = os.path.join(project_root, "secret_scan_report.txt")
    scanner.generate_report(findings, report_file)
    
    # Exit Code setzen
    if findings:
        print(f"\n❌ Secret Scanner beendet mit {len(findings)} Findings")
        sys.exit(1)
    else:
        print("\n✅ Secret Scanner erfolgreich - keine Secrets gefunden")
        sys.exit(0)

if __name__ == "__main__":
    main()