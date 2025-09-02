#!/usr/bin/env python3
"""
Test that new imports (atexit, fcntl) work correctly and are available.
"""

import os
import sys
import pytest

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


class TestNewImports:
    """Test new import functionality."""

    def test_atexit_import(self):
        """Test that atexit module is imported and available."""
        # Import the bot module to trigger imports
        import paperless_concierge.bot as bot_module

        # Check that atexit is available in the module
        assert hasattr(bot_module, "atexit")

        # Check that atexit has the register function we use
        assert hasattr(bot_module.atexit, "register")
        assert callable(bot_module.atexit.register)

    def test_fcntl_import(self):
        """Test that fcntl module is imported and available."""
        # Import the bot module to trigger imports
        import paperless_concierge.bot as bot_module

        # Check that fcntl is available in the module
        assert hasattr(bot_module, "fcntl")

        # fcntl is primarily used for file locking but we're using os.open instead
        # Just verify it imports without error
        assert bot_module.fcntl is not None

    def test_imports_dont_break_existing_functionality(self):
        """Test that new imports don't break existing bot functionality."""
        from paperless_concierge.bot import TelegramConcierge

        # Should be able to create bot instance without import errors
        bot = TelegramConcierge()
        assert bot is not None

        # Should have all the methods we expect
        assert hasattr(bot, "_build_document_url")
        assert hasattr(bot, "_format_ai_response")
        assert hasattr(bot, "_format_search_results")
        assert hasattr(bot, "query_documents")

    def test_os_functions_available(self):
        """Test that os functions used in singleton are available."""
        import paperless_concierge.bot as bot_module

        # Check that os functions we use are available
        assert hasattr(bot_module.os, "open")
        assert hasattr(bot_module.os, "write")
        assert hasattr(bot_module.os, "close")
        assert hasattr(bot_module.os, "unlink")
        assert hasattr(bot_module.os, "kill")
        assert hasattr(bot_module.os, "getpid")
        assert hasattr(bot_module.os, "O_CREAT")
        assert hasattr(bot_module.os, "O_EXCL")
        assert hasattr(bot_module.os, "O_WRONLY")

    def test_tempfile_functions_available(self):
        """Test that tempfile functions used in singleton are available."""
        import paperless_concierge.bot as bot_module

        # Check that tempfile functions we use are available
        assert hasattr(bot_module.tempfile, "gettempdir")
        assert callable(bot_module.tempfile.gettempdir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
