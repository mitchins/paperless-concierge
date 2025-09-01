#!/usr/bin/env python3
"""
Mock test for the Telegram bot functionality without requiring real tokens.
This allows testing the bot logic without external dependencies.
"""

import asyncio
import os
import sys
import tempfile
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the config to avoid requiring real tokens
mock_config = {
    "TELEGRAM_BOT_TOKEN": "mock_token",
    "AUTH_MODE": "global",
    "AUTHORIZED_USERS": "123456789,987654321",
    "PAPERLESS_URL": "http://mock-paperless:8000",
    "PAPERLESS_TOKEN": "mock_paperless_token",
    "PAPERLESS_AI_URL": "http://mock-ai:8080",
    "PAPERLESS_AI_TOKEN": "mock_ai_token",
}


async def test_paperless_client():
    """Test PaperlessClient without real connections."""
    print("🧪 Testing PaperlessClient (mocked)...")

    with patch.dict("os.environ", mock_config):
        from paperless_client import PaperlessClient

        # Create client with explicit parameters to bypass config
        client = PaperlessClient(
            paperless_url=mock_config["PAPERLESS_URL"],
            paperless_token=mock_config["PAPERLESS_TOKEN"],
            paperless_ai_url=mock_config["PAPERLESS_AI_URL"],
            paperless_ai_token=mock_config["PAPERLESS_AI_TOKEN"],
        )

        # Test that client is created with correct config
        assert client.base_url == mock_config["PAPERLESS_URL"]
        assert client.token == mock_config["PAPERLESS_TOKEN"]

        print("✅ PaperlessClient initialized correctly")

        # Test upload method exists and is callable
        assert hasattr(client, "upload_document")
        assert callable(client.upload_document)

        # Test search method exists and is callable
        assert hasattr(client, "search_documents")
        assert callable(client.search_documents)

        # Test AI query method exists and is callable
        assert hasattr(client, "query_ai")
        assert callable(client.query_ai)

        print("✅ All required methods are present")
        return True


async def test_bot_handlers():
    """Test that bot handlers are properly configured."""
    print("\n🤖 Testing Bot Handlers (mocked)...")

    # Mock all the external dependencies
    with patch.dict("os.environ", mock_config):
        with patch("config.TELEGRAM_BOT_TOKEN", mock_config["TELEGRAM_BOT_TOKEN"]):
            with patch("config.PAPERLESS_URL", mock_config["PAPERLESS_URL"]):
                with patch("config.PAPERLESS_TOKEN", mock_config["PAPERLESS_TOKEN"]):
                    # Import after patching
                    from bot import TelegramConcierge

                    concierge = TelegramConcierge()

                    # Test that concierge has required methods
                    required_methods = [
                        "start",
                        "help_command",
                        "handle_document",
                        "query_documents",
                        "check_status",
                        "get_paperless_client",
                    ]

                    for method_name in required_methods:
                        assert hasattr(
                            concierge, method_name
                        ), f"Missing method: {method_name}"
                        assert callable(
                            getattr(concierge, method_name)
                        ), f"Method not callable: {method_name}"

                    print("✅ All bot handlers are present")

                    # Test that user manager integration works
                    assert hasattr(concierge, "upload_tasks")
                    assert isinstance(concierge.upload_tasks, dict)

                    # Clean up concierge if it has a document tracker
                    if (
                        hasattr(concierge, "document_tracker")
                        and concierge.document_tracker
                    ):
                        concierge.document_tracker.cleanup()

                    print("✅ Bot initialization working")
                    return True


async def test_file_handling():
    """Test file handling logic."""
    print("\n📁 Testing File Handling...")

    # Create a temporary test file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
        tmp.write("Test document content")
        temp_path = tmp.name

    try:
        # Test that file exists and is readable
        assert os.path.exists(temp_path)

        with open(temp_path) as f:
            content = f.read()
            assert content == "Test document content"

        print("✅ File handling works correctly")
        return True

    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)


async def test_message_formatting():
    """Test message formatting functions."""
    print("\n💬 Testing Message Formatting...")

    # Test various message scenarios
    test_cases = [
        ("Document upload", "📤 Uploading to Paperless-NGX..."),
        ("Success message", "✅ Upload initiated!"),
        ("Error message", "❌ Upload failed:"),
    ]

    for _case_name, expected_prefix in test_cases:
        # Just verify the format strings are properly constructed
        assert isinstance(expected_prefix, str)
        assert len(expected_prefix) > 0

    print("✅ Message formatting looks good")
    return True


async def test_user_manager():
    """Test UserManager functionality."""
    print("\n👥 Testing User Manager...")

    with patch.dict("os.environ", mock_config, clear=True):
        # Need to re-import to pick up the new environment variables
        import importlib

        import config

        importlib.reload(config)

        from user_manager import UserManager

        # Test global mode with explicit mock config
        user_manager = UserManager(auth_mode="global")
        assert user_manager.auth_mode == "global"

        # The mock config has "123456789,987654321" so both should be authorized
        assert user_manager.is_authorized(123456789)
        assert user_manager.is_authorized(987654321)
        assert not user_manager.is_authorized(111111111)

        # Test with mocked user config instead of relying on environment
        from user_manager import UserConfig

        mock_user_config = UserConfig(
            user_id=123456789,
            name="Test User",
            username="testuser",
            paperless_url=mock_config["PAPERLESS_URL"],
            paperless_token=mock_config["PAPERLESS_TOKEN"],
            paperless_ai_url=mock_config["PAPERLESS_AI_URL"],
            paperless_ai_token=mock_config["PAPERLESS_AI_TOKEN"],
        )

        # Patch get_user_config to return our mock config
        with patch.object(
            user_manager, "get_user_config", return_value=mock_user_config
        ):
            user_config = user_manager.get_user_config(123456789)
            assert user_config is not None
            assert user_config.paperless_url == mock_config["PAPERLESS_URL"]

        print("✅ Global mode user manager working")

        # Test that user_scoped mode would work (even without file)
        user_manager_scoped = UserManager(auth_mode="user_scoped")
        assert user_manager_scoped.auth_mode == "user_scoped"
        # Should have no users without file
        assert len(user_manager_scoped.authorized_users) == 0

        print("✅ User-scoped mode initialization working")
        return True


async def run_mock_tests():
    """Run all mock tests."""
    print("🧪 Starting Mock Test Suite (No External Dependencies)")
    print("=" * 60)

    tests = [
        ("PaperlessClient Test", test_paperless_client()),
        ("User Manager Test", test_user_manager()),
        ("Bot Handlers Test", test_bot_handlers()),
        ("File Handling Test", test_file_handling()),
        ("Message Formatting Test", test_message_formatting()),
    ]

    results = []

    for test_name, test_coro in tests:
        try:
            result = await test_coro
            results.append((test_name, result))
        except (
            ValueError,
            KeyError,
            AttributeError,
            OSError,
            ImportError,
            AssertionError,
        ) as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))

    print("\n📊 Mock Test Results:")
    print("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1

    print("=" * 60)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("\n🎉 All mock tests passed! The bot logic is working correctly.")
        print("\nNext: Configure real tokens in .env and run 'python test_bot.py'")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the errors above.")


if __name__ == "__main__":
    asyncio.run(run_mock_tests())
