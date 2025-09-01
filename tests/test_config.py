#!/usr/bin/env python3
"""
Test config.py error handling for better coverage.
"""

import os
import sys
import pytest
from unittest.mock import patch


def test_missing_config_first():
    """Test ValueError when neither AUTHORIZED_USERS nor USER_CONFIG_FILE are provided."""
    # This hits the first error condition in config.py (line 56)
    with patch.dict(os.environ, {}, clear=True), patch(
        "dotenv.load_dotenv"
    ) as mock_load_dotenv:
        mock_load_dotenv.return_value = None
        if "config" in sys.modules:
            del sys.modules["config"]
        with pytest.raises(ValueError, match="❌ Configuration missing!"):
            import config  # noqa: F401


def test_missing_paperless_token():
    """Test ValueError when PAPERLESS_TOKEN is missing in global mode."""
    # This hits the PAPERLESS_TOKEN error (line 48)
    env_vars = {
        "AUTHORIZED_USERS": "123456789",
        "PAPERLESS_URL": "http://test:8000",
    }
    with patch.dict(os.environ, env_vars, clear=True), patch(
        "dotenv.load_dotenv"
    ) as mock_load_dotenv:
        mock_load_dotenv.return_value = None
        if "config" in sys.modules:
            del sys.modules["config"]
        with pytest.raises(ValueError, match="❌ PAPERLESS_TOKEN missing!"):
            import config  # noqa: F401


def test_missing_paperless_url():
    """Test ValueError when PAPERLESS_URL is missing in global mode."""
    env_vars = {
        "TELEGRAM_BOT_TOKEN": "test_token",
        "AUTHORIZED_USERS": "123456789",
    }
    with patch.dict(os.environ, env_vars, clear=True), patch(
        "dotenv.load_dotenv"
    ) as mock_load_dotenv:
        mock_load_dotenv.return_value = None
        if "config" in sys.modules:
            del sys.modules["config"]
        with pytest.raises(ValueError, match="❌ PAPERLESS_URL missing!"):
            import config  # noqa: F401
