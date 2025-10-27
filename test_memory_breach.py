#!/usr/bin/env python
"""
Test script for Memory Breach Data Storage.

Demonstrates how breach/vulnerability data is stored and retrieved
from the memory system.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.memory_store import get_memory_store
from datetime import datetime


def test_email_breach_storage():
    """Test storing and retrieving breach data."""
    print("\n" + "="*70)
    print("EMAIL BREACH DATA STORAGE TEST")
    print("="*70)

    # Get memory store
    memory = get_memory_store()

    # Test email
    test_email = "test@example.com"

    print(f"\n1. Adding test email: {test_email}")
    memory.remember_email(test_email, metadata={'source': 'test_script'})

    # Simulate breach data (like from HIBP)
    breach_info = {
        'pwned': True,
        'breach_count': 3,
        'paste_count': 1,
        'severity': 'high',
        'last_breach': '2024-01-15',
        'breaches': [
            {'name': 'Test Breach 1', 'date': '2024-01'},
            {'name': 'Test Breach 2', 'date': '2023-05'},
            {'name': 'Test Breach 3', 'date': '2023-01'}
        ]
    }

    # Simulate vulnerability data (like from LeakCheck)
    vuln_info = {
        'vulnerable': True,
        'leak_count': 5,
        'severity': 'medium',
        'found_in': ['Collection #1', 'Pastebin'],
        'breach_sources': [
            {'source': 'Collection #1', 'type': 'credential_dump', 'date': '2019-01'},
            {'source': 'Pastebin', 'type': 'paste_dump', 'date': '2024-01'},
            {'source': 'Local List: combo.txt', 'type': 'credential_dump', 'date': 'Unknown'}
        ]
    }

    print(f"\n2. Updating breach information...")
    memory.update_email_breach_info(test_email, breach_info, vuln_info)

    print(f"\n3. Retrieving breach data...")
    email_data = memory.get_email_with_breach_info(test_email)

    if email_data:
        print(f"\n   Email: {email_data['email']}")
        print(f"   Added: {email_data['added_at']}")
        print(f"   Last Updated: {email_data.get('last_updated', 'Never')}")

        breach_summary = email_data.get('breach_summary')
        if breach_summary:
            print(f"\n   Status: {breach_summary['status']}")
            print(f"   Last Checked: {breach_summary['last_checked']}")
            print(f"\n   Details: {len(breach_summary['details'])} findings")

            for detail in breach_summary['details']:
                print(f"   - {detail['type']}: {detail['severity']}")

    print(f"\n4. Generating formatted report...")
    report = memory.format_email_breach_report(test_email)
    print(report)

    print(f"\n5. Testing email without breach data...")
    test_email_2 = "safe@example.com"
    memory.remember_email(test_email_2, metadata={'source': 'test_script'})
    report_2 = memory.format_email_breach_report(test_email_2)
    print(report_2)

    print("\n✅ Test completed!")


def test_all_emails_with_breach_status():
    """Display all emails with their breach status."""
    print("\n" + "="*70)
    print("ALL EMAILS IN MEMORY (with Breach Status)")
    print("="*70)

    memory = get_memory_store()
    all_emails = memory.get_all_emails()

    if not all_emails:
        print("\nNo emails in memory.")
        return

    for i, entry in enumerate(all_emails, 1):
        email = entry['value']
        print(f"\n{i}. {email}")
        print(f"   Added: {entry.get('added_at', 'Unknown')}")

        # Check for breach data
        breach_data = entry.get('metadata', {}).get('breach_data', {})
        if breach_data:
            hibp = breach_data.get('hibp', {})
            vuln = breach_data.get('vulnerability', {})

            status = "✅ SAFE"
            if hibp.get('pwned'):
                status = "🚨 COMPROMISED"
            elif vuln.get('vulnerable'):
                status = "🔓 EXPOSED"

            print(f"   Status: {status}")
            print(f"   Last Checked: {breach_data.get('last_checked', 'Never')}")

            if hibp.get('pwned'):
                print(f"   Breaches: {hibp.get('breach_count', 0)}")

            if vuln.get('vulnerable'):
                print(f"   Leaks: {vuln.get('leak_count', 0)}")
        else:
            print(f"   Status: ❓ NO SCAN DATA")

    print(f"\n{'='*70}")
    print(f"Total: {len(all_emails)} emails")


if __name__ == "__main__":
    print("\n🔍 Testing Memory Breach Data Storage")
    print("=" * 70)

    # Run tests
    test_email_breach_storage()

    print("\n\n")

    test_all_emails_with_breach_status()

    print("\n✅ All tests completed!")
    print("\nℹ️  Note: The breach data is now persistently stored in data/memory.json")
    print("   Next time you analyze an email, the breach data will be saved automatically!")
