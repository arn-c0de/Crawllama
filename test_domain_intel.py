"""Test script for domain intelligence OSINT feature."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.osint import DomainIntelligence, OSINTQueryParser


def test_domain_intelligence():
    """Test DomainIntelligence module."""
    print("=" * 60)
    print("Testing Domain Intelligence")
    print("=" * 60)

    intel = DomainIntelligence()

    # Test domains
    test_domains = [
        "example.com",
        "www.github.com",
        "google.com"
    ]

    for domain in test_domains:
        print(f"\n{'=' * 60}")
        print(f"Analyzing: {domain}")
        print('=' * 60)

        result = intel.analyze_domain(domain)
        formatted = intel.format_results(result)
        print(formatted)
        print()


def test_query_parser():
    """Test OSINT Query Parser with domain operator."""
    print("\n" + "=" * 60)
    print("Testing Query Parser - Domain Operator")
    print("=" * 60)

    parser = OSINTQueryParser()

    # Test queries
    test_queries = [
        "domain:example.com",
        "domain:github.com site:github.com",
        "domain:google.de what is the location"
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        parsed = parser.parse(query)
        print(f"Parsed: {parsed}")
        print(f"  - Domain: {parsed.domain}")
        print(f"  - Text: {parsed.text}")
        print(f"  - Site: {parsed.site}")

        # Extract targets
        targets = parser.extract_targets(query)
        print(f"Targets: {targets}")


def test_osint_tool():
    """Test OSINT Tool with domain query."""
    print("\n" + "=" * 60)
    print("Testing OSINT Tool - Domain Intelligence")
    print("=" * 60)

    from tools.osint_tool import osint_search
    import json

    # Load config
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except:
        print("Warning: Could not load config.json, using defaults")
        config = {
            "llm": {
                "base_url": "http://127.0.0.1:11434",
                "model": "qwen2.5:3b"
            },
            "osint": {
                "enabled": True
            }
        }

    # Test query
    query = "domain:example.com"
    print(f"\nOSINT Query: {query}")
    print("-" * 60)

    try:
        result = osint_search(query, config)
        print(result)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🔍 CrawlLama - Domain Intelligence Test Suite\n")

    # Run tests
    try:
        test_domain_intelligence()
        test_query_parser()
        test_osint_tool()

        print("\n" + "=" * 60)
        print("✓ All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
