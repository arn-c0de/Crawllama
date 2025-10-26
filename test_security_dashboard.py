"""Test if security tests are detected by health dashboard."""
from core.health.test_collector import TestCollector

collector = TestCollector()
tests = collector.discover_tests()

# Filter security tests
sec_tests = [t for t in tests if t['category'] == 'security']

print(f"\n✓ Security tests found: {len(sec_tests)}")
print(f"✓ Total test functions in security: {sum(t['function_count'] for t in sec_tests)}")

if sec_tests:
    print(f"\nSecurity test files:")
    for test in sec_tests:
        print(f"  - {test['filename']}: {test['function_count']} tests")
else:
    print("\n✗ ERROR: No security tests found!")

# Show all categories
print(f"\nAll categories:")
summary = collector.get_category_summary(tests)
for category, count in sorted(summary.items()):
    print(f"  {category}: {count} files")
