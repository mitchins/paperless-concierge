#!/usr/bin/env python3
"""
HTTP boundary tests for PaperlessClient using pytest-httpx.
These exercise real httpx.AsyncClient calls with stubbed responses,
so we validate URLs, headers, and avoid real sockets.
"""

import os
import sys
import json
import asyncio
import tempfile

import pytest

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from paperless_concierge.paperless_client import PaperlessClient


pytestmark = pytest.mark.asyncio


async def test_upload_document_ok(httpx_mock, tmp_path):
    client = PaperlessClient(
        paperless_url="http://test:8000",
        paperless_token="tkn",
    )

    # Prepare temp file as upload source
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"hello")

    # Stub POST endpoint
    httpx_mock.add_response(
        method="POST",
        url="http://test:8000/api/documents/post_document/",
        json={"task_id": "task-1"},
        status_code=200,
    )

    result = await client.upload_document(str(p), title="doc.pdf")
    assert result.get("task_id") == "task-1"

    # Verify request basics
    req = httpx_mock.get_requests()[0]
    assert req.method == "POST"
    assert req.url == "http://test:8000/api/documents/post_document/"
    assert req.headers.get("Authorization") == "Token tkn"


async def test_get_document_status_ok(httpx_mock):
    c = PaperlessClient(paperless_url="http://test:8000", paperless_token="tkn")

    httpx_mock.add_response(
        method="GET",
        url="http://test:8000/api/tasks/abc-123/",
        json={"status": "SUCCESS", "document_id": 42},
        status_code=200,
    )

    data = await c.get_document_status("abc-123")
    assert data["status"] == "SUCCESS"
    assert data["document_id"] == 42


async def test_get_document_status_not_found(httpx_mock):
    c = PaperlessClient(paperless_url="http://test:8000", paperless_token="tkn")

    httpx_mock.add_response(
        method="GET",
        url="http://test:8000/api/tasks/missing/",
        status_code=404,
        json={"detail": "Not found"},
    )

    import pytest
    from paperless_concierge.exceptions import PaperlessTaskNotFoundError

    with pytest.raises(PaperlessTaskNotFoundError):
        await c.get_document_status("missing")


async def test_search_documents_ok(httpx_mock):
    c = PaperlessClient(paperless_url="http://test:8000", paperless_token="tkn")

    httpx_mock.add_response(
        method="GET",
        url="http://test:8000/api/documents/?query=invoice",
        json={"count": 1, "results": [{"id": 1, "title": "T"}]},
        status_code=200,
    )

    data = await c.search_documents("invoice")
    assert data["count"] == 1
    assert data["results"][0]["title"] == "T"


async def test_query_ai_success_parsing(httpx_mock):
    c = PaperlessClient(
        paperless_url="http://test:8000",
        paperless_token="tkn",
        paperless_ai_url="http://ai:8080",
        paperless_ai_token="ai-key",
    )

    httpx_mock.add_response(
        method="POST",
        url="http://ai:8080/api/chat",
        json={
            "answer": "Hello",
            "sources": [1],
            "documents": [{"title": "D"}],
            "tags": ["A"],
            "confidence": 0.9,
        },
        status_code=200,
    )

    parsed = await c.query_ai("hi")
    assert parsed["success"] is True
    assert parsed["answer"] == "Hello"
    assert parsed["documents_found"][0]["title"] == "D"


async def test_query_ai_temporarily_unavailable(httpx_mock):
    c = PaperlessClient(
        paperless_url="http://test:8000",
        paperless_token="tkn",
        paperless_ai_url="http://ai:8080",
        paperless_ai_token="ai-key",
    )

    # All endpoints return 404
    for path in ["/api/chat", "/api/query", "/chat", "/query"]:
        httpx_mock.add_response(
            method="POST",
            url=f"http://ai:8080{path}",
            status_code=404,
            json={"error": "not found"},
        )

    parsed = await c.query_ai("hi")
    assert parsed["success"] is False
    assert "temporarily unavailable" in parsed["error"].lower()


async def test_trigger_ai_processing_success(httpx_mock):
    c = PaperlessClient(
        paperless_url="http://test:8000",
        paperless_token="t",
        paperless_ai_url="http://ai:8080",
        paperless_ai_token="k",
    )

    httpx_mock.add_response(
        method="POST",
        url="http://ai:8080/api/scan/now",
        status_code=200,
        json={"ok": True},
    )
    httpx_mock.add_response(
        method="GET",
        url="http://ai:8080/api/processing-status",
        status_code=200,
        json={"lastProcessed": {"documentId": 123, "title": "Doc"}},
    )

    ok = await c.trigger_ai_processing(123)
    assert ok is True


async def test_trigger_ai_document_processing_fallback(httpx_mock):
    c = PaperlessClient(
        paperless_url="http://test:8000",
        paperless_token="t",
        paperless_ai_url="http://ai:8080",
        paperless_ai_token="k",
    )

    # Make scan/now fail so fallback path is exercised
    httpx_mock.add_response(
        method="POST",
        url="http://ai:8080/api/scan/now",
        status_code=500,
        json={"error": "fail"},
    )
    # Fallback: process specific document via POST /api/process/{id}
    httpx_mock.add_response(
        method="POST",
        url="http://ai:8080/api/process/123",
        status_code=200,
        json={"ok": True},
    )

    ok = await c.trigger_ai_processing(123)
    assert ok is True
