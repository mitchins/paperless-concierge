#!/usr/bin/env python3
"""
Test search result formatting edge cases, especially empty results and type issues.
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from paperless_concierge.bot import TelegramConcierge
from paperless_concierge.paperless_client import PaperlessClient


class TestSearchFormatting:
    """Test search result formatting methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.bot = TelegramConcierge()
        # Mock paperless client
        self.mock_client = Mock(spec=PaperlessClient)
        self.mock_client.base_url = "https://paperless.example.com"

    def test_format_ai_response_with_integer_tags(self):
        """Test that AI responses with integer tag IDs are handled properly."""
        ai_response = {
            "answer": "Found some invoices from 2023.",
            "tags_found": [1, 2, 3, 4, 5],  # Integer tag IDs
            "success": True,
        }

        result = self.bot._format_ai_response(ai_response)

        # Should convert integers to strings and join them
        assert "1, 2, 3, 4, 5" in result
        assert "🏷️ **Related Tags:**" in result
        assert "Found some invoices from 2023." in result

    def test_format_ai_response_with_dict_tags(self):
        """Test that AI responses with tag dictionaries are handled properly."""
        ai_response = {
            "answer": "Found some invoices.",
            "tags_found": [
                {"name": "invoice", "id": 1},
                {"label": "important", "id": 2},
                {"id": 3},  # No name or label
            ],
            "success": True,
        }

        result = self.bot._format_ai_response(ai_response)

        # Should extract names/labels from dicts
        assert "invoice, important" in result
        assert "🏷️ **Related Tags:**" in result

    def test_format_ai_response_with_mixed_tag_types(self):
        """Test that AI responses with mixed tag types are handled properly."""
        ai_response = {
            "answer": "Found some documents.",
            "tags_found": [
                "string_tag",
                42,  # Integer
                {"name": "dict_tag", "id": 1},
                {"label": "labeled_tag", "id": 2},
            ],
            "success": True,
        }

        result = self.bot._format_ai_response(ai_response)

        # Should handle all types
        assert "string_tag, 42, dict_tag, labeled_tag" in result
        assert "🏷️ **Related Tags:**" in result

    def test_format_ai_response_with_empty_tags(self):
        """Test that AI responses with empty tags list don't crash."""
        ai_response = {
            "answer": "No documents found with relevant tags.",
            "tags_found": [],
            "success": True,
        }

        result = self.bot._format_ai_response(ai_response)

        # Should not include tags section
        assert "🏷️ **Related Tags:**" not in result
        assert "No documents found with relevant tags." in result

    def test_format_ai_response_with_no_tags_key(self):
        """Test that AI responses without tags_found key don't crash."""
        ai_response = {"answer": "Found some documents.", "success": True}

        result = self.bot._format_ai_response(ai_response)

        # Should not include tags section
        assert "🏷️ **Related Tags:**" not in result
        assert "Found some documents." in result

    def test_format_search_results_with_integer_tags(self):
        """Test that regular search results with integer tags are handled properly."""
        search_results = {
            "count": 1,
            "results": [
                {
                    "title": "Test Document",
                    "created": "2023-01-01T00:00:00Z",
                    "tags": [1, 2, 3],  # Integer tag IDs
                }
            ],
        }

        result = self.bot._format_search_results(search_results)

        # Should convert integers to strings
        assert "[Tags: 1, 2, 3]" in result
        assert "Test Document" in result

    def test_format_search_results_with_dict_tags(self):
        """Test that search results with tag dictionaries are handled properly."""
        search_results = {
            "count": 1,
            "results": [
                {
                    "title": "Test Document",
                    "created": "2023-01-01T00:00:00Z",
                    "tags": [
                        {"name": "invoice", "id": 1},
                        {"label": "important", "id": 2},
                    ],
                }
            ],
        }

        result = self.bot._format_search_results(search_results)

        # Should extract names/labels from dicts
        assert "[Tags: invoice, important]" in result
        assert "Test Document" in result

    def test_format_search_results_empty_results(self):
        """Test that empty search results are handled properly."""
        search_results = {"count": 0, "results": []}

        result = self.bot._format_search_results(search_results)

        # Should handle empty results gracefully
        assert "Found 0 documents:" in result
        assert not result.endswith("... and")  # No "more documents" message

    def test_format_search_results_no_tags(self):
        """Test that documents without tags are handled properly."""
        search_results = {
            "count": 1,
            "results": [
                {
                    "title": "Test Document",
                    "created": "2023-01-01T00:00:00Z",
                    "tags": [],  # Empty tags
                }
            ],
        }

        result = self.bot._format_search_results(search_results)

        # Should not include tag section
        assert "[Tags:" not in result
        assert "Test Document" in result

    def test_build_document_url(self):
        """Test document URL building."""
        url = self.bot._build_document_url(self.mock_client, 123)
        assert url == "https://paperless.example.com/documents/123/"

    def test_build_document_url_with_trailing_slash(self):
        """Test document URL building with trailing slash in base URL."""
        self.mock_client.base_url = "https://paperless.example.com/"
        url = self.bot._build_document_url(self.mock_client, 456)
        assert url == "https://paperless.example.com/documents/456/"

    def test_format_ai_response_with_document_links(self):
        """Test that AI responses include document links when IDs are available."""
        ai_response = {
            "answer": "Found some invoices from 2023.",
            "documents_found": [
                {"title": "Invoice Jan 2023", "id": 101},
                {"title": "Invoice Feb 2023", "id": 102},
                {"title": "Invoice Mar 2023", "name": "March Invoice"},  # No ID
            ],
            "success": True,
        }

        result = self.bot._format_ai_response(ai_response, self.mock_client)

        # Should include document links for documents with IDs
        assert (
            "[Invoice Jan 2023](https://paperless.example.com/documents/101/)" in result
        )
        assert (
            "[Invoice Feb 2023](https://paperless.example.com/documents/102/)" in result
        )
        # Should not include link for document without ID
        assert "Invoice Mar 2023" in result
        assert "documents/March" not in result

    def test_format_ai_response_without_client(self):
        """Test AI response formatting without client (no links)."""
        ai_response = {
            "answer": "Found some invoices.",
            "documents_found": [{"title": "Invoice Jan 2023", "id": 101}],
            "success": True,
        }

        result = self.bot._format_ai_response(ai_response)

        # Should not include links without client
        assert "Invoice Jan 2023" in result
        assert "documents/101" not in result
        assert "[" not in result or "](" not in result

    def test_format_search_results_with_document_links(self):
        """Test that search results include document links."""
        search_results = {
            "count": 2,
            "results": [
                {
                    "title": "Test Document 1",
                    "created": "2023-01-01T00:00:00Z",
                    "id": 201,
                    "tags": [],
                },
                {
                    "title": "Test Document 2",
                    "created": "2023-01-02T00:00:00Z",
                    "tags": []
                    # No ID field
                },
            ],
        }

        result = self.bot._format_search_results(search_results, self.mock_client)

        # Should include link for first document
        assert (
            "[Test Document 1](https://paperless.example.com/documents/201/)" in result
        )
        # Should not include link for second document (no ID)
        assert "Test Document 2" in result
        assert "documents/Test" not in result

    def test_format_search_results_without_client(self):
        """Test search results formatting without client (no links)."""
        search_results = {
            "count": 1,
            "results": [
                {
                    "title": "Test Document",
                    "created": "2023-01-01T00:00:00Z",
                    "id": 301,
                    "tags": [],
                }
            ],
        }

        result = self.bot._format_search_results(search_results)

        # Should not include links without client
        assert "Test Document" in result
        assert "documents/301" not in result
        assert "[" not in result or "](" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
