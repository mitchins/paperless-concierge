#!/usr/bin/env python3
"""
Targeted tests for exception classes to provide meaningful coverage
without adding heavy boilerplate.
"""

from paperless_concierge.exceptions import (
    PaperlessError,
    PaperlessErrorType,
    TelegramErrorType,
    PaperlessConnectionError,
    PaperlessAuthenticationError,
    PaperlessTaskNotFoundError,
    PaperlessUploadError,
    PaperlessAPIError,
    TelegramBotError,
    FileDownloadError,
    FileProcessingError,
    UnsupportedFileTypeError,
    TempFileError,
)


def test_paperless_error_hierarchy_and_helpers():
    conn = PaperlessConnectionError("conn")
    assert isinstance(conn, PaperlessError)
    assert conn.error_type == PaperlessErrorType.CONNECTION_FAILED
    assert conn.is_connection_error() is True
    assert conn.status_code is None

    auth = PaperlessAuthenticationError("auth")
    assert isinstance(auth, PaperlessError)
    assert auth.error_type == PaperlessErrorType.AUTHENTICATION_FAILED

    not_found = PaperlessTaskNotFoundError("missing")
    assert isinstance(not_found, PaperlessError)
    assert not_found.error_type == PaperlessErrorType.TASK_NOT_FOUND
    assert not_found.is_not_found() is True
    assert not_found.status_code == 404

    up = PaperlessUploadError("upload", status_code=400)
    assert up.error_type == PaperlessErrorType.UPLOAD_FAILED
    assert up.status_code == 400

    api = PaperlessAPIError("api", status_code=500)
    assert api.error_type == PaperlessErrorType.API_ERROR
    assert api.status_code == 500


def test_telegam_error_hierarchy_and_helpers():
    base = TelegramBotError("base")
    assert isinstance(base, Exception)

    dl = FileDownloadError("dl")
    assert isinstance(dl, TelegramBotError)
    assert dl.error_type == TelegramErrorType.FILE_DOWNLOAD_FAILED
    assert dl.is_download_error() is True

    proc = FileProcessingError("proc")
    assert proc.error_type == TelegramErrorType.FILE_PROCESSING_FAILED

    unsup = UnsupportedFileTypeError("unsup")
    assert unsup.error_type == TelegramErrorType.UNSUPPORTED_FILE_TYPE
    assert unsup.is_unsupported_file() is True

    tmp = TempFileError("tmp")
    assert tmp.error_type == TelegramErrorType.TEMP_FILE_OPERATION_FAILED
