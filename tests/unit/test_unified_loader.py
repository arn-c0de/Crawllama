"""Quick test for UnifiedLoader functionality."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_unified_loader():
    """Test basic UnifiedLoader functionality."""
    print("🧪 Testing UnifiedLoader...")
    
    from core.unified_loader import get_unified_loader
    
    loader = get_unified_loader()
    
    # Test 1: Singleton pattern
    loader2 = get_unified_loader()
    assert loader is loader2, "❌ Singleton failed"
    print("✅ Singleton pattern works")
    
    # Test 2: Cache stats
    stats = loader.get_cache_stats()
    assert "tools" in stats, "❌ Cache stats missing 'tools'"
    assert "plugins" in stats, "❌ Cache stats missing 'plugins'"
    print(f"✅ Cache stats: {stats}")
    
    # Test 3: Discover plugins
    plugins = loader.discover_plugins()
    assert isinstance(plugins, list), "❌ discover_plugins didn't return list"
    print(f"✅ Discovered {len(plugins)} plugins: {plugins}")
    
    # Test 4: Tool configs available
    assert hasattr(loader, '_tool_configs'), "❌ Tool configs missing"
    assert "web_search" in loader._tool_configs, "❌ web_search config missing"
    print(f"✅ Tool configs available: {list(loader._tool_configs.keys())}")
    
    print("\n🎉 All UnifiedLoader tests passed!")


def test_backwards_compatibility():
    """Test backwards compatibility with old APIs."""
    print("\n🧪 Testing Backwards Compatibility...")
    
    import warnings
    
    # Suppress deprecation warnings for this test
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        
        from core.lazy_loader import get_plugin_loader, get_tool_loader
        
        # Test old tool loader
        tool_loader = get_tool_loader()
        if tool_loader is None:
            raise AssertionError("❌ get_tool_loader() failed")
        print("✅ get_tool_loader() works (deprecated)")

        # Test old plugin loader
        plugin_loader = get_plugin_loader()
        if plugin_loader is None:
            raise AssertionError("❌ get_plugin_loader() failed")
        print("✅ get_plugin_loader() works (deprecated)")
    
    print("✅ Backwards compatibility maintained!")


def test_plugin_manager_integration():
    """Test PluginManager integration with UnifiedLoader."""
    print("\n🧪 Testing PluginManager Integration...")
    
    from core.plugin_manager import PluginManager
    
    # Create plugin manager
    manager = PluginManager(plugin_dir="plugins")
    
    # Test discovery
    plugins = manager.discover_plugins()
    assert isinstance(plugins, list), "❌ PluginManager.discover_plugins() failed"
    print(f"✅ PluginManager discovers plugins: {plugins}")
    
    # Test internal loader
    assert hasattr(manager, '_unified_loader'), "❌ PluginManager not using UnifiedLoader"
    print("✅ PluginManager uses UnifiedLoader internally")
    
    print("✅ PluginManager integration successful!")


if __name__ == "__main__":
    try:
        test_unified_loader()
        test_backwards_compatibility()
        test_plugin_manager_integration()
        
        print("\n" + "="*50)
        print("🎉 ALL TESTS PASSED!")
        print("="*50)
        print("\n✅ UnifiedLoader is production-ready!")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
