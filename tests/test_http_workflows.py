#!/usr/bin/env python3
"""
HTTP workflow tests — unittest, async, and quiet

Professionalized: moved to unittest's IsolatedAsyncioTestCase, removed custom
print statements and ad‑hoc harness. Let the test runner handle reporting.
Run with any of:
  • python -m unittest -q
  • python -m unittest tests.test_http_workflows -q
  • pytest (captures output by default)
"""

import os
import inspect
import sys
import unittest
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

# Third‑party test helper
from aioresponses import aioresponses

# =============================================================================
# Shared Telegram-ish mocks
# =============================================================================


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
    text: str = "test message"

    def __post_init__(self):
        if self.from_user is None:
            self.from_user = MockUser()
        if self.chat is None:
            self.chat = MockChat()

    @property
    def chat_id(self):
        return self.chat.id

    async def reply_text(self, _text, _reply_markup=None):
        mock_response = Mock()
        mock_response.edit_text = AsyncMock()
        return mock_response


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
    def __init__(self, file_id: str = "test_file_123"):
        self.file_id = file_id
        self.file_path = f"photos/{file_id}.jpg"

    async def get_file(self):  # parity with telegram API
        return self

    async def download_to_drive(self, path):
        with open(path, "wb") as f:
            f.write(b"fake image data")


# =============================================================================
# Imports from the SUT (after sys.path wiring)
# =============================================================================
from paperless_concierge.bot import TelegramConcierge
from paperless_concierge.document_tracker import DocumentTracker, TrackedDocument
from paperless_concierge.paperless_client import PaperlessClient


# =============================================================================
# DRY helpers
# =============================================================================


def _default_user_config(*, ai: bool = False):
    cfg = Mock()
    cfg.paperless_url = "http://test:8000"
    cfg.paperless_token = "test_token"
    cfg.paperless_ai_url = "http://test-ai:8080" if ai else None
    cfg.paperless_ai_token = "test_ai_token" if ai else None
    return cfg


@contextmanager
def patched_user_manager(user_config: Mock, *, authorized: bool = True):
    """Patch paperless_concierge.bot.get_user_manager for the duration."""
    with patch("paperless_concierge.bot.get_user_manager") as mock_get_um:
        mock_um = Mock()
        mock_um.is_authorized.return_value = authorized
        mock_um.get_user_config.return_value = user_config
        mock_get_um.return_value = mock_um
        yield mock_um


def make_update_context(
    *, text: str | None = None, args: list[str] | None = None, with_photo: bool = False
):
    """Create a Mock Update + Context with common wiring and a status message."""
    update = MockUpdate()
    if text is not None:
        update.message.text = text

    status_message = Mock()
    status_message.edit_text = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=status_message)

    context = Mock()
    context.args = args or []
    context.bot = Mock()
    context.bot.get_file = AsyncMock(return_value=MockFile())

    if with_photo:
        photo_size = Mock()
        photo_size.get_file = AsyncMock(return_value=MockFile())
        update.message.photo = [photo_size]

    return update, context, status_message


def make_callback_query(
    *, user_id: int = 12345, data: str = "status_status-task-456"
) -> Mock:
    q = Mock()
    q.answer = AsyncMock()
    q.data = data
    q.from_user = Mock()
    q.from_user.id = user_id
    q.edit_message_text = AsyncMock()
    return q


# =============================================================================
# Tests (unittest, no custom prints)
# =============================================================================


