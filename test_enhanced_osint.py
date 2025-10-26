#!/usr/bin/env python3
"""
Test enhanced OSINT capabilities with social intelligence.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.osint_tool import OSINTTool, osint_search
from core.llm_client import OllamaClient

def test_social_intelligence():
    """Test social intelligence functionality."""
    print("🔍 Testing Enhanced OSINT with Social Intelligence")
    print("=" * 60)
    
    # Test cases
    test_queries = [
        "username:github",
        "elonmusk",
        "social:microsoft",
        "@openai",
        "email:test@example.com",
        "phone:+1234567890"
    ]
    
    for query in test_queries:
        print(f"\n📋 Testing query: {query}")
        print("-" * 40)
        
        try:
            result = osint_search(query)
            print(result)
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("\n" + "=" * 40)

def test_social_query_detection():
    """Test social query type detection."""
    print("\n🎯 Testing Social Query Detection")
    print("=" * 60)
    
    try:
        # Create LLM client
        llm = OllamaClient(base_url='http://127.0.0.1:11434', model='qwen3:8b')
        osint = OSINTTool(llm)
        
        test_cases = [
            ("username:github", "social_intelligence"),
            ("elonmusk", "social_intelligence"),
            ("social:microsoft", "social_intelligence"),
            ("@openai", "social_intelligence"),
            ("email:test@example.com", "email_intelligence"),
            ("site:github.com", "advanced_search"),
            ("python programming", "general_search")
        ]
        
        for query, expected in test_cases:
            parsed = osint.query_parser.parse(query)
            detected = osint._determine_query_type(parsed)
            
            status = "✅" if detected == expected else "❌"
            print(f"{status} '{query}' -> {detected} (expected: {expected})")
            
    except Exception as e:
        print(f"❌ Error in detection test: {e}")

async def test_direct_social_search():
    """Test direct social intelligence search."""
    print("\n🌐 Testing Direct Social Search")
    print("=" * 60)
    
    try:
        # Import social intelligence directly
        from core.osint.social_intel import SocialIntelligence
        
        social_intel = SocialIntelligence()
        
        # Test username search
        print("Searching for 'github' across social platforms...")
        result = await social_intel.search_username("github")
        
        print(f"\nResults:")
        print(f"Total platforms: {len(result.get('platforms', {}))}")
        
        found_count = 0
        for platform, data in result.get('platforms', {}).items():
            if data.get('exists'):
                found_count += 1
                print(f"✓ Found on {platform}")
                if data.get('profile_data'):
                    profile = data['profile_data']
                    if profile.get('display_name'):
                        print(f"  Name: {profile['display_name']}")
                    if profile.get('followers'):
                        print(f"  Followers: {profile['followers']}")
                        
        print(f"\nTotal found: {found_count}")
        
    except Exception as e:
        print(f"❌ Error in direct test: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run all tests."""
    print("🚀 Enhanced OSINT System Test Suite")
    print("=" * 60)
    
    # Test 1: Basic functionality
    test_social_intelligence()
    
    # Test 2: Query type detection
    test_social_query_detection()
    
    # Test 3: Direct social search
    print("\n🔄 Running async social search test...")
    try:
        asyncio.run(test_direct_social_search())
    except Exception as e:
        print(f"❌ Async test failed: {e}")
    
    print("\n✅ Test suite completed!")
    print("\n💡 Usage examples:")
    print("  - osint_search('username:github')")
    print("  - osint_search('elonmusk')")
    print("  - osint_search('@microsoft')")
    print("  - osint_search('email:test@example.com')")

if __name__ == "__main__":
    main()