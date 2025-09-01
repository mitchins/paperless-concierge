#!/usr/bin/env python3
"""
Unit tests for configuration and constants modules.
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


async def test_config_module_loading():
    """Test config module can be imported and has expected attributes"""
    print("Testing config module loading...")

    # Test that config can be imported and has expected attributes
    from paperless_concierge import config

    # These should exist even if None/default values
    assert hasattr(config, "TELEGRAM_BOT_TOKEN")
    assert hasattr(config, "PAPERLESS_URL")
    assert hasattr(config, "PAPERLESS_TOKEN")
    assert hasattr(config, "AUTH_MODE")


async def test_constants_module():
    """Test constants module and HTTPStatus enum"""
    print("Testing constants module...")

    from paperless_concierge.constants import HTTPStatus, DEFAULT_SEARCH_RESULTS

    # Test HTTPStatus enum
    assert HTTPStatus.OK == 200
    assert HTTPStatus.NOT_FOUND == 404
    assert HTTPStatus.CREATED == 201

    # Test default values
    assert isinstance(DEFAULT_SEARCH_RESULTS, int)
    assert DEFAULT_SEARCH_RESULTS > 0


async def run_config_tests():
    """Run all configuration and constants tests"""
    print("⚙️ Running Config and Constants Tests...")
    print("=" * 50)

    tests = [
        test_config_module_loading,
        test_constants_module,
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
    print(f"Config Tests: {passed}/{total} passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_config_tests())
    sys.exit(0 if success else 1)