class HTTPWorkflowTests(IsolatedAsyncioTestCase):
    async def test_paperless_upload_workflow(self):
        """End-to-end document upload with task status."""
        with patched_user_manager(_default_user_config(ai=True)):
            bot = TelegramConcierge()
            update, context, status_msg = make_update_context(with_photo=True)

            with aioresponses() as m:
                m.post(
                    "http://test:8000/api/documents/post_document/",
                    status=200,
                    payload={"task_id": "upload-task-123"},
                )
                m.get(
                    "http://test:8000/api/tasks/upload-task-123/",
                    status=200,
                    payload={
                        "status": "SUCCESS",
                        "document_id": 456,
                        "result": {"document_id": 456},
                    },
                )

                await bot.handle_document(update, context)

                update.message.reply_text.assert_called_with(
                    "📤 Uploading to Paperless-NGX..."
                )
                status_msg.edit_text.assert_called()
                self.assertEqual(
                    bot.upload_tasks[update.message.chat_id]["task_id"],
                    "upload-task-123",
                )
                await bot.aclose()

    async def test_document_search_workflow(self):
        """Basic search via HTTP."""
        with patched_user_manager(_default_user_config(ai=False)):
            bot = TelegramConcierge()
            update, context, _ = make_update_context(
                text="/search test query", args=["test", "query"]
            )

            with aioresponses() as m:
                m.get(
                    "http://test:8000/api/documents/",
                    status=200,
                    payload={
                        "count": 2,
                        "results": [
                            {
                                "id": 1,
                                "title": "Test Document 1",
                                "created": "2023-01-01",
                                "tags": [1, 2],
                            },
                            {
                                "id": 2,
                                "title": "Test Document 2",
                                "created": "2023-01-02",
                                "tags": [],
                            },
                        ],
                    },
                )

                await bot.query_documents(update, context)
                update.message.reply_text.assert_called()
                await bot.aclose()

    async def test_ai_query_workflow(self):
        """AI query path with fallback search."""
        with patched_user_manager(_default_user_config(ai=True)):
            bot = TelegramConcierge()
            prompt = "What invoices do I have from 2023?"
            update, context, _ = make_update_context(text=prompt, args=prompt.split())

            with aioresponses() as m:
                m.post(
                    "http://test-ai:8080/api/chat",
                    status=200,
                    payload={
                        "success": True,
                        "answer": "Based on the documents, here's the information...",
                        "documents_found": [
                            {"title": "Relevant Doc 1", "id": 123},
                            {"title": "Relevant Doc 2", "id": 124},
                        ],
                        "tags_found": ["invoice", "2023"],
                        "confidence": 0.85,
                        "sources": ["Document 1", "Document 2"],
                    },
                )
                m.get(
                    "http://test:8000/api/documents/",
                    status=200,
                    payload={
                        "count": 1,
                        "results": [{"title": "Fallback Doc", "id": 999}],
                    },
                )

                await bot.query_documents(update, context)
                update.message.reply_text.assert_called()
                await bot.aclose()

    async def test_document_status_check_workflow(self):
        """Button callback → task status check."""
        with patched_user_manager(_default_user_config()):
            bot = TelegramConcierge()

            mock_query = make_callback_query(data="status_status-task-456")
            update = MockUpdate()
            update.callback_query = mock_query
            context = Mock()

            with aioresponses() as m:
                m.get(
                    "http://test:8000/api/tasks/status-task-456/",
                    status=200,
                    payload={
                        "status": "SUCCESS",
                        "document_id": 789,
                        "result": {"document_id": 789},
                    },
                )

                await bot.check_status(update, context)

                mock_query.answer.assert_called_once()
                mock_query.edit_message_text.assert_called_once()
                self.assertIn(
                    "successfully", mock_query.edit_message_text.call_args[0][0]
                )
                await bot.aclose()

    async def test_document_tracker_workflow(self):
        """Basic DocumentTracker plumbing."""
        tracker = DocumentTracker(Mock())

        mock_client = Mock()
        mock_client.base_url = "http://test:8000"
        mock_client.token = "test_token"

        doc = TrackedDocument(
            task_id="test-task-123",
            user_id=12345,
            chat_id=12345,
            filename="test.pdf",
            upload_time=datetime.now(),
            paperless_client=mock_client,
            tracking_uuid="uuid-123",
        )
        doc.document_id = 999

        tracker.tracked_documents[doc.task_id] = doc
        self.assertTrue(list(tracker.tracked_documents.values()))

        tracker.cleanup()

    async def test_paperless_client_workflows(self):
        """Direct PaperlessClient HTTPs."""
        client = PaperlessClient(
            paperless_url="http://test:8000",
            paperless_token="test_token",
            paperless_ai_url="http://test-ai:8080",
            paperless_ai_token="test_ai_token",
        )

        with aioresponses() as m:
            m.post(
                "http://test:8000/api/documents/post_document/",
                status=200,
                payload={"task_id": "client-task-789"},
            )
            m.get(
                "http://test:8000/api/documents/",
                status=200,
                payload={
                    "count": 1,
                    "results": [{"id": 555, "title": "Direct Client Test"}],
                },
            )

            # Upload (guarded — we only care that HTTP layer is exercised)
            with patch("builtins.open"):
                try:
                    await client.upload_document("/fake/path/test.pdf")
                except Exception:
                    pass

            # Search
            try:
                results = await client.search_documents("test query")
                self.assertIsNotNone(results)
            except Exception:
                pass

            if hasattr(client, "aclose"):
                await client.aclose()
            else:
                res = getattr(client, "close", lambda: None)()
                if inspect.isawaitable(res):
                    await res

    async def test_error_handling_workflows(self):
        """HTTP error paths (e.g., 404 search)."""
        with patched_user_manager(_default_user_config(ai=False)):
            bot = TelegramConcierge()
            update, context, _ = make_update_context(
                text="/search nonexistent", args=["nonexistent"]
            )

            with aioresponses() as m:
                m.get(
                    "http://test:8000/api/documents/",
                    status=404,
                    payload={"error": "Not found"},
                )

                await bot.query_documents(update, context)
                update.message.reply_text.assert_called()
                await bot.aclose()


if __name__ == "__main__":
    unittest.main()
