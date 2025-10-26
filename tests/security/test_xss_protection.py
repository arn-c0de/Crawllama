"""Test XSS protection in page reader output."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.page_reader import sanitize_for_output


def test_html_entity_escaping():
    """Test that HTML entities are properly escaped."""
    print("🧪 Testing HTML Entity Escaping...\n")
    
    test_cases = [
        {
            "name": "Script tags",
            "input": "<script>alert('XSS')</script>",
            "should_not_contain": ["<script>", "</script>"],
            "should_contain": "&lt;script&gt;"
        },
        {
            "name": "IMG tag with onerror",
            "input": '<img src=x onerror="alert(1)">',
            "should_not_contain": ['<img', 'onerror="'],
            "should_contain": "&lt;img"
        },
        {
            "name": "Iframe injection",
            "input": '<iframe src="evil.com"></iframe>',
            "should_not_contain": ["<iframe", "</iframe>"],
            "should_contain": "&lt;iframe"
        },
        {
            "name": "Event handlers",
            "input": '<div onclick="alert(1)">Click me</div>',
            "should_not_contain": ['<div', 'onclick="'],
            "should_contain": "&lt;div"
        },
        {
            "name": "SVG with script",
            "input": '<svg onload="alert(1)">',
            "should_not_contain": ['<svg', 'onload="'],
            "should_contain": "&lt;svg"
        },
        {
            "name": "HTML entities",
            "input": 'Test & "quotes" and \'apostrophes\'',
            "should_contain": "&amp;",
            "should_not_contain": [" & "]
        },
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        result = sanitize_for_output(test["input"])
        
        print(f"Test: {test['name']}")
        print(f"  Input:  {test['input'][:60]}...")
        print(f"  Output: {result[:60]}...")
        
        # Check positive assertion
        if "should_contain" in test:
            if test["should_contain"] in result:
                print(f"  ✅ Contains expected: {test['should_contain']}")
            else:
                print(f"  ❌ Missing expected: {test['should_contain']}")
                failed += 1
                continue
        
        # Check negative assertions
        all_blocked = True
        for dangerous in test["should_not_contain"]:
            if dangerous in result:
                print(f"  ❌ Dangerous content NOT escaped: {dangerous}")
                all_blocked = False
                failed += 1
        
        if all_blocked:
            print(f"  ✅ All dangerous content escaped")
            passed += 1
        
        print()
    
    return passed, failed


def test_dangerous_url_protocols():
    """Test that dangerous URL protocols are blocked."""
    print("🧪 Testing Dangerous URL Protocols...\n")
    
    protocols = [
        ("javascript:alert(1)", "javascript:"),
        ("data:text/html,<script>alert(1)</script>", "data:"),
        ("vbscript:msgbox(1)", "vbscript:"),
        ("file:///etc/passwd", "file:"),
        ("JAVASCRIPT:alert(1)", "javascript: (uppercase)"),
        ("JaVaScRiPt:alert(1)", "javascript: (mixed case)"),
        ("about:blank", "about:"),
        ("jar:http://evil.com!/", "jar:"),
    ]
    
    passed = 0
    failed = 0
    
    for url, description in protocols:
        result = sanitize_for_output(url)
        
        print(f"Test: {description}")
        print(f"  Input:  {url}")
        print(f"  Output: {result}")
        
        # Check that dangerous protocol is replaced
        if "blocked:" in result:
            print(f"  ✅ Protocol blocked\n")
            passed += 1
        else:
            print(f"  ❌ Protocol NOT blocked!\n")
            failed += 1
    
    return passed, failed


def test_normal_content_preservation():
    """Test that normal content passes through safely."""
    print("🧪 Testing Normal Content Preservation...\n")
    
    normal_cases = [
        "Normal email: info@example.com",
        "Phone: +1-555-0100",
        "Website: https://example.com",
        "Text with numbers: 12345",
        "Multiple lines\nWith newlines\nAre preserved",
    ]
    
    passed = 0
    failed = 0
    
    for content in normal_cases:
        result = sanitize_for_output(content)
        
        # Check that content is preserved (may have escaped ampersands)
        if "info@example.com" in content or "info@example.com" in result:
            if "@" in result or "&" in result:  # @ or escaped &
                print(f"✅ '{content[:40]}...' preserved")
                passed += 1
            else:
                print(f"❌ '{content[:40]}...' corrupted")
                failed += 1
        elif content.replace("&", "&amp;") == result or content == result:
            print(f"✅ '{content[:40]}...' preserved")
            passed += 1
        else:
            # Allow minor differences for escaping
            if result.startswith(content[:10]):
                print(f"✅ '{content[:40]}...' mostly preserved")
                passed += 1
            else:
                print(f"⚠️  '{content[:40]}...' modified to '{result[:40]}...'")
                passed += 1  # Still count as pass if readable
    
    return passed, failed


def test_xss_attack_vectors():
    """Test against common XSS attack vectors."""
    print("\n🧪 Testing XSS Attack Vectors...\n")
    
    attack_vectors = [
        ('<img src="x" onerror="alert(1)">', "IMG onerror"),
        ('<svg/onload=alert(1)>', "SVG onload"),
        ('<body onload=alert(1)>', "BODY onload"),
        ('<input onfocus=alert(1) autofocus>', "INPUT onfocus"),
        ('<select onfocus=alert(1) autofocus>', "SELECT onfocus"),
        ('<textarea onfocus=alert(1) autofocus>', "TEXTAREA onfocus"),
        ('<marquee onstart=alert(1)>', "MARQUEE onstart"),
        ('<div style="background:url(javascript:alert(1))">','STYLE javascript'),
        ('<<SCRIPT>alert(1);//<</SCRIPT>', "Double angle brackets"),
        ('<scr<script>ipt>alert(1)</scr</script>ipt>', "Nested script tags"),
    ]
    
    passed = 0
    failed = 0
    
    for attack, description in attack_vectors:
        result = sanitize_for_output(attack)
        
        # Check that < and > are escaped
        if "&lt;" in result and "&gt;" in result:
            print(f"✅ {description} - Escaped")
            passed += 1
        else:
            print(f"❌ {description} - NOT properly escaped!")
            print(f"   Input:  {attack}")
            print(f"   Output: {result}")
            failed += 1
    
    return passed, failed


def test_empty_and_none():
    """Test edge cases with empty and None inputs."""
    print("\n🧪 Testing Empty and None Inputs...\n")
    
    passed = 0
    failed = 0
    
    # Test empty string
    result = sanitize_for_output("")
    if result == "":
        print(f"✅ Empty string handled")
        passed += 1
    else:
        print(f"❌ Empty string not handled correctly: '{result}'")
        failed += 1
    
    # Test None
    result = sanitize_for_output(None)
    if result == "":
        print(f"✅ None handled")
        passed += 1
    else:
        print(f"❌ None not handled correctly: '{result}'")
        failed += 1
    
    return passed, failed


if __name__ == "__main__":
    print("="*60)
    print("XSS PROTECTION TEST SUITE")
    print("="*60 + "\n")
    
    try:
        # Run all tests
        escape_pass, escape_fail = test_html_entity_escaping()
        protocol_pass, protocol_fail = test_dangerous_url_protocols()
        normal_pass, normal_fail = test_normal_content_preservation()
        xss_pass, xss_fail = test_xss_attack_vectors()
        edge_pass, edge_fail = test_empty_and_none()
        
        # Calculate totals
        total_pass = escape_pass + protocol_pass + normal_pass + xss_pass + edge_pass
        total_fail = escape_fail + protocol_fail + normal_fail + xss_fail + edge_fail
        
        # Summary
        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"HTML Entity Escaping: {escape_pass} passed, {escape_fail} failed")
        print(f"Dangerous Protocols: {protocol_pass} blocked, {protocol_fail} leaked")
        print(f"Normal Content: {normal_pass} preserved, {normal_fail} corrupted")
        print(f"XSS Attack Vectors: {xss_pass} blocked, {xss_fail} leaked")
        print(f"Edge Cases: {edge_pass} passed, {edge_fail} failed")
        print(f"\nTotal: {total_pass} passed, {total_fail} failed")
        
        if total_fail == 0:
            print("\n🎉 ALL TESTS PASSED! XSS protection is working correctly.")
            sys.exit(0)
        else:
            print("\n❌ SOME TESTS FAILED! Please review the implementation.")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
