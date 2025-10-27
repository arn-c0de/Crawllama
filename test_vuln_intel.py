#!/usr/bin/env python
"""
Test script for Email Vulnerability Intelligence.

Tests the new EmailVulnerabilityIntel class that checks for
leaked credentials in public breach databases without requiring
API keys or authentication.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.osint.email_intel import EmailVulnerabilityIntel


def test_vulnerability_check(email: str):
    """Test vulnerability check for an email address."""
    print("\n" + "="*70)
    print("EMAIL VULNERABILITY INTELLIGENCE TEST")
    print("="*70)
    print(f"Testing email: {email}\n")

    # Initialize vulnerability intelligence
    vuln_intel = EmailVulnerabilityIntel()

    # Check vulnerability
    result = vuln_intel.check_vulnerability(email)

    # Display results
    print(f"Vulnerable: {result['vulnerable']}")
    print(f"Leak Count: {result['leak_count']}")
    print(f"Severity: {result['severity']}")
    print(f"Found In: {result['found_in']}")

    print(f"\nEmail Hashes (for anonymous lookup):")
    print(f"  MD5:    {result['hashes']['md5']}")
    print(f"  SHA1:   {result['hashes']['sha1']}")
    print(f"  SHA256: {result['hashes']['sha256']}")

    if result['breach_sources']:
        print(f"\nBreach Sources:")
        for source in result['breach_sources']:
            print(f"  - {source}")

    print(f"\nRecommendations:")
    for rec in result['recommendations']:
        print(f"  {rec}")


def test_vulnerability_report(email: str):
    """Generate and display full vulnerability report."""
    vuln_intel = EmailVulnerabilityIntel()
    report = vuln_intel.generate_vulnerability_report(email)
    print(report)


if __name__ == "__main__":
    # Test with a sample email
    test_email = "test@example.com"

    if len(sys.argv) > 1:
        test_email = sys.argv[1]

    print("\n🔍 Testing Vulnerability Intelligence Module")
    print("=" * 70)
    print("\nNOTE: This is currently a SIMULATION.")
    print("To enable real checks, you need to:")
    print("  1. Create ./data/breaches/ directory")
    print("  2. Add public breach lists (legal sources only)")
    print("  3. Set GITHUB_TOKEN for GitHub leak scanning")
    print("=" * 70)

    # Run basic test
    test_vulnerability_check(test_email)

    # Generate full report
    print("\n\n🔍 FULL VULNERABILITY REPORT:")
    test_vulnerability_report(test_email)

    print("\n✅ Test completed!")
