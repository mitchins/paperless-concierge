#!/usr/bin/env python3
import os
import sys
import pytest
from unittest.mock import Mock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


pytestmark = pytest.mark.asyncio


async def test_check_ai_processing_builds_metadata(httpx_mock):
    from paperless_concierge.document_tracker import DocumentTracker, TrackedDocument

    tracker = DocumentTracker(Mock())
    doc = TrackedDocument(
        task_id="ta",
        user_id=1,
        chat_id=1,
        filename="f.pdf",
        upload_time=__import__("datetime").datetime.now(),
        paperless_client=Mock(base_url="http://test:8000", token="tkn"),
        document_id=10,
    )

    # Document details with tags, correspondent, type and content
    httpx_mock.add_response(
        method="GET",
        url="http://test:8000/api/documents/10/",
        json={
            "title": "Doc",
            "tags": [1, 2],
            "correspondent": 3,
            "document_type": 4,
            "content": "Some OCR content",
        },
        status_code=200,
    )
    # Tags list
    httpx_mock.add_response(
        method="GET",
        url="http://test:8000/api/tags/",
        json={"results": [{"id": 1, "name": "Tag1"}, {"id": 2, "name": "Tag2"}]},
        status_code=200,
    )
    # Correspondent
    httpx_mock.add_response(
        method="GET",
        url="http://test:8000/api/correspondents/3/",
        json={"name": "Alice"},
        status_code=200,
    )
    # Type
    httpx_mock.add_response(
        method="GET",
        url="http://test:8000/api/document_types/4/",
        json={"name": "Invoice"},
        status_code=200,
    )

    ai = await tracker._check_ai_processing(doc)
    assert ai is not None
    assert ai["tags"] == ["Tag1", "Tag2"]
    assert ai["correspondent"] == "Alice"
    assert ai["document_type"] == "Invoice"


async def test_is_document_ready_true(httpx_mock, monkeypatch):
    from paperless_concierge.document_tracker import DocumentTracker, TrackedDocument

    tracker = DocumentTracker(Mock())
    doc = TrackedDocument(
        task_id="tb",
        user_id=1,
        chat_id=1,
        filename="f.pdf",
        upload_time=__import__("datetime").datetime.now(),
        paperless_client=Mock(base_url="http://test:8000", token="tkn"),
        document_id=11,
    )

    # First GET document/{id}
    httpx_mock.add_response(
        method="GET",
        url="http://test:8000/api/documents/11/",
        json={
            "content": "text",
            "created": "2024-01-01T00:00:00Z",
            "checksum": "x",
            "file_type": "pdf",
        },
        status_code=200,
    )
    # Recent documents include id=11 (must match params order)
    httpx_mock.add_response(
        method="GET",
        url="http://test:8000/api/documents/?page=1&page_size=50&ordering=-created&truncate_content=true",
        json={"results": [{"id": 11}]},
        status_code=200,
    )

    ok = await tracker._is_document_ready(doc)
    assert ok is True


@pytest.mark.asyncio
async def test_is_document_ready_recent_docs_error(httpx_mock):
    from paperless_concierge.document_tracker import DocumentTracker, TrackedDocument

    tracker = DocumentTracker(Mock())
    doc = TrackedDocument(
        task_id="tc",
        user_id=1,
        chat_id=1,
        filename="f.pdf",
        upload_time=__import__("datetime").datetime.now(),
        paperless_client=Mock(base_url="http://test:8000", token="tkn"),
        document_id=12,
    )

    # First document GET is OK with content/created
    httpx_mock.add_response(
        method="GET",
        url="http://test:8000/api/documents/12/",
        json={"content": "text", "created": "2024-01-01T00:00:00Z"},
        status_code=200,
    )
    # Recent documents request fails with 500 to hit the warning branch
    httpx_mock.add_response(
        method="GET",
        url="http://test:8000/api/documents/?page=1&page_size=50&ordering=-created&truncate_content=true",
        status_code=500,
        json={"error": "server"},
    )

    ok = await tracker._is_document_ready(doc)
    assert ok is False
