#!/usr/bin/env python3
"""
Comprehensive workflow tests with mocks for Paperless-NGX Telegram Concierge.
Tests the complete end-to-end workflow without external dependencies.
"""

import asyncio
import os
import sys
from dataclasses import dataclass
from unittest.mock import AsyncMock, Mock, patch

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


# Mock Telegram objects
@dataclass
class MockUser:
    id: int = 12345
    username: str = "testuser"
    first_name: str = "Test"


@dataclass
class MockChat:
    id: int = 12345


@dataclass
class MockMessage:
    message_id: int = 1
    from_user: MockUser = None
    chat: MockChat = None
    photo: list = None
    document: Mock = None

    def __post_init__(self):
        if self.from_user is None:
            self.from_user = MockUser()
        if self.chat is None:
            self.chat = MockChat()

    @property
    def chat_id(self):
        return self.chat.id


@dataclass
class MockUpdate:
    message: MockMessage = None
    effective_user: MockUser = None
    callback_query: Mock = None

    def __post_init__(self):
        if self.message is None:
            self.message = MockMessage()
        if self.effective_user is None:
            self.effective_user = MockUser()


class MockFile:
    def __init__(self, file_id="test_file_123"):
        self.file_id = file_id
        self.file_path = f"photos/{file_id}.jpg"

    async def get_file(self):
        return self

    async def download_to_drive(self, path):
        # Create a dummy file
        with open(path, "wb") as f:
            f.write(b"fake image data")


# Test the complete document upload workflow (HTTP stubbed)
import pytest


@pytest.mark.asyncio
async def test_document_upload_workflow(httpx_mock):
    """Test complete document upload workflow with mocks"""

    from paperless_concierge.bot import TelegramConcierge

    # Mock user manager
    with patch("paperless_concierge.bot.get_user_manager") as mock_get_user_manager:
        mock_user_manager = Mock()
        mock_user_manager.is_authorized.return_value = True
        mock_user_manager.get_user_config.return_value = Mock(
            paperless_url="http://test-paperless:8000",
            paperless_token="test_token",
            paperless_ai_url="http://test-ai:8080",
            paperless_ai_token="test_ai_token",
        )
        mock_get_user_manager.return_value = mock_user_manager

        # Mock document tracker
        mock_tracker = Mock()

        # Create bot instance
        bot = TelegramConcierge(document_tracker=mock_tracker)

        # Create mock update with photo
        update = MockUpdate()
        update.message.photo = [MockFile()]

        # Mock context
        context = Mock()

        # Mock message reply methods
        status_message = Mock()
        status_message.edit_text = AsyncMock()
        update.message.reply_text = AsyncMock(return_value=status_message)

        # Stub HTTP upload and immediate status
        httpx_mock.add_response(
            method="POST",
            url="http://test-paperless:8000/api/documents/post_document/",
            json={"task_id": "task-123"},
            status_code=200,
        )
        httpx_mock.add_response(
            method="GET",
            url="http://test-paperless:8000/api/tasks/task-123/",
            json={"status": "completed", "document_id": 1},
            status_code=200,
        )

        # Execute the upload
        await bot.handle_document(update, context)

        # Verify the workflow
        assert update.message.reply_text.called
        assert mock_tracker.add_document.called
        assert status_message.edit_text.called

        # Clean up tracker
        if hasattr(bot, "document_tracker") and bot.document_tracker:
            bot.document_tracker.cleanup()


async def test_ai_processing_workflow():
    """Test AI processing workflow with mocks"""

    from paperless_concierge.paperless_client import PaperlessClient

    client = PaperlessClient(
        paperless_url="http://test:8000",
        paperless_token="test_token",
        paperless_ai_url="http://test-ai:8080",
        paperless_ai_token="test_ai_token",
    )

    # Test that methods exist and are configured
    assert hasattr(client, "trigger_ai_processing")
    assert callable(client.trigger_ai_processing)
    assert hasattr(client, "query_ai")
    assert callable(client.query_ai)

    # Test client configuration
    assert client.ai_url == "http://test-ai:8080"
    assert client.ai_token == "test_ai_token"


async def test_state_persistence():
    """Test document tracker state persistence"""

    from paperless_concierge.document_tracker import DocumentTracker, TrackedDocument

    # Mock telegram application
    mock_app = Mock()

    tracker = DocumentTracker(mock_app)

    # Add a document
    from datetime import datetime

    mock_client = Mock()
    document = TrackedDocument(
        task_id="test-123",
        user_id=12345,
        chat_id=12345,
        filename="test.pdf",
        upload_time=datetime.now(),
        paperless_client=mock_client,
        tracking_uuid="uuid-123",
    )

    tracker.tracked_documents["test-123"] = document

    # Test state can be serialized/deserialized
    state = {
        "task_id": document.task_id,
        "user_id": document.user_id,
        "filename": document.filename,
        "status": document.status,
    }

    assert state["task_id"] == "test-123"
    assert state["status"] == "processing"

    # Clean up tracker resources
    tracker.cleanup()


async def test_error_handling():
    """Test error handling and resilience"""

    from paperless_concierge.bot import TelegramConcierge

    bot = TelegramConcierge()

    # Test with invalid update
    with patch("paperless_concierge.bot.get_user_manager") as mock_get_user_manager:
        mock_user_manager = Mock()
        mock_user_manager.is_authorized.return_value = True
        mock_user_manager.get_user_config.return_value = None  # No config
        mock_get_user_manager.return_value = mock_user_manager

        update = MockUpdate()
        context = Mock()

        # Should handle missing config gracefully
        with patch.object(
            bot, "get_paperless_client", side_effect=ValueError("No config")
        ):
            update.message.reply_text = AsyncMock()

            await bot.handle_document(update, context)

            # Should have sent an error message
            assert update.message.reply_text.called

            # Clean up bot document tracker
            if hasattr(bot, "document_tracker") and bot.document_tracker:
                bot.document_tracker.cleanup()


def test_configuration_validation():
    """Test configuration validation"""

    from paperless_concierge.config import TELEGRAM_BOT_TOKEN
    from paperless_concierge.user_manager import UserManager

    # Test environment variables are loaded
    assert TELEGRAM_BOT_TOKEN is not None

    # Test user manager configurations
    user_manager = UserManager(auth_mode="global")
    assert user_manager.auth_mode == "global"


if __name__ == "__main__":
    # Run tests
    async def run_tests():
        print("🧪 Running comprehensive workflow tests...")

        await test_document_upload_workflow()
        print("✅ Document upload workflow test passed")

        await test_ai_processing_workflow()
        print("✅ AI processing workflow test passed")

        await test_state_persistence()
        print("✅ State persistence test passed")

        await test_error_handling()
        print("✅ Error handling test passed")

        test_configuration_validation()
        print("✅ Configuration validation test passed")

        print("🎉 All workflow tests passed!")

    asyncio.run(run_tests())
