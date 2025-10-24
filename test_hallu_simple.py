#!/usr/bin/env python3
"""Simple test for Hallucination Detection without network dependencies."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.hallu_detect import create_detector


def test_basic_functionality():
    """Test basic hallucination detection without Wikipedia."""
    print("🔍 Testing Basic Hallucination Detection\n")
    
    # Configuration without network dependencies
    config = {
        "enabled": True,
        "detection_level": "medium",
        "fact_checking_enabled": False,  # Disable Wikipedia
        "context_analysis_enabled": True,
        "max_processing_time": 2.0
    }
    
    detector = create_detector(config)
    
    # Test cases
    test_cases = [
        {
            "name": "Normal Response",
            "context": "What is the capital of France?",
            "response": "The capital of France is Paris.",
            "expected_hallucination": False
        },
        {
            "name": "Fabricated Citation",
            "context": "Tell me about climate change.",
            "response": "According to a 2023 study by the Climate Research Institute, temperatures increased by exactly 2.47 degrees.",
            "expected_hallucination": True
        },
        {
            "name": "Context Misalignment", 
            "context": "Explain quantum computing.",
            "response": "Quantum computing is actually about cooking recipes and ingredients.",
            "expected_hallucination": True
        },
        {
            "name": "Internal Contradiction",
            "context": "Is AI helpful?", 
            "response": "AI is always helpful and never causes problems. However, AI can never be trusted and always causes issues.",
            "expected_hallucination": True
        }
    ]
    
    correct_predictions = 0
    total_tests = len(test_cases)
    
    print(f"Running {total_tests} test cases...\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['name']}")
        print(f"Context: {test_case['context']}")
        print(f"Response: {test_case['response'][:80]}...")
        
        result = detector.detect(test_case['response'], test_case['context'])
        
        is_correct = result.is_hallucination == test_case['expected_hallucination']
        if is_correct:
            correct_predictions += 1
            status = "✅ CORRECT"
        else:
            status = "❌ INCORRECT"
            
        print(f"Expected: {'Hallucination' if test_case['expected_hallucination'] else 'Valid'}")
        print(f"Detected: {'Hallucination' if result.is_hallucination else 'Valid'} ({result.confidence_score:.3f})")
        print(f"Result: {status}")
        
        if result.violations:
            print(f"Violations: {len(result.violations)}")
            for violation in result.violations[:2]:
                print(f"  - {violation['type']} ({violation['severity']})")
        
        print(f"Processing time: {result.processing_time:.3f}s")
        print("-" * 60)
    
    # Summary
    accuracy = (correct_predictions / total_tests) * 100
    print(f"\n📊 Test Summary:")
    print(f"Correct predictions: {correct_predictions}/{total_tests}")
    print(f"Accuracy: {accuracy:.1f}%")
    
    # Statistics
    stats = detector.get_statistics()
    print(f"\n📈 Detector Statistics:")
    print(f"Total checks: {stats['total_checks']}")
    print(f"Hallucinations detected: {stats['hallucinations_detected']}")
    print(f"Average processing time: {stats['avg_processing_time']:.3f}s")
    
    # Performance check
    if stats['avg_processing_time'] > 1.0:
        print("⚠️  Warning: Slow processing detected")
    else:
        print("✅ Good performance")
    
    return accuracy >= 50  # At least 50% accuracy expected


def test_configuration_levels():
    """Test different detection levels."""
    print(f"\n{'='*60}")
    print("Testing Detection Levels")
    print(f"{'='*60}")
    
    test_response = "According to a 2023 study by the Fake Research Institute, this is 100% accurate."
    test_context = "Tell me about recent research."
    
    levels = ["low", "medium", "high"]
    
    for level in levels:
        config = {
            "enabled": True,
            "detection_level": level,
            "fact_checking_enabled": False,
            "max_processing_time": 1.0
        }
        
        detector = create_detector(config)
        result = detector.detect(test_response, test_context)
        
        print(f"\nLevel {level.upper()}:")
        print(f"  Hallucination: {'YES' if result.is_hallucination else 'NO'}")
        print(f"  Confidence: {result.confidence_score:.3f}")
        print(f"  Risk: {result.risk_level}")
        print(f"  Violations: {len(result.violations)}")


if __name__ == "__main__":
    try:
        print("Starting Hallucination Detection Tests...")
        print("="*60)
        
        # Run basic tests
        success = test_basic_functionality()
        
        # Run level tests
        test_configuration_levels()
        
        print(f"\n{'='*60}")
        if success:
            print("✅ All tests completed successfully!")
        else:
            print("⚠️  Some tests had issues - check accuracy")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        sys.exit(1)