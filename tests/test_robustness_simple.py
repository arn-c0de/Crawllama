"""Simple robustness test without dependencies."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def test_all():
    """Run all robustness tests."""
    print("\n" + "=" * 60)
    print("  CrawlLama Robustness Test Suite")
    print("=" * 60)

    passed = 0
    failed = 0

    # Test 1: Import robustness module
    print("\nTest 1: Import robustness module...")
    try:
        from core.robustness import (
            validate_input,
            sanitize_query,
            safe_execute,
            retry_on_failure,
            health_checker
        )
        print("  ✓ PASS: Robustness module imported successfully")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1
        return

    # Test 2: validate_input
    print("\nTest 2: validate_input()...")
    try:
        is_valid, error = validate_input("test", min_length=1, max_length=100)
        assert is_valid == True, "Should be valid"

        is_valid, error = validate_input("", min_length=1)
        assert is_valid == False, "Should be invalid"

        print("  ✓ PASS: validate_input works correctly")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # Test 3: sanitize_query
    print("\nTest 3: sanitize_query()...")
    try:
        result = sanitize_query("  lots   of    spaces  ")
        assert result == "lots of spaces", f"Expected 'lots of spaces', got '{result}'"

        result = sanitize_query("test\x00null")
        assert "\x00" not in result, "Null bytes should be removed"

        print("  ✓ PASS: sanitize_query works correctly")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # Test 4: safe_execute
    print("\nTest 4: safe_execute()...")
    try:
        success, result = safe_execute(lambda: 2 + 2, default=0)
        assert success == True and result == 4, "Should succeed and return 4"

        success, result = safe_execute(lambda: 1 / 0, default="error", log_error=False)
        assert success == False and result == "error", "Should fail and return default"

        print("  ✓ PASS: safe_execute works correctly")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # Test 5: retry_on_failure
    print("\nTest 5: retry_on_failure()...")
    try:
        attempt_count = [0]

        @retry_on_failure(max_retries=2, delay=0.1)
        def unstable():
            attempt_count[0] += 1
            if attempt_count[0] < 2:
                raise ValueError("Fail")
            return "Success"

        result = unstable()
        assert result == "Success" and attempt_count[0] == 2, "Should succeed on retry"

        print("  ✓ PASS: retry_on_failure works correctly")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # Test 6: HealthCheck
    print("\nTest 6: HealthCheck system...")
    try:
        health_checker.register_check("test_check", lambda: True, cache_seconds=1)
        is_healthy = health_checker.is_healthy("test_check")
        assert is_healthy == True, "Should be healthy"

        status = health_checker.get_status()
        assert "test_check" in status, "Should include registered check"

        print("  ✓ PASS: HealthCheck works correctly")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # Test 7: Agent with robustness
    print("\nTest 7: Agent with robustness improvements...")
    try:
        import json
        from core.agent import SearchAgent

        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        agent = SearchAgent(config, enable_web=False, debug=False)

        # Test invalid input
        response = agent.query("")
        assert "Ungültige" in response or "Invalid" in response, "Should reject empty input"

        # Test sanitization
        response = agent.query("  test   query  ")
        assert response is not None and len(response) > 0, "Should handle whitespace"

        print("  ✓ PASS: Agent robustness works correctly")
        passed += 1
    except Exception as e:
        print(f"  ✗ FAIL: {e}")
        failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"  Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed == 0:
        print("\n✓ ALL TESTS PASSED!")
        print("\nRobustness improvements include:")
        print("  • Input validation and sanitization")
        print("  • Retry mechanisms for LLM/Search")
        print("  • Better error handling and logging")
        print("  • Health checks for components")
        print("  • Safe execution wrappers")
        return 0
    else:
        print(f"\n✗ {failed} TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(test_all())
