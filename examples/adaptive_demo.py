"""
Demo script for Adaptive Agent Hopping System

This script demonstrates how to use the adaptive system standalone
without the full API. Useful for testing and development.

Usage:
    python examples/adaptive_demo.py

Author: CrawlLama Team
"""

import sys
import json
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.adaptive_hops import AdaptiveHopManager, AdaptiveConfig, ComplexityLevel
from core.adaptive_integration import AdaptiveQueryProcessor, initialize_adaptive_system
from core.agent import SearchAgent
from core.langgraph_agent import MultiHopReasoningAgent
from core.unified_loader import get_unified_loader

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """Load configuration from config.json"""
    config_path = Path(__file__).parent.parent / "config.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def demo_complexity_analysis(manager: AdaptiveHopManager):
    """Demonstrate complexity analysis for different queries."""
    print("\n" + "="*70)
    print("DEMO 1: COMPLEXITY ANALYSIS")
    print("="*70)

    test_queries = [
        "What is Python?",
        "Latest AI developments in 2025",
        "Compare the economic impact of AI in healthcare vs manufacturing, then analyze growth potential",
        "What are the steps to implement a REST API?"
    ]

    for query in test_queries:
        print(f"\n📝 Query: {query}")
        print("-" * 70)

        complexity, metadata = manager.analyze_query_complexity(query)

        print(f"✓ Complexity: {complexity.value.upper()}")
        print(f"✓ Query Length: {metadata['query_length']}")
        print(f"✓ Factors: {', '.join(metadata['factors'])}")
        if 'llm_classification' in metadata:
            print(f"✓ LLM Classification: {metadata['llm_classification']}")


def demo_strategy_decision(manager: AdaptiveHopManager):
    """Demonstrate strategy decisions for different scenarios."""
    print("\n" + "="*70)
    print("DEMO 2: STRATEGY DECISIONS")
    print("="*70)

    test_cases = [
        ("Simple factual query", "What is the capital of France?"),
        ("Search-based query", "Latest news about quantum computing"),
        ("Complex multi-step query", "Compare X and Y, analyze pros and cons, then recommend best option")
    ]

    for case_name, query in test_cases:
        print(f"\n📝 Case: {case_name}")
        print(f"   Query: {query}")
        print("-" * 70)

        strategy = manager.decide_agent_strategy(query)

        print(f"✓ Complexity: {strategy['complexity'].upper()}")
        print(f"✓ Agent: {strategy['agent_type']}")
        print(f"✓ Use MultiHop: {strategy['use_multihop']}")
        print(f"✓ Use Tools: {strategy['use_tools']}")
        print(f"✓ Max Hops: {strategy['max_hops']}")
        print(f"✓ Reasoning:")
        for reason in strategy['reasoning']:
            print(f"   - {reason}")


def demo_resource_constraints(manager: AdaptiveHopManager):
    """Demonstrate resource constraint handling."""
    print("\n" + "="*70)
    print("DEMO 3: RESOURCE CONSTRAINTS")
    print("="*70)

    resource_status = manager.check_resource_constraints()

    print(f"\n✓ Resource Monitoring: {'Enabled' if manager.config.enable_resource_monitoring else 'Disabled'}")
    print(f"✓ Constrained: {resource_status.get('constrained', False)}")

    if 'cpu_percent' in resource_status:
        print(f"✓ CPU Usage: {resource_status['cpu_percent']:.1f}%")
        print(f"✓ Memory Usage: {resource_status['memory_percent']:.1f}%")
    else:
        print(f"✓ Reason: {resource_status.get('reason', 'unknown')}")


def demo_escalation(manager: AdaptiveHopManager):
    """Demonstrate escalation logic."""
    print("\n" + "="*70)
    print("DEMO 4: ESCALATION LOGIC")
    print("="*70)

    # Test escalation from LOW to MID
    print("\n📝 Scenario: LOW complexity with low confidence")
    print("-" * 70)

    low_strategy = {
        "complexity": "low",
        "agent_type": "SearchAgent"
    }

    should_escalate, new_strategy = manager.should_escalate(
        low_strategy,
        confidence=0.4,
        attempt_count=1
    )

    print(f"✓ Should Escalate: {should_escalate}")
    if should_escalate:
        print(f"✓ New Complexity: {new_strategy['complexity']}")
        print(f"✓ New Agent: {new_strategy['agent_type']}")
        print(f"✓ Reason: {new_strategy.get('escalation_reason')}")

    # Test no escalation with high confidence
    print("\n📝 Scenario: LOW complexity with high confidence")
    print("-" * 70)

    should_escalate, new_strategy = manager.should_escalate(
        low_strategy,
        confidence=0.9,
        attempt_count=1
    )

    print(f"✓ Should Escalate: {should_escalate}")
    if not should_escalate:
        print(f"✓ Reason: Confidence is high enough")


