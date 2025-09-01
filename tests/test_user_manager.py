#!/usr/bin/env python3
"""
Unit tests for UserManager class functionality.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, Mock, patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

# Mock external dependencies before any imports
sys.modules["aiohttp"] = MagicMock()
sys.modules["telegram"] = MagicMock()
sys.modules["telegram.ext"] = MagicMock()
sys.modules["diskcache"] = MagicMock()
sys.modules["aiofiles"] = MagicMock()
sys.modules["python-dotenv"] = MagicMock()


async def test_user_manager_initialization():
    """Test UserManager initialization and configuration"""
    print("Testing UserManager initialization...")

    from paperless_concierge.user_manager import UserManager

    # Test global mode initialization
    user_manager = UserManager(auth_mode="global")
    assert user_manager.auth_mode == "global"

    # Test user_scoped mode initialization
    user_manager_scoped = UserManager(auth_mode="user_scoped")
    assert user_manager_scoped.auth_mode == "user_scoped"

    # Test that authorized_users is a set
    assert isinstance(user_manager.authorized_users, set)

    # Test basic functionality exists
    assert hasattr(user_manager, "is_authorized")
    assert callable(user_manager.is_authorized)


async def test_user_config_dataclass():
    """Test UserConfig dataclass functionality"""
    print("Testing UserConfig dataclass...")

    from paperless_concierge.user_manager import UserConfig

    user_config = UserConfig(
        user_id=123,
        name="Test",
        username="test",
        paperless_url="http://test:8000",
        paperless_token="token",
    )

    assert user_config.user_id == 123
    assert user_config.name == "Test"
    assert user_config.username == "test"
    assert user_config.paperless_url == "http://test:8000"
    assert user_config.paperless_token == "token"


async def run_user_manager_tests():
    """Run all UserManager tests"""
    print("👥 Running UserManager Tests...")
    print("=" * 50)

    tests = [
        test_user_manager_initialization,
        test_user_config_dataclass,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            await test()
            passed += 1
            print(f"✅ {test.__name__}")
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")

    print("=" * 50)
    print(f"UserManager Tests: {passed}/{total} passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_user_manager_tests())
    sys.exit(0 if success else 1)
