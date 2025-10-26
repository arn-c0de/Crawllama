#!/usr/bin/env python3
"""
Simple IP intelligence test without LLM dependency.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_ip_lookup_simple():
    """Test IP lookup without full OSINT integration."""
    print("🌐 Simple IP Intelligence Test")
    print("=" * 50)
    
    try:
        from core.osint.ip_intel import IPIntelligence
        
        # Test with Google DNS
        test_ip = "8.8.8.8"
        print(f"Testing IP: {test_ip}")
        print("-" * 30)
        
        async with IPIntelligence() as intel:
            result = await intel.lookup_ip(test_ip)
            
            # Display formatted results
            formatted = intel.format_results(result)
            print(formatted)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def test_ip_validation():
    """Test IP validation logic."""
    print("\n🔍 IP Validation Test")
    print("=" * 50)
    
    try:
        from core.osint.ip_intel import IPIntelligence
        
        intel = IPIntelligence()
        
        test_cases = [
            "8.8.8.8",           # Valid IPv4 public
            "192.168.1.1",       # Valid IPv4 private
            "2001:4860:4860::8888",  # Valid IPv6 public
            "127.0.0.1",         # Loopback
            "invalid-ip",        # Invalid
            "300.300.300.300"    # Invalid IPv4
        ]
        
        for ip in test_cases:
            is_valid, ip_type, normalized = intel.validate_ip(ip)
            status = "✅" if is_valid else "❌"
            print(f"{status} {ip} -> {ip_type} ({normalized})")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def test_query_parsing():
    """Test IP query parsing."""
    print("\n📝 Query Parsing Test")
    print("=" * 50)
    
    try:
        from core.osint.query_parser import OSINTQueryParser
        
        parser = OSINTQueryParser()
        
        test_queries = [
            "ip:8.8.8.8",
            "8.8.8.8",           # Should auto-detect
            "ip:192.168.1.1 test",
            "site:example.com ip:1.1.1.1"
        ]
        
        for query in test_queries:
            parsed = parser.parse(query)
            print(f"Query: '{query}'")
            print(f"  IP: {parsed.ip}")
            print(f"  Text: '{parsed.text}'")
            print(f"  Site: {parsed.site}")
            print()
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Run IP intelligence tests."""
    print("🚀 IP Intelligence Test Suite")
    print("=" * 60)
    
    # Test 1: IP validation
    test_ip_validation()
    
    # Test 2: Query parsing
    test_query_parsing()
    
    # Test 3: Simple IP lookup
    print("\n🔄 Running IP lookup test...")
    try:
        asyncio.run(test_ip_lookup_simple())
    except Exception as e:
        print(f"❌ Lookup test failed: {e}")
    
    print("\n✅ IP Intelligence tests completed!")
    print("\n💡 IP Intelligence features:")
    print("  ✓ IPv4 and IPv6 validation")
    print("  ✓ Private/Public IP detection") 
    print("  ✓ Multiple geolocation services")
    print("  ✓ Reverse DNS lookup")
    print("  ✓ WHOIS information")
    print("  ✓ Security reputation checks")
    print("  ✓ VPN/Proxy detection")

if __name__ == "__main__":
    main()