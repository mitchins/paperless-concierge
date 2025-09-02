#!/usr/bin/env python3
"""
Unit tests for PaperlessClient class functionality.
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
sys.modules["python-dotenv"] = MagicMock()


async def test_paperless_client_initialization():
    """Test PaperlessClient initialization and configuration"""
    print("Testing PaperlessClient initialization...")

    from paperless_concierge.paperless_client import PaperlessClient

    client = PaperlessClient(
        paperless_url="http://test:8000",
        paperless_token="test_token",
        paperless_ai_url="http://test-ai:8080",
        paperless_ai_token="test_ai_token",
    )

    # Test initialization
    assert client.base_url == "http://test:8000"
    assert client.token == "test_token"
    assert client.ai_url == "http://test-ai:8080"
    assert client.ai_token == "test_ai_token"


async def test_paperless_client_headers():
    """Test PaperlessClient headers property"""
    print("Testing PaperlessClient headers...")

    from paperless_concierge.paperless_client import PaperlessClient

    client = PaperlessClient(
        paperless_url="http://test:8000", paperless_token="test_token"
    )

    # Test headers property
    headers = client.headers
    assert "Authorization" in headers
    assert headers["Authorization"] == "Token test_token"


async def test_paperless_client_minimal_config():
    """Test PaperlessClient with minimal configuration"""
    print("Testing PaperlessClient minimal config...")

    from paperless_concierge.paperless_client import PaperlessClient

    client = PaperlessClient(
        paperless_url="http://test:8000", paperless_token="test_token"
    )

    # Test properties work with minimal config
    assert client.base_url == "http://test:8000"
    headers = client.headers
    assert isinstance(headers, dict)


async def run_paperless_client_tests():
    """Run all PaperlessClient tests"""
    print("🔧 Running PaperlessClient Tests...")
    print("=" * 50)

    tests = [
        test_paperless_client_initialization,
        test_paperless_client_headers,
        test_paperless_client_minimal_config,
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
    print(f"PaperlessClient Tests: {passed}/{total} passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_paperless_client_tests())
    sys.exit(0 if success else 1)
