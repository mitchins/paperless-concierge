#!/usr/bin/env python3
"""
Simple import tests to validate package structure and basic functionality.
"""

import os
import sys

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


def test_imports():
    """Test that all modules can be imported without errors"""
    try:
        import paperless_concierge  # noqa: F401
        from paperless_concierge import config  # noqa: F401
        from paperless_concierge import document_tracker  # noqa: F401
        from paperless_concierge import paperless_client  # noqa: F401
        from paperless_concierge import user_manager  # noqa: F401

        print("✅ All modules imported successfully")
        assert True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        assert False, f"Import error: {e}"


def test_basic_functionality():
    """Test basic functionality of key classes"""
    try:
        from paperless_concierge.document_tracker import DocumentTracker
        from paperless_concierge.paperless_client import PaperlessClient
        from paperless_concierge.user_manager import UserManager

        # Test client creation
        client = PaperlessClient(
            paperless_url="http://test:8000", paperless_token="test_token"
        )
        assert client.base_url == "http://test:8000"
        assert client.token == "test_token"

        # Test user manager
        user_manager = UserManager(auth_mode="global")
        assert user_manager.auth_mode == "global"

        # Test document tracker (with mock app)
        from unittest.mock import Mock

        mock_app = Mock()
        tracker = DocumentTracker(mock_app)
        assert tracker.tracked_documents == {}

        # Clean up tracker resources
        tracker.cleanup()

        print("✅ Basic functionality tests passed")
        assert True

    except (ValueError, KeyError, AttributeError, OSError, ImportError) as e:
        print(f"❌ Basic functionality test failed: {e}")
        assert False, f"Basic functionality failed: {e}"


def test_configuration():
    """Test configuration loading"""
    try:
        from paperless_concierge import config

        # Should have loaded environment variables
        assert hasattr(config, "TELEGRAM_BOT_TOKEN")
        assert hasattr(config, "PAPERLESS_URL")

        print("✅ Configuration tests passed")
        assert True

    except (ValueError, KeyError, AttributeError, OSError) as e:
        print(f"❌ Configuration test failed: {e}")
        assert False, f"Configuration failed: {e}"


def test_persistent_cache():
    """Test persistent cache functionality"""
    try:
        import diskcache as dc

        # Check if diskcache is mocked (from our coverage test setup)
        if hasattr(dc, "_mock_name"):
            # If mocked, just verify the module can be imported
            print("✅ Persistent cache tests passed (mocked)")
            assert True
            return

        # Test cache creation and basic operations
        cache = dc.Cache(".test_cache")
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"
        cache.clear()
        cache.close()

        # Clean up
        import shutil

        if os.path.exists(".test_cache"):
            shutil.rmtree(".test_cache")

        print("✅ Persistent cache tests passed")
        assert True

    except (OSError, ValueError, ImportError) as e:
        print(f"❌ Persistent cache test failed: {e}")
        assert False, f"Persistent cache failed: {e}"


if __name__ == "__main__":
    print("🧪 Running import and basic functionality tests...")
    print("=" * 50)

    tests = [
        ("Module Imports", test_imports),
        ("Basic Functionality", test_basic_functionality),
        ("Configuration", test_configuration),
        ("Persistent Cache", test_persistent_cache),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n🔄 Running {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")

    print(f"\n🎯 Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Package is properly organized.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check the output above.")
        sys.exit(1)
