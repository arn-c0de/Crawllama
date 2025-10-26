#!/usr/bin/env python3
"""
Test IP intelligence functionality.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_ip_intelligence():
    """Test IP intelligence functionality."""
    from tools.osint_tool import osint_search
    
    print("🌐 Testing IP Intelligence")
    print("=" * 50)
    
    # Test cases - using well-known public IPs
    test_ips = [
        "ip:8.8.8.8",  # Google DNS
        "ip:1.1.1.1",  # Cloudflare DNS
        "ip:208.67.222.222",  # OpenDNS
        "192.168.1.1",  # Should detect as IP even without ip: prefix
        "invalid-ip"   # Should handle invalid IP
    ]
    
    for query in test_ips:
        print(f"\n🔍 Testing: {query}")
        print("-" * 30)
        
        try:
            result = osint_search(query)
            print(result)
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 30)

def test_direct_ip_lookup():
    """Test direct IP lookup."""
    print("\n🔄 Testing Direct IP Lookup")
    print("=" * 50)
    
    async def run_test():
        try:
            from core.osint.ip_intel import IPIntelligence
            
            async with IPIntelligence() as intel:
                # Test Google DNS
                result = await intel.lookup_ip("8.8.8.8")
                
                print("Direct lookup result:")
                print(f"IP: {result.get('ip')}")
                print(f"Valid: {result.get('valid')}")
                print(f"Type: {result.get('type')}")
                
                geo = result.get('geolocation', {})
                if geo:
                    print(f"Country: {geo.get('country', 'Unknown')}")
                    print(f"ISP: {geo.get('isp', 'Unknown')}")
                
                print(f"Confidence: {result.get('confidence_score', 0):.1%}")
                
        except Exception as e:
            print(f"❌ Direct test error: {e}")
            import traceback
            traceback.print_exc()
    
    # Run async test
    try:
        asyncio.run(run_test())
    except Exception as e:
        print(f"❌ Async test failed: {e}")

def main():
    """Run all IP intelligence tests."""
    print("🚀 IP Intelligence Test Suite")
    print("=" * 60)
    
    # Test 1: OSINT tool integration
    test_ip_intelligence()
    
    # Test 2: Direct IP lookup
    test_direct_ip_lookup()
    
    print("\n✅ IP Intelligence test completed!")
    print("\n💡 Usage examples:")
    print("  - osint_search('ip:8.8.8.8')")
    print("  - osint_search('ip:1.1.1.1')")
    print("  - osint_search('192.168.1.1')  # Auto-detects IP")

if __name__ == "__main__":
    main()