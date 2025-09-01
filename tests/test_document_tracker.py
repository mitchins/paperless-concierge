#!/usr/bin/env python3
"""
Unit tests for DocumentTracker class functionality.
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


async def test_document_tracker_initialization():
    """Test DocumentTracker initialization"""
    print("Testing DocumentTracker initialization...")

    from paperless_concierge.document_tracker import DocumentTracker

    mock_app = Mock()
    tracker = DocumentTracker(mock_app)

    # Test basic properties
    assert tracker.tracked_documents == {}
    assert tracker.bot == mock_app

    # Test document list retrieval
    docs = list(tracker.tracked_documents.values())
    assert isinstance(docs, list)

    # Cleanup
    tracker.cleanup()


async def test_tracked_document_dataclass():
    """Test TrackedDocument dataclass functionality"""
    print("Testing TrackedDocument dataclass...")

    from paperless_concierge.document_tracker import TrackedDocument
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

    assert document.task_id == "test-123"
    assert document.user_id == 12345
    assert document.filename == "test.pdf"
    assert document.paperless_client == mock_client


async def run_document_tracker_tests():
    """Run all DocumentTracker tests"""
    print("📊 Running DocumentTracker Tests...")
    print("=" * 50)

    tests = [
        test_document_tracker_initialization,
        test_tracked_document_dataclass,
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
    print(f"DocumentTracker Tests: {passed}/{total} passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_document_tracker_tests())
    sys.exit(0 if success else 1)
