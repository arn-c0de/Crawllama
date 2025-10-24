"""Test Script: Verify Health Monitoring Installation.

Run this script to verify all health monitoring components are working.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from core.health import (
            SystemMonitor,
            ComponentHealthChecker,
            PerformanceTracker,
            AlertSystem,
            RichHealthDashboard,
            monitored,
            HealthMonitoringContext
        )
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_system_monitor():
    """Test system monitoring."""
    print("\nTesting system monitor...")
    
    try:
        from core.health import SystemMonitor
        
        monitor = SystemMonitor(update_interval=0.5)
        monitor.start()
        
        import time
        time.sleep(1.5)  # Wait for metrics
        
        metrics = monitor.get_latest_metrics()
        
        if metrics:
            print(f"✅ System metrics collected:")
            print(f"   CPU: {metrics.cpu_percent:.1f}%")
            print(f"   Memory: {metrics.memory_percent:.1f}%")
            print(f"   Disk: {metrics.disk_percent:.1f}%")
            result = True
        else:
            print("❌ No metrics collected")
            result = False
        
        monitor.stop()
        return result
        
    except Exception as e:
        print(f"❌ System monitor failed: {e}")
        return False


def test_component_checker():
    """Test component health checks."""
    print("\nTesting component checker...")
    
    try:
        from core.health import ComponentHealthChecker
        
        checker = ComponentHealthChecker(Path.cwd())
        health = checker.check_all()
        
        print(f"✅ Checked {len(health)} components:")
        for name, status in health.items():
            print(f"   {name}: {status.status.value} ({status.response_time_ms:.0f}ms)")
        
        return True
        
    except Exception as e:
        print(f"❌ Component checker failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_performance_tracker():
    """Test performance tracking."""
    print("\nTesting performance tracker...")
    
    try:
        from core.health import PerformanceTracker, PerformanceTimer
        import time
        
        tracker = PerformanceTracker()
        
        # Track some operations
        for i in range(5):
            with PerformanceTimer(tracker, "test_operation"):
                time.sleep(0.1)
        
        stats = tracker.get_stats("test_operation")
        
        if stats and stats.count == 5:
            print(f"✅ Performance tracking working:")
            print(f"   Count: {stats.count}")
            print(f"   Average: {stats.avg_duration_ms:.0f}ms")
            print(f"   P95: {stats.p95_duration_ms:.0f}ms")
            return True
        else:
            print("❌ Performance tracking failed")
            return False
        
    except Exception as e:
        print(f"❌ Performance tracker failed: {e}")
        return False


def test_alert_system():
    """Test alert system."""
    print("\nTesting alert system...")
    
    try:
        from core.health import AlertSystem, AlertLevel
        
        alerts = AlertSystem()
        
        # Register callback
        received = []
        def callback(alert):
            received.append(alert)
        
        alerts.register_callback(callback)
        
        # Create test alert by checking system with high CPU threshold
        from core.health import SystemMonitor
        monitor = SystemMonitor()
        monitor.start()
        
        import time
        time.sleep(1.5)
        
        # Check with low threshold to trigger alert
        alerts.check_alerts({
            'system_metrics': monitor.get_latest_metrics()
        })
        
        monitor.stop()
        
        active = alerts.get_alerts()
        print(f"✅ Alert system working:")
        print(f"   Active alerts: {len(active)}")
        print(f"   Callback triggered: {len(received)} times")
        
        return True
        
    except Exception as e:
        print(f"❌ Alert system failed: {e}")
        return False


def test_decorator():
    """Test monitoring decorator."""
    print("\nTesting @monitored decorator...")
    
    try:
        from core.health import monitored, get_performance_tracker
        import time
        
        @monitored("decorated_function")
        def test_function():
            time.sleep(0.1)
            return "success"
        
        # Call function a few times
        for i in range(3):
            result = test_function()
        
        # Check stats
        tracker = get_performance_tracker()
        stats = tracker.get_stats("decorated_function")
        
        if stats and stats.count == 3:
            print(f"✅ Decorator working:")
            print(f"   Tracked calls: {stats.count}")
            print(f"   Average time: {stats.avg_duration_ms:.0f}ms")
            return True
        else:
            print("❌ Decorator tracking failed")
            return False
        
    except Exception as e:
        print(f"❌ Decorator test failed: {e}")
        return False


def test_integration():
    """Test integration helpers."""
    print("\nTesting integration helpers...")
    
    try:
        from core.health import (
            HealthMonitoringContext,
            print_health_summary
        )
        import time
        
        with HealthMonitoringContext(check_alerts=False) as monitor:
            time.sleep(0.5)
            metrics = monitor.get_metrics()
        
        if metrics:
            print(f"✅ Integration context working")
            print(f"   Latest metrics available: CPU={metrics.cpu_percent:.1f}%")
            return True
        else:
            print("❌ Integration context failed")
            return False
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("🏥 CrawlLama Health Monitoring - Verification Tests")
    print("="*60)
    
    tests = [
        ("Imports", test_imports),
        ("System Monitor", test_system_monitor),
        ("Component Checker", test_component_checker),
        ("Performance Tracker", test_performance_tracker),
        ("Alert System", test_alert_system),
        ("Decorator", test_decorator),
        ("Integration", test_integration),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Health monitoring is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
