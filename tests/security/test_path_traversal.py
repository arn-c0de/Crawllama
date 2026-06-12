"""Test path traversal protection in plugin name validation."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import HTTPException

from app import validate_plugin_name


def test_valid_plugin_names():
    """Test that valid plugin names pass validation."""
    print("🧪 Testing Valid Plugin Names...\n")
    
    valid_names = [
        "example_plugin",
        "my-plugin",
        "plugin123",
        "test_plugin_v2",
        "ai-helper",
        "data_processor",
        "WebScraper",
        "API_Client",
    ]
    
    passed = 0
    failed = 0
    
    for name in valid_names:
        try:
            result = validate_plugin_name(name)
            if result == name:
                print(f"✅ '{name}' - Valid")
                passed += 1
            else:
                print(f"❌ '{name}' - Unexpected result: {result}")
                failed += 1
        except HTTPException as e:
            print(f"❌ '{name}' - Rejected: {e.detail}")
            failed += 1
    
    return passed, failed


def test_path_traversal_attacks():
    """Test that path traversal attempts are blocked."""
    print("\n🧪 Testing Path Traversal Attacks...\n")
    
    attack_vectors = [
        ("../../../etc/passwd", "Basic path traversal"),
        ("..\\..\\..\\windows\\system32", "Windows path traversal"),
        ("plugin/../secret", "Relative path in middle"),
        ("test..test", "Double dot without slash"),
        ("./plugin", "Current directory reference"),
        (".\\plugin", "Windows current directory"),
        ("plugin/subdir", "Forward slash"),
        ("plugin\\subdir", "Backslash"),
        ("%2e%2e%2f%2e%2e%2f", "URL encoded traversal"),
        ("plugin\0secret", "Null byte injection"),
        ("plugin%00secret", "URL encoded null byte"),
    ]
    
    passed = 0
    failed = 0
    
    for attack, description in attack_vectors:
        try:
            result = validate_plugin_name(attack)
            print(f"❌ '{attack}' ({description}) - NOT BLOCKED! Result: {result}")
            failed += 1
        except HTTPException:
            print(f"✅ '{attack}' ({description}) - Blocked")
            passed += 1
    
    return passed, failed


def test_unicode_bypass_attempts():
    """Test that Unicode normalization prevents bypass."""
    print("\n🧪 Testing Unicode Bypass Attempts...\n")
    
    unicode_attacks = [
        ("\u002e\u002e", "Unicode dots (U+002E)"),
        ("\uFF0E\uFF0E", "Fullwidth dots (U+FF0E)"),
        ("test\u2024\u2024test", "One dot leader (U+2024)"),
        ("plugin\uFF0Fsubdir", "Fullwidth solidus (U+FF0F)"),
        ("test\u0000secret", "Unicode null (U+0000)"),
    ]
    
    passed = 0
    failed = 0
    
    for attack, description in unicode_attacks:
        try:
            validate_plugin_name(attack)
            print(f"❌ '{attack}' ({description}) - NOT BLOCKED!")
            failed += 1
        except HTTPException:
            print(f"✅ '{attack}' ({description}) - Blocked")
            passed += 1
    
    return passed, failed


def test_forbidden_names():
    """Test that forbidden names are blocked."""
    print("\n🧪 Testing Forbidden Names...\n")
    
    forbidden = [
        (".", "Current directory"),
        ("..", "Parent directory"),
        ("__init__", "Python init file"),
        ("config", "Config file"),
        ("secret", "Secret file"),
        (".env", "Environment file"),
        ("password", "Password file"),
        ("CON", "Windows reserved (CON)"),
        ("prn", "Windows reserved (PRN)"),
        ("AUX", "Windows reserved (AUX)"),
        ("COM1", "Windows reserved (COM1)"),
    ]
    
    passed = 0
    failed = 0
    
    for name, description in forbidden:
        try:
            validate_plugin_name(name)
            print(f"❌ '{name}' ({description}) - NOT BLOCKED!")
            failed += 1
        except HTTPException:
            print(f"✅ '{name}' ({description}) - Blocked")
            passed += 1
    
    return passed, failed


def test_length_limits():
    """Test that excessively long names are rejected."""
    print("\n🧪 Testing Length Limits...\n")
    
    test_cases = [
        ("a" * 50, "50 chars (at limit)", True),
        ("a" * 51, "51 chars (over limit)", False),
        ("a" * 100, "100 chars (way over)", False),
        ("plugin_" + "x" * 43, "50 chars valid name", True),
    ]
    
    passed = 0
    failed = 0
    
    for name, description, should_pass in test_cases:
        try:
            validate_plugin_name(name)
            if should_pass:
                print(f"✅ {description} - Accepted")
                passed += 1
            else:
                print(f"❌ {description} - Should have been rejected!")
                failed += 1
        except HTTPException:
            if not should_pass:
                print(f"✅ {description} - Rejected")
                passed += 1
            else:
                print(f"❌ {description} - Should have been accepted!")
                failed += 1
    
    return passed, failed


def test_special_characters():
    """Test that special characters are blocked."""
    print("\n🧪 Testing Special Characters...\n")
    
    special_chars = [
        ("plugin@test", "@"),
        ("plugin#test", "#"),
        ("plugin$test", "$"),
        ("plugin test", "space"),
        ("plugin\ttab", "tab"),
        ("plugin\nline", "newline"),
        ("plugin;cmd", "semicolon"),
        ("plugin|cmd", "pipe"),
        ("plugin&cmd", "ampersand"),
        ("plugin<script>", "angle brackets"),
    ]
    
    passed = 0
    failed = 0
    
    for name, char_desc in special_chars:
        try:
            validate_plugin_name(name)
            print(f"❌ '{char_desc}' character - NOT BLOCKED!")
            failed += 1
        except HTTPException:
            print(f"✅ '{char_desc}' character - Blocked")
            passed += 1
    
    return passed, failed


def test_empty_and_none():
    """Test empty and None inputs."""
    print("\n🧪 Testing Empty and None Inputs...\n")
    
    passed = 0
    failed = 0
    
    # Test empty string
    try:
        validate_plugin_name("")
        print("❌ Empty string - NOT BLOCKED!")
        failed += 1
    except HTTPException:
        print("✅ Empty string - Blocked")
        passed += 1
    
    # Test whitespace
    try:
        validate_plugin_name("   ")
        print("❌ Whitespace - NOT BLOCKED!")
        failed += 1
    except HTTPException:
        print("✅ Whitespace - Blocked")
        passed += 1
    
    return passed, failed


if __name__ == "__main__":
    print("="*60)
    print("PATH TRAVERSAL PROTECTION TEST SUITE")
    print("="*60 + "\n")
    
    try:
        # Run all tests
        valid_pass, valid_fail = test_valid_plugin_names()
        traversal_pass, traversal_fail = test_path_traversal_attacks()
        unicode_pass, unicode_fail = test_unicode_bypass_attempts()
        forbidden_pass, forbidden_fail = test_forbidden_names()
        length_pass, length_fail = test_length_limits()
        special_pass, special_fail = test_special_characters()
        empty_pass, empty_fail = test_empty_and_none()
        
        # Calculate totals
        total_pass = valid_pass + traversal_pass + unicode_pass + forbidden_pass + length_pass + special_pass + empty_pass
        total_fail = valid_fail + traversal_fail + unicode_fail + forbidden_fail + length_fail + special_fail + empty_fail
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"Valid Plugin Names: {valid_pass} passed, {valid_fail} failed")
        print(f"Path Traversal: {traversal_pass} blocked, {traversal_fail} leaked")
        print(f"Unicode Bypass: {unicode_pass} blocked, {unicode_fail} leaked")
        print(f"Forbidden Names: {forbidden_pass} blocked, {forbidden_fail} leaked")
        print(f"Length Limits: {length_pass} passed, {length_fail} failed")
        print(f"Special Characters: {special_pass} blocked, {special_fail} leaked")
        print(f"Empty/None: {empty_pass} blocked, {empty_fail} leaked")
        print(f"\nTotal: {total_pass} passed, {total_fail} failed")
        
        if total_fail == 0:
            print("\n🎉 ALL TESTS PASSED! Path traversal protection is working correctly.")
            sys.exit(0)
        else:
            print("\n❌ SOME TESTS FAILED! Please review the implementation.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