def demo_full_integration(processor: AdaptiveQueryProcessor):
    """Demonstrate full integration with query processing."""
    print("\n" + "="*70)
    print("DEMO 5: FULL QUERY PROCESSING")
    print("="*70)

    test_queries = [
        ("Simple query", "What is machine learning?"),
        ("Complex query", "Compare supervised and unsupervised learning, explain use cases")
    ]

    for case_name, query in test_queries:
        print(f"\n📝 {case_name}")
        print(f"   Query: {query}")
        print("-" * 70)

        try:
            result = processor.process_query(
                query=query,
                enable_escalation=True
            )

            print(f"✓ Strategy:")
            print(f"   - Complexity: {result['strategy']['complexity']}")
            print(f"   - Agent: {result['strategy']['agent_type']}")
            print(f"   - Max Hops: {result['strategy']['max_hops']}")

            print(f"✓ Metadata:")
            print(f"   - Attempts: {result['metadata']['attempts']}")
            print(f"   - Elapsed Time: {result['metadata']['elapsed_time']:.2f}s")
            print(f"   - Escalations: {len(result['metadata']['escalation_history'])}")

            if result['metadata']['escalation_history']:
                print(f"✓ Escalation History:")
                for esc in result['metadata']['escalation_history']:
                    print(f"   - Attempt {esc['attempt']}: {esc['from_agent']} → {esc['to_agent']}")
                    print(f"     Reason: {esc['reason']}")

            print(f"\n✓ Answer Preview:")
            answer_preview = result['answer'][:200]
            print(f"   {answer_preview}{'...' if len(result['answer']) > 200 else ''}")

        except Exception as e:
            print(f"✗ Error: {e}")


def demo_custom_config():
    """Demonstrate custom configuration."""
    print("\n" + "="*70)
    print("DEMO 6: CUSTOM CONFIGURATION")
    print("="*70)

    # Create custom config
    custom_config = AdaptiveConfig(
        enable_resource_monitoring=False,
        enable_confidence_escalation=True,
        confidence_low=0.6,
        max_hops_high=3,
        degraded_mode_max_hops=1
    )

    print(f"✓ Custom Configuration:")
    print(f"   - Resource Monitoring: {custom_config.enable_resource_monitoring}")
    print(f"   - Confidence Escalation: {custom_config.enable_confidence_escalation}")
    print(f"   - Confidence Low Threshold: {custom_config.confidence_low}")
    print(f"   - Max Hops (HIGH): {custom_config.max_hops_high}")
    print(f"   - Degraded Mode Hops: {custom_config.degraded_mode_max_hops}")


def main():
    """Main demo function."""
    print("\n" + "="*70)
    print(" CrawlLama - Adaptive Agent Hopping System Demo")
    print("="*70)

    try:
        # Load config
        print("\n⚙ Loading configuration...")
        config = load_config()

        # Initialize LLM
        print("⚙ Initializing LLM...")
        loader = get_unified_loader(config)
        llm = loader.load_llm(
            model_name=config["llm"]["model"],
            temperature=config["llm"]["temperature"]
        )

        # Initialize agents
        print("⚙ Initializing agents...")
        agent = SearchAgent(config=config, enable_web=True, debug=False)
        multihop_agent = MultiHopReasoningAgent(config=config, max_hops=3)

        # Initialize adaptive system
        print("⚙ Initializing adaptive system...")
        adaptive_manager, adaptive_processor = initialize_adaptive_system(
            llm=llm,
            agent=agent,
            multihop_agent=multihop_agent,
            system_monitor=None,  # Optional
            performance_tracker=None  # Optional
        )

        print("✓ All systems initialized!\n")

        # Run demos
        demo_complexity_analysis(adaptive_manager)
        demo_strategy_decision(adaptive_manager)
        demo_resource_constraints(adaptive_manager)
        demo_escalation(adaptive_manager)
        demo_full_integration(adaptive_processor)
        demo_custom_config()

        print("\n" + "="*70)
        print(" Demo completed successfully! ✓")
        print("="*70)

    except KeyboardInterrupt:
        print("\n\n⚠ Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        print(f"\n✗ Demo failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
