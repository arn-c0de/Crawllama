"""Quick test for GlobalRegistry."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_registry():
    """Test GlobalRegistry functionality."""
    print("🧪 Testing GlobalRegistry...")
    
    from core.registry import GlobalRegistry, get_unified_loader
    
    # Test 1: Singleton pattern
    loader1 = get_unified_loader()
    loader2 = get_unified_loader()
    assert loader1 is loader2, "❌ Singleton failed"
    print("✅ Singleton pattern works")
    
    # Test 2: Instance caching
    assert GlobalRegistry.has("unified_loader"), "❌ Instance not cached"
    print("✅ Instance caching works")
    
    # Test 3: List instances
    instances = GlobalRegistry.list_instances()
    assert "unified_loader" in instances, "❌ Instance not in list"
    print(f"✅ Listed instances: {instances}")
    
    # Test 4: List factories
    factories = GlobalRegistry.list_factories()
    assert "unified_loader" in factories, "❌ unified_loader factory not registered"
    assert "safe_fetcher" in factories, "❌ safe_fetcher factory not registered"
    print(f"✅ Listed factories: {factories}")
    
    # Test 5: Clear specific instance
    GlobalRegistry.clear("unified_loader")
    assert not GlobalRegistry.has("unified_loader"), "❌ Clear failed"
    print("✅ Clear specific instance works")
    
    # Test 6: Re-create after clear
    loader3 = get_unified_loader()
    assert loader3 is not loader1, "❌ Should be new instance"
    assert loader3 is not None, "❌ Failed to re-create"
    print("✅ Re-creation after clear works")
    
    print("\n🎉 All GlobalRegistry tests passed!")


if __name__ == "__main__":
    try:
        test_registry()
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
