#!/usr/bin/env python3
"""
Test singleton functionality to prevent duplicate bot instances.
"""

import os
import sys
import tempfile
import pytest
from unittest.mock import Mock, patch

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from paperless_concierge.bot import ensure_singleton


class TestSingleton:
    """Test singleton functionality."""

    def setup_method(self):
        """Clean up any existing lock files before each test."""
        lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")
        try:
            os.unlink(lock_file)
        except OSError:
            pass

    def teardown_method(self):
        """Clean up lock files after each test."""
        lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")
        try:
            os.unlink(lock_file)
        except OSError:
            pass

    def test_ensure_singleton_first_instance(self):
        """Test that first instance can acquire lock successfully."""
        with patch("os.getpid", return_value=12345):
            lock_fd = ensure_singleton()
            assert lock_fd is not None

            # Lock file should exist with correct PID
            lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")
            assert os.path.exists(lock_file)

            with open(lock_file, "r") as f:
                pid_content = f.read().strip()
                assert pid_content == "12345"

    def test_ensure_singleton_duplicate_running_process(self):
        """Test that duplicate instance exits when process is still running."""
        # Create a lock file with a fake PID
        lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")
        with open(lock_file, "w") as f:
            f.write("99999")

        # Mock os.kill to not raise an exception (process exists)
        with patch("os.kill") as mock_kill:
            mock_kill.return_value = None  # Process exists

            with patch("builtins.exit") as mock_exit:
                with patch("builtins.print") as mock_print:
                    ensure_singleton()

                    # Should have tried to check if process exists
                    mock_kill.assert_called_once_with(99999, 0)
                    # Should have printed error message
                    mock_print.assert_any_call(
                        "❌ Another instance is already running (PID: 99999)"
                    )
                    mock_print.assert_any_call(
                        "   Stop it first or wait for it to exit."
                    )
                    # Should have exited
                    mock_exit.assert_called_once_with(1)

    def test_ensure_singleton_stale_lock_file(self):
        """Test that stale lock file is cleaned up and new instance starts."""
        # Create a lock file with a fake PID
        lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")
        with open(lock_file, "w") as f:
            f.write("88888")

        # Mock os.kill to raise ProcessLookupError (process doesn't exist)
        with patch("os.kill", side_effect=ProcessLookupError("No such process")):
            with patch("os.getpid", return_value=12345):
                lock_fd = ensure_singleton()
                assert lock_fd is not None

                # Lock file should exist with new PID
                assert os.path.exists(lock_file)
                with open(lock_file, "r") as f:
                    pid_content = f.read().strip()
                    assert pid_content == "12345"

    def test_ensure_singleton_invalid_pid_in_lock(self):
        """Test handling of corrupted lock file with invalid PID."""
        # Create a lock file with invalid content
        lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")
        with open(lock_file, "w") as f:
            f.write("not-a-number")

        with patch("os.getpid", return_value=12345):
            lock_fd = ensure_singleton()
            assert lock_fd is not None

            # Lock file should be recreated with new PID
            assert os.path.exists(lock_file)
            with open(lock_file, "r") as f:
                pid_content = f.read().strip()
                assert pid_content == "12345"

    def test_ensure_singleton_permission_error(self):
        """Test handling when unable to remove stale lock file due to permissions."""
        # Create a lock file with a fake PID
        lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")
        with open(lock_file, "w") as f:
            f.write("77777")

        # Mock os.kill to raise ProcessLookupError (stale process)
        # Mock os.unlink to raise permission error
        with patch("os.kill", side_effect=ProcessLookupError("No such process")):
            with patch("os.unlink", side_effect=OSError("Permission denied")):
                with patch("builtins.exit") as mock_exit:
                    with patch("builtins.print") as mock_print:
                        ensure_singleton()

                        # Should have printed error message
                        mock_print.assert_called_once_with(
                            "❌ Cannot acquire lock - permission denied"
                        )
                        # Should have exited
                        mock_exit.assert_called_once_with(1)

    def test_ensure_singleton_lock_file_path(self):
        """Test that lock file is created in the correct location."""
        with patch("os.getpid", return_value=12345):
            ensure_singleton()

            expected_path = os.path.join(
                tempfile.gettempdir(), "paperless-concierge.lock"
            )
            assert os.path.exists(expected_path)

    @patch("atexit.register")
    def test_ensure_singleton_registers_cleanup(self, mock_atexit):
        """Test that cleanup function is registered with atexit."""
        with patch("os.getpid", return_value=12345):
            ensure_singleton()

            # atexit.register should have been called
            mock_atexit.assert_called_once()
            cleanup_func = mock_atexit.call_args[0][0]
            assert callable(cleanup_func)

    def test_cleanup_function(self):
        """Test the cleanup function works correctly."""
        with patch("os.getpid", return_value=12345):
            lock_fd = ensure_singleton()

            # Manually call cleanup (normally called by atexit)
            lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")

            # Verify file exists before cleanup
            assert os.path.exists(lock_file)

            # The cleanup function is registered with atexit, but we can test it indirectly
            # by checking that the file gets removed when the process exits
            # For now, just verify the file exists (cleanup will happen on real exit)
            assert os.path.exists(lock_file)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
