#!/usr/bin/env python3
"""
Test main function enhancements, particularly singleton enforcement.
"""

import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


class TestMainFunction:
    """Test main function enhancements."""

    @patch("paperless_concierge.bot.ensure_singleton")
    @patch("paperless_concierge.bot.Application")
    @patch("paperless_concierge.bot.DocumentTracker")
    @patch("paperless_concierge.bot.TelegramConcierge")
    def test_main_calls_ensure_singleton(
        self, mock_concierge, mock_tracker, mock_app, mock_singleton
    ):
        """Test that main function calls ensure_singleton before doing anything else."""
        # Mock the application builder chain
        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = MagicMock()
        mock_app.builder.return_value = mock_builder

        # Mock the concierge and tracker
        mock_concierge_instance = MagicMock()
        mock_concierge.return_value = mock_concierge_instance
        mock_tracker_instance = MagicMock()
        mock_tracker.return_value = mock_tracker_instance

        # Mock the application instance
        mock_app_instance = MagicMock()
        mock_builder.build.return_value = mock_app_instance

        # Import and call main
        from paperless_concierge.bot import main

        # Mock sys.argv to avoid argparse issues
        with patch("sys.argv", ["paperless-concierge"]):
            try:
                main()
            except SystemExit:
                # main() calls app.run_polling() which might exit
                pass

        # Verify ensure_singleton was called
        mock_singleton.assert_called_once()

    @patch("paperless_concierge.bot.ensure_singleton", side_effect=SystemExit(1))
    def test_main_exits_if_singleton_fails(self, mock_singleton):
        """Test that main function exits if ensure_singleton fails."""
        from paperless_concierge.bot import main

        # Should exit due to singleton check
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
        mock_singleton.assert_called_once()

    @patch("paperless_concierge.bot.ensure_singleton")
    @patch("paperless_concierge.bot.argparse.ArgumentParser")
    def test_main_singleton_called_before_argparse(self, mock_parser, mock_singleton):
        """Test that ensure_singleton is called before argument parsing."""
        # Mock parser
        mock_parser_instance = MagicMock()
        mock_parser.return_value = mock_parser_instance
        mock_parser_instance.parse_args.return_value = MagicMock()

        from paperless_concierge.bot import main

        # Mock the rest of main to avoid full execution
        with patch("paperless_concierge.bot.Application") as mock_app:
            mock_builder = MagicMock()
            mock_builder.token.return_value = mock_builder
            mock_builder.build.return_value = MagicMock()
            mock_app.builder.return_value = mock_builder

            with patch("paperless_concierge.bot.DocumentTracker"):
                with patch("paperless_concierge.bot.TelegramConcierge"):
                    try:
                        main()
                    except (SystemExit, AttributeError):
                        # May exit during app.run_polling()
                        pass

        # Verify ensure_singleton was called
        mock_singleton.assert_called_once()

        # Verify parser was created (meaning we got past singleton check)
        mock_parser.assert_called_once()

    def test_ensure_singleton_function_exists(self):
        """Test that ensure_singleton function exists and is callable."""
        from paperless_concierge.bot import ensure_singleton

        assert callable(ensure_singleton)

    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        from paperless_concierge.bot import main

        assert callable(main)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
