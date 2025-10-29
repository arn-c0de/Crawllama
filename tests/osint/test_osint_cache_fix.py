"""
Test script to verify OSINT cache fix.

This script tests that result references (quelle/source commands) 
properly access search results from OSINT queries.

NOTE: This is an integration test that makes real web searches.
It is disabled by default to avoid timeouts in CI/CD pipelines.
Run manually with: pytest tests/test_osint_cache_fix.py -v
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent import SearchAgent

# Mark as slow integration test - skip by default
pytestmark = pytest.mark.skip(reason="Integration test - makes real web requests, takes >30s. Run manually if needed.")


def test_osint_cache_fix():
    """Test that quelle commands work after OSINT search."""
    print("\n" + "="*60)
    print("Testing OSINT Cache Fix")
    print("="*60 + "\n")
    
    # Initialize agent with default config
    import json
    from pathlib import Path
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path) as f:
        config = json.load(f)
    agent = SearchAgent(config=config)
    
    # Test 1: OSINT search
    print("Test 1: OSINT Search")
    print("-" * 60)
    query1 = "site:python.org"
    # lgtm [py/clear-text-logging-sensitive-data] - Test query, not sensitive data
    print(f"Query: {query1}")
    response1 = agent.query(query1)
    print(f"Response: {response1[:200]}...")
    
    # Check if results were stored
    if agent.last_search_results:
        print(f"✅ Search results stored: {len(agent.last_search_results)} results")
    else:
        print("❌ No search results stored!")
        return False
    
    # Test 2: Source command (should NOT use cache)
    print("\n" + "="*60)
    print("Test 2: Source Command")
    print("-" * 60)
    query2 = "quelle 1"
    # lgtm [py/clear-text-logging-sensitive-data] - Test query, not sensitive data
    print(f"Query: {query2}")
    response2 = agent.query(query2)
    print(f"Response: {response2[:200]}...")

    # Check if response is NOT "No previous search results available"
    if "No previous search results" in response2:
        print("❌ Source command failed - no results found!")
        return False
    else:
        print("✅ Source command successful!")

    # Test 3: Multiple source commands (should NOT cache)
    print("\n" + "="*60)
    print("Test 3: Multiple Source Commands")
    print("-" * 60)
    query3 = "quelle 1 2"
    # lgtm [py/clear-text-logging-sensitive-data] - Test query, not sensitive data
    print(f"Query: {query3}")
    response3 = agent.query(query3)
    print(f"Response: {response3[:200]}...")
    
    if "No previous search results" in response3:
        print("❌ Multiple quelle command failed!")
        return False
    else:
        print("✅ Multiple quelle command successful!")
    
    # Test 4: Session persistence
    print("\n" + "="*60)
    print("Test 4: Session Persistence")
    print("-" * 60)
    
    # Save session
    if agent.save_session():
        print("✅ Session saved successfully")
    else:
        print("❌ Session save failed!")
        return False
    
    # Create new agent and load session
    agent2 = Agent()
    if agent2.load_session():
        print("✅ Session loaded successfully")
        print(f"Loaded {len(agent2.last_search_results)} search results")
        
        # Try source command with loaded session
        query4 = "quelle 1"
        print(f"Query (after reload): {query4}")
        response4 = agent2.query(query4)

        if "No previous search results" in response4:
            print("❌ Source command failed after session reload!")
            return False
        else:
            print("✅ Source command works after session reload!")
    else:
        print("❌ Session load failed!")
        return False
    
    print("\n" + "="*60)
    print("All tests passed! ✅")
    print("="*60 + "\n")
    return True


if __name__ == "__main__":
    try:
        success = test_osint_cache_fix()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
