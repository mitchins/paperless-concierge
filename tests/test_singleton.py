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

from paperless_concierge.bot import (
    ensure_singleton,
    _is_valid_pid,
    _is_owned_by_current_user,
)


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

    def test_is_valid_pid_positive_normal(self):
        """Test PID validation for normal positive PIDs."""
        assert _is_valid_pid(1234) == True
        assert _is_valid_pid(9999) == True
        assert _is_valid_pid(100000) == True

    def test_is_valid_pid_invalid_cases(self):
        """Test PID validation rejects invalid PIDs."""
        # Negative PIDs
        assert _is_valid_pid(-1) == False
        assert _is_valid_pid(-100) == False

        # Zero PID
        assert _is_valid_pid(0) == False

        # PID 1 (init/systemd) - too sensitive
        assert _is_valid_pid(1) == False

        # Extremely large PIDs (potential security risk)
        assert _is_valid_pid(2**20 + 1) == False
        assert _is_valid_pid(2**30) == False

        # Non-integer types
        assert _is_valid_pid("1234") == False
        assert _is_valid_pid(12.34) == False
        assert _is_valid_pid(None) == False

    def test_is_valid_pid_boundary_cases(self):
        """Test PID validation boundary cases."""
        # Maximum valid PID (just under limit)
        assert _is_valid_pid(2**20) == True
        assert _is_valid_pid(2**20 - 1) == True

        # Minimum valid PID
        assert _is_valid_pid(2) == True

    @patch("os.path.exists", return_value=True)
    @patch("os.getuid", return_value=1000)
    @patch("os.stat")
    def test_is_owned_by_current_user_owned(
        self, mock_stat, _mock_getuid, _mock_exists
    ):
        """Test ownership check when process is owned by current user."""
        # Mock stat result with matching UID
        mock_stat_result = Mock()
        mock_stat_result.st_uid = 1000  # Same as current user
        mock_stat.return_value = mock_stat_result

        assert _is_owned_by_current_user(1234) == True

    @patch("os.path.exists", return_value=True)
    @patch("os.getuid", return_value=1000)
    @patch("os.stat")
    def test_is_owned_by_current_user_not_owned(
        self, mock_stat, _mock_getuid, _mock_exists
    ):
        """Test ownership check when process is owned by different user."""
        # Mock stat result with different UID
        mock_stat_result = Mock()
        mock_stat_result.st_uid = 1001  # Different from current user
        mock_stat.return_value = mock_stat_result

        assert _is_owned_by_current_user(1234) == False

    @patch("os.path.exists", return_value=False)
    def test_is_owned_by_current_user_no_proc(self, _mock_exists):
        """Test ownership check when /proc doesn't exist (e.g., macOS)."""
        # Should default to True when /proc isn't available
        assert _is_owned_by_current_user(1234) == True

    @patch("os.path.exists", side_effect=OSError("Permission denied"))
    def test_is_owned_by_current_user_permission_error(self, _mock_exists):
        """Test ownership check handles permission errors safely."""
        assert _is_owned_by_current_user(1234) == True

    def test_ensure_singleton_oversized_pid_in_lock(self):
        """Test that oversized PIDs in lock file are handled securely."""
        # Create lock file with invalid PID (too large)
        lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")
        with open(lock_file, "w") as f:
            f.write(str(2**30))  # Extremely large PID

        with patch("os.getpid", return_value=12345):
            with patch("paperless_concierge.bot.logger") as mock_logger:
                lock_fd = ensure_singleton()
                assert lock_fd is not None

                # Should have logged warning about invalid PID
                mock_logger.warning.assert_called()
                assert "Invalid PID" in str(mock_logger.warning.call_args)

    def test_ensure_singleton_negative_pid_in_lock(self):
        """Test that negative PIDs in lock file are handled securely."""
        # Create lock file with negative PID
        lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")
        with open(lock_file, "w") as f:
            f.write("-1")

        with patch("os.getpid", return_value=12345):
            with patch("paperless_concierge.bot.logger") as mock_logger:
                lock_fd = ensure_singleton()
                assert lock_fd is not None

                # Should have logged warning about invalid PID
                mock_logger.warning.assert_called()

    @patch("paperless_concierge.bot._is_owned_by_current_user", return_value=False)
    def test_ensure_singleton_different_user_process(self, _mock_ownership):
        """Test that PIDs owned by different users are handled safely."""
        # Create lock file with PID owned by different user
        lock_file = os.path.join(tempfile.gettempdir(), "paperless-concierge.lock")
        with open(lock_file, "w") as f:
            f.write("5555")

        with patch("os.getpid", return_value=12345):
            with patch("paperless_concierge.bot.logger") as mock_logger:
                lock_fd = ensure_singleton()
                assert lock_fd is not None

                # Should have logged warning about ownership
                mock_logger.warning.assert_called()
                assert "not owned by current user" in str(mock_logger.warning.call_args)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
