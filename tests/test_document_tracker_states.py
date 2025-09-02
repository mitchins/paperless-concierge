#!/usr/bin/env python3
import os
import sys
import pytest
from unittest.mock import AsyncMock, Mock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


@pytest.mark.asyncio
async def test_add_document_with_immediate_status_success():
    from paperless_concierge.document_tracker import DocumentTracker

    tracker = DocumentTracker(Mock())
    client = Mock()

    tracker.add_document(
        task_id="t1",
        user_id=1,
        chat_id=1,
        filename="f.pdf",
        paperless_client=client,
        immediate_status={"status": "SUCCESS", "document_id": 99},
        tracking_uuid="u-1",
    )
    doc = tracker.tracked_documents["t1"]
    assert doc.document_id == 99
    assert doc.status == "paperless_indexing"


@pytest.mark.asyncio
async def test_handle_processing_state_moves_to_waiting():
    from paperless_concierge.document_tracker import DocumentTracker, TrackedDocument

    tracker = DocumentTracker(Mock())
    doc = TrackedDocument(
        task_id="t2",
        user_id=1,
        chat_id=1,
        filename="f.pdf",
        upload_time=__import__("datetime").datetime.now(),
        paperless_client=Mock(),
    )

    # Make client.get_document_status raise Not found
    async def _raise(*_a, **_k):
        raise ValueError("Not found")

    doc.paperless_client.get_document_status = AsyncMock(side_effect=_raise)
    await tracker._handle_processing_state("t2", doc)
    assert doc.status == "waiting_for_consumption"


@pytest.mark.asyncio
async def test_handle_waiting_for_consumption_found_by_uuid(monkeypatch):
    from paperless_concierge.document_tracker import DocumentTracker, TrackedDocument

    tracker = DocumentTracker(Mock())
    doc = TrackedDocument(
        task_id="t3",
        user_id=1,
        chat_id=1,
        filename="f.pdf",
        upload_time=__import__("datetime").datetime.now(),
        paperless_client=Mock(),
        tracking_uuid="uuid-123",
    )

    async def _find_uuid(_client, _uuid):
        return 77

    monkeypatch.setattr(
        tracker, "_find_document_by_uuid", AsyncMock(side_effect=_find_uuid)
    )
    done = await tracker._handle_waiting_for_consumption_state("t3", doc)
    assert done is False
    assert doc.status == "paperless_indexing"
    assert doc.document_id == 77


@pytest.mark.asyncio
async def test_handle_waiting_for_consumption_timeout(monkeypatch):
    from paperless_concierge.document_tracker import DocumentTracker, TrackedDocument
    from paperless_concierge.constants import CONSUMPTION_TIMEOUT

    tracker = DocumentTracker(Mock())
    doc = TrackedDocument(
        task_id="t4",
        user_id=1,
        chat_id=1,
        filename="f.pdf",
        upload_time=__import__("datetime").datetime.now(),
        paperless_client=Mock(),
    )
    # Force near-timeout and ensure no doc found
    doc.retry_count = CONSUMPTION_TIMEOUT - 1
    monkeypatch.setattr(
        tracker,
        "_find_recent_document_by_filename",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(tracker, "_send_basic_success_notification", AsyncMock())
    done = await tracker._handle_waiting_for_consumption_state("t4", doc)
    assert done is True


@pytest.mark.asyncio
async def test_handle_paperless_indexing_state_ready(monkeypatch):
    from paperless_concierge.document_tracker import DocumentTracker, TrackedDocument

    tracker = DocumentTracker(Mock())
    doc = TrackedDocument(
        task_id="t5",
        user_id=1,
        chat_id=1,
        filename="f.pdf",
        upload_time=__import__("datetime").datetime.now(),
        paperless_client=Mock(),
    )
    monkeypatch.setattr(tracker, "_is_document_ready", AsyncMock(return_value=True))
    done = await tracker._handle_paperless_indexing_state(doc)
    assert done is False
    assert doc.status == "triggering_ai"


@pytest.mark.asyncio
async def test_handle_triggering_ai_state_paths(monkeypatch):
    from paperless_concierge.document_tracker import DocumentTracker, TrackedDocument
    from paperless_concierge.constants import AI_TRIGGER_MAX_RETRIES

    tracker = DocumentTracker(Mock())
    # Case 1: AI configured, trigger fails until max retries -> basic success
    doc = TrackedDocument(
        task_id="t6",
        user_id=1,
        chat_id=1,
        filename="f.pdf",
        upload_time=__import__("datetime").datetime.now(),
        paperless_client=Mock(),
        document_id=5,
    )
    doc.paperless_client.ai_url = "http://ai"
    doc.retry_count = AI_TRIGGER_MAX_RETRIES - 1
    doc.paperless_client.trigger_ai_processing = AsyncMock(return_value=False)
    monkeypatch.setattr(tracker, "_send_basic_success_notification", AsyncMock())
    assert await tracker._handle_triggering_ai_state(doc) is True

    # Case 2: No AI configured -> immediate success notification
    doc2 = TrackedDocument(
        task_id="t7",
        user_id=1,
        chat_id=1,
        filename="f.pdf",
        upload_time=__import__("datetime").datetime.now(),
        paperless_client=Mock(),
        document_id=6,
    )
    doc2.paperless_client.ai_url = None
    monkeypatch.setattr(tracker, "_send_success_notification", AsyncMock())
    assert await tracker._handle_triggering_ai_state(doc2) is True
