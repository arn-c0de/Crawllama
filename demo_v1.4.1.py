"""
Quick Start Demo for v1.4.1 Deep Intelligence Features

This script demonstrates all new intelligence modules without requiring API keys.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.osint import (
    TwitterIntelligence,
    LinkedInIntelligence,
    GitHubIntelligence,
    IPIntelligence,
    DomainIntelligence
)


async def demo_twitter():
    """Demo Twitter Intelligence (fallback mode)."""
    print("\n" + "=" * 80)
    print("🐦 TWITTER/X INTELLIGENCE DEMO")
    print("=" * 80)
    
    twitter = TwitterIntelligence()  # No API key - uses fallback
    print(f"✓ Initialized (API access: {twitter.has_api_access})")
    print("Note: Without API key, limited data available via fallback scraping")
    
    print("\n📊 Example with API key:")
    print("""
    twitter = TwitterIntelligence(bearer_token="YOUR_TOKEN")
    profile = await twitter.analyze_profile("github")
    print(f"Followers: {profile['followers']}")
    print(f"Verified: {profile['verified']}")
    """)


async def demo_linkedin():
    """Demo LinkedIn Intelligence."""
    print("\n" + "=" * 80)
    print("💼 LINKEDIN INTELLIGENCE DEMO")
    print("=" * 80)
    
    linkedin = LinkedInIntelligence()  # No API key - uses fallback
    print(f"✓ Initialized (API access: {linkedin.has_api_access})")
    print("Note: LinkedIn API requires Proxycurl subscription")
    
    print("\n📊 Example with API key:")
    print("""
    linkedin = LinkedInIntelligence(proxycurl_api_key="YOUR_KEY")
    profile = await linkedin.analyze_profile("https://linkedin.com/in/username")
    print(f"Name: {profile['full_name']}")
    print(f"Company: {profile['current_company']}")
    print(f"Skills: {profile['skills']}")
    """)


async def demo_github():
    """Demo GitHub Intelligence (works without token!)."""
    print("\n" + "=" * 80)
    print("🐙 GITHUB INTELLIGENCE DEMO")
    print("=" * 80)
    
    github = GitHubIntelligence()  # Works without token!
    print(f"✓ Initialized (API access: {github.has_api_access})")
    print("Note: Basic features work without token, enhanced features require GitHub token")
    
    print("\n🔍 Analyzing GitHub user (no token required)...")
    try:
        result = await github.analyze_developer("octocat")
        print(f"✓ Username: {result['username']}")
        print(f"✓ Name: {result['name']}")
        print(f"✓ Public Repos: {result['public_repos']}")
        print(f"✓ Followers: {result['followers']}")
        print(f"✓ Confidence: {result['confidence']:.2f}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n📊 Example with API token for enhanced features:")
    print("""
    github = GitHubIntelligence(github_token="YOUR_TOKEN")
    developer = await github.analyze_developer("torvalds")
    print(f"Contributions last year: {developer['contributions_last_year']}")
    print(f"Top languages: {developer['top_languages']}")
    """)


async def demo_ip():
    """Demo IP Intelligence."""
    print("\n" + "=" * 80)
    print("🌐 IP INTELLIGENCE DEMO")
    print("=" * 80)
    
    ip_intel = IPIntelligence()  # Uses free geolocation API
    print(f"✓ Initialized (IPinfo: {ip_intel.has_ipinfo}, AbuseIPDB: {ip_intel.has_abuseipdb})")
    print("Note: Free tier uses ip-api.com, paid tier uses IPinfo/AbuseIPDB")
    
    print("\n🔍 Analyzing IP address (free API)...")
    try:
        result = await ip_intel.analyze_ip("8.8.8.8")
        print(f"✓ IP: {result['ip']}")
        print(f"✓ Country: {result['country']}")
        print(f"✓ City: {result['city']}")
        print(f"✓ ISP: {result['isp']}")
        print(f"✓ ASN: {result['asn']}")
        print(f"✓ Confidence: {result['confidence']:.2f}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n📊 Example with API keys for enhanced features:")
    print("""
    ip_intel = IPIntelligence(
        ipinfo_token="YOUR_TOKEN",
        abuseipdb_key="YOUR_KEY"
    )
    reputation = await ip_intel.check_reputation("192.0.2.1")
    print(f"Threat score: {reputation['threat_score']}")
    """)


async def demo_domain():
    """Demo Domain Intelligence (works without API!)."""
    print("\n" + "=" * 80)
    print("🔒 DOMAIN INTELLIGENCE DEMO")
    print("=" * 80)
    
    domain_intel = DomainIntelligence()  # Works without API keys!
    print(f"✓ Initialized (WHOIS API: {domain_intel.has_whois_api})")
    print("Note: Basic DNS/SSL analysis works without API keys")
    
    print("\n🔍 Analyzing domain (no API required)...")
    try:
        result = await domain_intel.analyze_domain("github.com")
        print(f"✓ Domain: {result['domain']}")
        print(f"✓ IP Addresses: {result['ip_addresses']}")
        print(f"✓ SSL Valid: {result['ssl_certificate'].get('valid')}")
        print(f"✓ Technologies: {[t['value'] for t in result['technologies'][:3]]}")
        print(f"✓ Security Score: {result['security_score']:.2f}")
        print(f"✓ Confidence: {result['confidence']:.2f}")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print("\n📊 Example with API keys for enhanced features:")
    print("""
    domain_intel = DomainIntelligence(
        whois_api_key="YOUR_KEY",
        securitytrails_key="YOUR_KEY",
        virustotal_key="YOUR_KEY"
    )
    domain_data = await domain_intel.analyze_domain("example.com")
    print(f"Registrar: {domain_data['whois']['registrar']}")
    print(f"Subdomains: {domain_data['subdomains']}")
    print(f"Reputation: {domain_data['reputation']}")
    """)


async def main():
    """Run all demos."""
    print("\n" + "=" * 80)
    print("🚀 CRAWLLAMA v1.4.1 - DEEP INTELLIGENCE QUICK START")
    print("=" * 80)
    print("\nThis demo shows all new intelligence modules.")
    print("Most features work WITHOUT API keys (fallback methods included)!")
    print("\nFor full functionality, obtain API keys from:")
    print("  • Twitter: https://developer.twitter.com/")
    print("  • LinkedIn (Proxycurl): https://nubela.co/proxycurl/")
    print("  • GitHub: https://github.com/settings/tokens")
    print("  • IPinfo: https://ipinfo.io/")
    print("  • AbuseIPDB: https://www.abuseipdb.com/")
    print("  • Domain APIs: See docs/V1.4.1_PATCH_NOTES.md")
    
    # Run all demos
    await demo_twitter()
    await demo_linkedin()
    await demo_github()
    await demo_ip()
    await demo_domain()
    
    print("\n" + "=" * 80)
    print("✅ DEMO COMPLETE")
    print("=" * 80)
    print("\n📚 Next Steps:")
    print("  1. Read docs/V1.4.1_PATCH_NOTES.md for detailed documentation")
    print("  2. Run tests: pytest tests/test_v1.4.1_all.py -v")
    print("  3. Configure API keys in config.json (optional)")
    print("  4. Try the interactive CLI: python main.py")
    print("\n💡 All modules work without API keys - get started right away!")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    asyncio.run(main())
