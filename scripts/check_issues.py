#!/usr/bin/env python3
"""Check codeql-results.sarif for high-severity issues excluding known false positives.
Excludes: py/weak-sensitive-data-hashing and any findings in paths matching 'tests/'.
Exits 0 when no issues (success), 1 when one or more relevant issues found.
"""
import json
import sys
from pathlib import Path

sarif = Path('reports/codeql-results.sarif')
if not sarif.exists():
    print('ERROR: reports/codeql-results.sarif not found', file=sys.stderr)
    sys.exit(2)

try:
    data = json.loads(sarif.read_text(encoding='utf-8'))
except Exception as e:
    print('ERROR: failed to parse SARIF: ' + str(e), file=sys.stderr)
    sys.exit(2)

results = data.get('runs', [])[0].get('results', []) if data.get('runs') else []
relevant = []
for r in results:
    level = r.get('level')
    rule = r.get('ruleId')
    try:
        uri = r.get('locations', [])[0].get('physicalLocation', {}).get('artifactLocation', {}).get('uri', '')
    except Exception:
        uri = ''
    if level == 'error' and rule != 'py/weak-sensitive-data-hashing' and 'tests/' not in uri:
        relevant.append((rule, uri, r.get('locations', [])[0].get('physicalLocation', {}).get('region', {}).get('startLine')))

if not relevant:
    print('✅ CodeQL security scan passed!')
    sys.exit(0)

print(f'❌ Found {len(relevant)} high severity security issues!')
print('Review codeql-results.sarif for details')
for rule, uri, line in relevant:
    print(f'- {rule} in {uri} at line {line}')
print('To commit anyway, use: git commit --no-verify')
sys.exit(1)
