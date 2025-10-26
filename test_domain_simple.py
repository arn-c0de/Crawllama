"""Simple test script for domain intelligence."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Direct import to avoid dependency issues
from core.osint.domain_intel import DomainIntelligence
from core.osint.query_parser import OSINTQueryParser


def main():
    print("\n🔍 Testing Domain Intelligence\n")
    print("=" * 70)

    # Initialize
    intel = DomainIntelligence()

    # Test domain
    test_domain = "example.com"
    print(f"\nAnalyzing domain: {test_domain}")
    print("=" * 70)

    # Analyze
    result = intel.analyze_domain(test_domain)

    # Format and display
    formatted = intel.format_results(result)
    print(formatted)

    # Test query parser
    print("\n" + "=" * 70)
    print("Testing Query Parser")
    print("=" * 70)

    parser = OSINTQueryParser()
    query = "domain:github.com"
    print(f"\nQuery: {query}")

    parsed = parser.parse(query)
    print(f"Parsed domain: {parsed.domain}")
    print(f"Remaining text: {parsed.text}")

    # Extract targets
    targets = parser.extract_targets(query)
    print(f"Extracted targets: {targets}")

    print("\n" + "=" * 70)
    print("✓ Test completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
