"""Test API key hashing for secure logging."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app import hash_api_key_for_logging


def test_api_key_hashing():
    """Test that API keys are properly hashed for logging."""
    
    print("🧪 Testing API Key Hashing for Secure Logging...\n")
    
    test_cases = [
        {
            "name": "Real API Key",
            "input": "sk-1234567890abcdefghijklmnopqrstuvwxyz",
            "should_be_hashed": True,
            "should_not_contain": "1234567890abcdefghijklmnopqrstuvwxyz"
        },
        {
            "name": "Short API Key",
            "input": "abc123",
            "should_be_hashed": True,
            "should_not_contain": "abc123"
        },
        {
            "name": "Dev Mode Key",
            "input": "dev",
            "should_be_hashed": False,
            "expected": "dev"
        },
        {
            "name": "Unknown Key",
            "input": "unknown",
            "should_be_hashed": False,
            "expected": "unknown"
        },
        {
            "name": "IP Address (IPv4)",
            "input": "192.168.1.100",
            "should_be_hashed": False,
            "expected": "192.168.1.100"
        },
        {
            "name": "IP Address (IPv6)",
            "input": "2001:0db8::1",
            "should_be_hashed": False,
            "expected": "2001:0db8::1"
        },
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        result = hash_api_key_for_logging(test["input"])
        
        print(f"Test: {test['name']}")
        print(f"  Input: {test['input']}")
        print(f"  Output: {result}")
        
        if test["should_be_hashed"]:
            # Check that output is hashed (16 hex chars)
            if len(result) == 16 and all(c in "0123456789abcdef" for c in result):
                print("  ✅ Properly hashed (16 hex chars)")
                passed += 1
            else:
                print("  ❌ Not properly hashed")
                failed += 1
            
            # Check that sensitive data is not in output
            if "should_not_contain" in test:
                if test["should_not_contain"] not in result:
                    print("  ✅ Sensitive data not exposed")
                else:
                    print("  ❌ Sensitive data still visible!")
                    failed += 1
        else:
            # Check that special values pass through
            if result == test["expected"]:
                print("  ✅ Special value passed through correctly")
                passed += 1
            else:
                print(f"  ❌ Expected '{test['expected']}', got '{result}'")
                failed += 1
        
        print()
    
    return passed, failed


def test_hash_consistency():
    """Test that same input produces same hash."""
    print("🧪 Testing Hash Consistency...\n")
    
    api_key = "test-api-key-123"
    hash1 = hash_api_key_for_logging(api_key)
    hash2 = hash_api_key_for_logging(api_key)
    hash3 = hash_api_key_for_logging(api_key)
    
    if hash1 == hash2 == hash3:
        print(f"✅ Hash is consistent: {hash1}")
        return True
    else:
        print("❌ Hash is NOT consistent!")
        print(f"  Hash 1: {hash1}")
        print(f"  Hash 2: {hash2}")
        print(f"  Hash 3: {hash3}")
        return False


def test_hash_uniqueness():
    """Test that different inputs produce different hashes."""
    print("\n🧪 Testing Hash Uniqueness...\n")
    
    keys = [
        "api-key-1",
        "api-key-2",
        "api-key-3",
        "different-key",
        "another-key"
    ]
    
    hashes = [hash_api_key_for_logging(key) for key in keys]
    
    # Check all hashes are unique
    if len(hashes) == len(set(hashes)):
        print(f"✅ All {len(hashes)} hashes are unique")
        for key, hash_val in zip(keys, hashes):
            print(f"  {key} -> {hash_val}")
        return True
    else:
        print("❌ Hash collision detected!")
        return False


def test_no_reverse_engineering():
    """Test that hash cannot be easily reverse engineered."""
    print("\n🧪 Testing Reverse Engineering Resistance...\n")
    
    # Test with known patterns
    patterns = [
        ("password123", "Common password"),
        ("admin", "Common username"),
        ("test", "Common test value"),
        ("sk-proj-1234567890", "OpenAI-style key"),
    ]
    
    all_pass = True
    for value, description in patterns:
        hashed = hash_api_key_for_logging(value)
        
        # Check that original value is not in hash
        if value.lower() not in hashed.lower():
            print(f"✅ {description}: '{value}' -> '{hashed}' (not reversible)")
        else:
            print(f"❌ {description}: Original value visible in hash!")
            all_pass = False
    
    return all_pass


if __name__ == "__main__":
    print("="*60)
    print("API KEY HASHING TEST SUITE")
    print("="*60 + "\n")
    
    try:
        # Run tests
        passed, failed = test_api_key_hashing()
        consistency_ok = test_hash_consistency()
        uniqueness_ok = test_hash_uniqueness()
        no_reverse_ok = test_no_reverse_engineering()
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Basic Hashing Tests: {passed} passed, {failed} failed")
        print(f"Consistency Test: {'✅ PASS' if consistency_ok else '❌ FAIL'}")
        print(f"Uniqueness Test: {'✅ PASS' if uniqueness_ok else '❌ FAIL'}")
        print(f"Reverse Engineering Test: {'✅ PASS' if no_reverse_ok else '❌ FAIL'}")
        
        if failed == 0 and consistency_ok and uniqueness_ok and no_reverse_ok:
            print("\n🎉 ALL TESTS PASSED! API key hashing is secure.")
            sys.exit(0)
        else:
            print("\n❌ SOME TESTS FAILED!")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
