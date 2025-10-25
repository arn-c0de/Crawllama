"""Quick check for OSINT test discovery."""
from core.health.test_collector import TestCollector

tc = TestCollector()
tests = tc.discover_tests()
osint_tests = [t for t in tests if t['category'] == 'osint']

print(f'Total tests found: {len(tests)}')
print(f'OSINT tests found: {len(osint_tests)}')
print('\nOSINT test files:')
for t in osint_tests:
    print(f'  ✓ {t["filename"]} - {t["function_count"]} test functions')
    print(f'    Path: {t["file"]}')

# Check specific v1.4.1 files
expected = ['test_twitter_intel.py', 'test_github_intel.py', 'test_ip_intel.py', 'test_domain_intel.py']
found = [t['filename'] for t in osint_tests]

print('\nv1.4.1 Module Status:')
for exp in expected:
    status = '✅' if exp in found else '❌'
    print(f'{status} {exp}')

if all(exp in found for exp in expected):
    print('\n✅ SUCCESS: All v1.4.1 OSINT tests discovered!')
else:
    print('\n⚠️ WARNING: Some v1.4.1 tests missing!')
