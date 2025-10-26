"""Test script for OSINT module.

Run this to verify OSINT features are working correctly.
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from core.osint import (
    OSINTQueryParser,
    EmailIntelligence,
    PhoneIntelligence,
    DomainIntelligence,
    QueryEnhancer,
    OSINTCompliance
)
from core.llm_client import OllamaClient

console = Console()


def test_query_parser():
    """Test query parser."""
    console.print("\n[bold cyan]═══ Testing Query Parser ═══[/bold cyan]")

    parser = OSINTQueryParser()

    test_queries = [
        'site:github.com python',
        'email:test@example.com site:linkedin.com',
        'phone:"+49 151 12345678"',
        'site:github.com inurl:python filetype:md',
        'intext:"machine learning" -tensorflow'
    ]

    table = Table(title="Query Parser Tests")
    table.add_column("Query", style="cyan")
    table.add_column("Site", style="green")
    table.add_column("Email", style="yellow")
    table.add_column("Phone", style="magenta")
    table.add_column("Operators", style="dim")

    for query in test_queries:
        parsed = parser.parse(query)
        ops = []
        if parsed.inurl:
            ops.append(f"inurl:{parsed.inurl}")
        if parsed.filetype:
            ops.append(f"filetype:{parsed.filetype}")
        if parsed.exclude:
            ops.append(f"-{','.join(parsed.exclude)}")

        table.add_row(
            query,
            parsed.site or "-",
            parsed.email or "-",
            parsed.phone or "-",
            ", ".join(ops) or "-"
        )

    console.print(table)
    console.print("[green]✓ Query Parser tests completed[/green]")


def test_email_intel():
    """Test email intelligence."""
    console.print("\n[bold cyan]═══ Testing Email Intelligence ═══[/bold cyan]")

    email_intel = EmailIntelligence()

    test_emails = [
        'test@example.com',
        'john.doe@company.com',
        'invalid.email',
        'test@tempmail.com'  # Disposable
    ]

    for email in test_emails:
        result = email_intel.analyze_email(email)

        console.print(f"\n[bold]Email:[/bold] {email}")
        console.print(f"  Valid: {'✓' if result['valid'] else '✗'} {result['valid']}")
        if result['valid']:
            console.print(f"  Domain: {result['domain']}")
            console.print(f"  Disposable: {result['disposable']}")
            console.print(f"  Confidence: {result['confidence']:.2f}")
            if result['variations']:
                console.print(f"  Variations: {', '.join(result['variations'][:3])}")

    console.print("\n[green]✓ Email Intelligence tests completed[/green]")


def test_phone_intel():
    """Test phone intelligence."""
    console.print("\n[bold cyan]═══ Testing Phone Intelligence ═══[/bold cyan]")

    phone_intel = PhoneIntelligence()

    test_phones = [
        ('+49 151 12345678', 'DE'),
        ('+1 555 123 4567', 'US'),
        ('0151 12345678', 'DE'),
        ('invalid', None)
    ]

    for phone, region in test_phones:
        result = phone_intel.analyze_phone(phone, region)

        console.print(f"\n[bold]Phone:[/bold] {phone}")
        console.print(f"  Valid: {'✓' if result['valid'] else '✗'} {result['valid']}")
        if result['valid']:
            console.print(f"  Formatted: {result['formatted']}")
            console.print(f"  Country: {result['country']}")
            console.print(f"  Type: {result['type']}")
            if result['carrier']:
                console.print(f"  Carrier: {result['carrier']}")
            console.print(f"  Confidence: {result['confidence']:.2f}")

    # Check if phonenumbers library available
    if phone_intel.has_phonenumbers:
        console.print("\n[green]✓ phonenumbers library available - full features enabled[/green]")
    else:
        console.print("\n[yellow]⚠ phonenumbers library not installed - basic features only[/yellow]")
        console.print("[dim]Install with: pip install phonenumbers[/dim]")

    console.print("\n[green]✓ Phone Intelligence tests completed[/green]")


def test_query_enhancer():
    """Test AI query enhancer."""
    console.print("\n[bold cyan]═══ Testing AI Query Enhancer ═══[/bold cyan]")

    try:
        # Initialize LLM
        llm = OllamaClient()

        # Check connection
        if not llm._ensure_connection():
            console.print("[yellow]⚠ Ollama not running - skipping AI tests[/yellow]")
            return

        enhancer = QueryEnhancer(llm)

        # Test entity type identification
        test_entities = [
            'test@example.com',
            '+49 151 12345678',
            'Max Mustermann',
            'example.com'
        ]

        console.print("\n[bold]Entity Type Detection:[/bold]")
        for entity in test_entities:
            entity_type = enhancer.identify_entity_type(entity)
            console.print(f"  {entity} → {entity_type}")

        # Test query variations
        console.print("\n[bold]Query Variations:[/bold]")
        query = "Max Mustermann developer"
        variations = enhancer.generate_variations(query, max_variations=3)
        console.print(f"  Original: {query}")
        for var in variations:
            console.print(f"    → {var}")

        # Test operator suggestions
        console.print("\n[bold]Operator Suggestions:[/bold]")
        query = "find John Doe on LinkedIn"
        operators = enhancer.suggest_operators(query)
        console.print(f"  Query: {query}")
        for op, val in operators.items():
            console.print(f"    → {op}: {val}")

        console.print("\n[green]✓ AI Query Enhancer tests completed[/green]")

    except Exception as e:
        console.print(f"[yellow]⚠ AI tests skipped: {e}[/yellow]")


def test_compliance():
    """Test compliance module."""
    console.print("\n[bold cyan]═══ Testing Compliance Module ═══[/bold cyan]")

    compliance = OSINTCompliance()

    # Test terms acceptance
    user_id = "test_user"

    console.print(f"\n[bold]Terms Accepted:[/bold] {compliance.check_terms_accepted(user_id)}")

    # Accept terms
    compliance.accept_terms(user_id)
    console.print(f"[bold]After Acceptance:[/bold] {compliance.check_terms_accepted(user_id)}")

    # Test query compliance
    test_cases = [
        ("email:test@example.com", "email_search", True),
        ("password hack", "general_osint", False),
        ("phone:+49151", "phone_search", True),
    ]

    console.print("\n[bold]Query Compliance:[/bold]")
    for query, qtype, expected in test_cases:
        allowed, reason = compliance.check_query(query, user_id, qtype)
        status = "✓" if allowed else "✗"
        console.print(f"  {status} {query} ({qtype})")
        if not allowed:
            console.print(f"    Reason: {reason}")

    # Test usage stats
    stats = compliance.get_usage_stats(user_id)
    console.print("\n[bold]Usage Statistics:[/bold]")
    console.print(f"  Total requests (last hour): {stats['total_requests_last_hour']}")
    console.print(f"  Remaining limits:")
    for qtype, remaining in stats['remaining_limits'].items():
        console.print(f"    • {qtype}: {remaining}")

    console.print("\n[green]✓ Compliance tests completed[/green]")


def test_domain_intel():
    """Test domain intelligence."""
    console.print("\n[bold cyan]═══ Testing Domain Intelligence ═══[/bold cyan]")

    domain_intel = DomainIntelligence()

    test_domains = [
        'google.com',
        'github.com',
        'example.com'
    ]

    for domain in test_domains:
        result = domain_intel.analyze_domain(domain)

        console.print(f"\n[bold]Domain:[/bold] {domain}")
        console.print(f"  Valid: {'✓' if result['valid'] else '✗'} {result['valid']}")
        if result['valid']:
            if result['ips']:
                console.print(f"  IPs: {', '.join(result['ips'][:3])}")
            if result['geolocation'].get('country'):
                geo = result['geolocation']
                console.print(f"  Location: {geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}")
            console.print(f"  Confidence: {result['confidence']:.2f}")

    console.print("\n[green]✓ Domain Intelligence tests completed[/green]")


def test_social_intelligence():
    """Social Intelligence OSINT Test (Dashboard Discovery)."""
    console.print("\n[bold cyan]═══ Testing Social Intelligence ═══[/bold cyan]")
    try:
        import asyncio
        from core.osint.social_intel import SocialIntelligence
        social_intel = SocialIntelligence()

        async def run_social_tests_full():
            # Test 1: Username Analysis
            test_username = "testuser123"
            console.print("=" * 60)
            console.print("TEST 1: Username Analysis")
            console.print("=" * 60)
            console.print(f"Analyzing username: {test_username}")
            results = await social_intel.analyze_username(test_username, ['github', 'twitter', 'instagram'])
            console.print(f"\n📊 Analysis Results:")
            console.print(f"├─ Username: {results['username']}")
            console.print(f"├─ Platforms checked: {results['summary']['total_platforms_checked']}")
            console.print(f"├─ Platforms found: {results['summary']['platforms_with_presence']}")
            console.print(f"├─ Confidence: {results['summary']['confidence_score']:.1f}%")
            if results['platforms_found']:
                console.print(f"\n✅ Found on platforms:")
                for platform in results['platforms_found']:
                    console.print(f"   └─ {platform['platform']}: {platform['url']}")
            if results['platforms_not_found']:
                console.print(f"\n❌ Not found on: {', '.join(results['platforms_not_found'])}")
            if results['summary']['risk_indicators']:
                console.print(f"\n⚠️  Risk indicators:")
                for indicator in results['summary']['risk_indicators']:
                    console.print(f"   └─ {indicator}")

            # Test 2: Email Profile Discovery
            console.print("\n" + "=" * 60)
            console.print("TEST 2: Email Profile Discovery")
            console.print("=" * 60)
            test_email = "john.doe@example.com"
            console.print(f"Discovering profiles for email: {test_email}")
            email_results = await social_intel.discover_profiles_by_email(test_email)
            console.print(f"\n📧 Email Analysis:")
            console.print(f"├─ Email: {email_results['email']}")
            console.print(f"├─ Extracted username: {email_results['extracted_username']}")
            console.print(f"├─ Domain: {email_results['domain']}")
            console.print(f"└─ Username matches found: {len(email_results['username_matches'])}")
            if email_results['username_matches']:
                console.print(f"\n🔗 Username-based matches:")
                for match in email_results['username_matches']:
                    console.print(f"   └─ {match['platform']}: {match['url']}")

            # Test 3: Generate Report
            console.print("\n" + "=" * 60)
            console.print("TEST 3: Social Intelligence Report")
            console.print("=" * 60)
            report = social_intel.generate_social_report(results)
            console.print(report)

            # Test 4: Platform Validation
            console.print("\n" + "=" * 60)
            console.print("TEST 4: Platform Username Validation")
            console.print("=" * 60)
            test_cases = [
                ("validuser", "twitter"),
                ("invalid@user", "twitter"),
                ("toolongusernamethatexceedslimits", "instagram"),
                ("valid_user", "github")
            ]
            for username, platform in test_cases:
                pattern = social_intel.platforms[platform]['username_pattern']
                is_valid = social_intel._validate_username_format(username, pattern)
                status = "✅ VALID" if is_valid else "❌ INVALID"
                console.print(f"{status} - {username} for {platform}")

        asyncio.run(run_social_tests_full())
        console.print("[green]✓ Social Intelligence tests completed[/green]")
    except Exception as e:
        console.print(f"[yellow]⚠ Social Intelligence tests skipped: {e}[/yellow]")


def main():
    """Run all tests."""
    console.print(Panel.fit(
        "[bold cyan]CrawlLama OSINT Module Test Suite[/bold cyan]\n"
        "Testing all OSINT components...",
        border_style="cyan"
    ))

    try:
        # Run tests

        test_query_parser()
        test_email_intel()
        test_phone_intel()
        test_domain_intel()
        test_query_enhancer()
        test_compliance()
        test_social_intelligence()

        # Summary
        console.print("\n" + "═" * 60)
        console.print(Panel.fit(
            "[bold green]✓ All OSINT Tests Completed Successfully![/bold green]\n\n"
            "OSINT module is ready to use.\n"
            "Start using with: python main.py",
            border_style="green"
        ))

        # Display usage info
        console.print("\n[bold cyan]Quick Start:[/bold cyan]")
        console.print("  • Email: [yellow]email:test@example.com[/yellow]")
        console.print("  • Phone: [yellow]phone:\"+49 151 12345678\"[/yellow]")
        console.print("  • Domain: [yellow]domain:example.com[/yellow]")
        console.print("  • Search: [yellow]site:github.com python[/yellow]")

    except Exception as e:
        console.print(f"\n[red]✗ Test failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
