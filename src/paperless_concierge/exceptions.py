"""Custom exceptions for Paperless-NGX Telegram Concierge."""

from enum import Enum, auto
from typing import Optional


class PaperlessErrorType(Enum):
    """Types of Paperless API errors."""

    CONNECTION_FAILED = auto()
    AUTHENTICATION_FAILED = auto()
    TASK_NOT_FOUND = auto()
    UPLOAD_FAILED = auto()
    API_ERROR = auto()
    INVALID_RESPONSE = auto()


class TelegramErrorType(Enum):
    """Types of Telegram bot errors."""

    FILE_DOWNLOAD_FAILED = auto()
    FILE_PROCESSING_FAILED = auto()
    UNSUPPORTED_FILE_TYPE = auto()
    TEMP_FILE_OPERATION_FAILED = auto()
    MESSAGE_SEND_FAILED = auto()


class PaperlessError(Exception):
    """Base exception for all Paperless-related errors."""

    def __init__(
        self,
        message: str,
        error_type: PaperlessErrorType = PaperlessErrorType.API_ERROR,
        status_code: Optional[int] = None,
    ):
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code

    def is_not_found(self) -> bool:
        """Check if this is a not-found error."""
        return self.error_type == PaperlessErrorType.TASK_NOT_FOUND

    def is_connection_error(self) -> bool:
        """Check if this is a connection error."""
        return self.error_type == PaperlessErrorType.CONNECTION_FAILED


class TelegramBotError(Exception):
    """Base exception for Telegram bot operations."""

    def __init__(
        self,
        message: str,
        error_type: TelegramErrorType = TelegramErrorType.FILE_PROCESSING_FAILED,
    ):
        super().__init__(message)
        self.error_type = error_type

    def is_download_error(self) -> bool:
        """Check if this is a download error."""
        return self.error_type == TelegramErrorType.FILE_DOWNLOAD_FAILED

    def is_unsupported_file(self) -> bool:
        """Check if this is an unsupported file error."""
        return self.error_type == TelegramErrorType.UNSUPPORTED_FILE_TYPE


# For backwards compatibility and clarity, provide specific exception classes
class PaperlessConnectionError(PaperlessError):
    """Raised when unable to connect to Paperless-NGX."""

    def __init__(self, message: str):
        super().__init__(message, PaperlessErrorType.CONNECTION_FAILED)


class PaperlessAuthenticationError(PaperlessError):
    """Raised when authentication with Paperless-NGX fails."""

    def __init__(self, message: str):
        super().__init__(message, PaperlessErrorType.AUTHENTICATION_FAILED)


class PaperlessTaskNotFoundError(PaperlessError):
    """Raised when a task is not found in Paperless-NGX."""

    def __init__(self, message: str):
        super().__init__(message, PaperlessErrorType.TASK_NOT_FOUND, status_code=404)


class PaperlessUploadError(PaperlessError):
    """Raised when document upload fails."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message, PaperlessErrorType.UPLOAD_FAILED, status_code)


class PaperlessAPIError(PaperlessError):
    """Raised for general API errors from Paperless-NGX."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message, PaperlessErrorType.API_ERROR, status_code)


class FileDownloadError(TelegramBotError):
    """Raised when file download from Telegram fails."""

    def __init__(self, message: str):
        super().__init__(message, TelegramErrorType.FILE_DOWNLOAD_FAILED)


class FileProcessingError(TelegramBotError):
    """Raised when file processing fails."""

    def __init__(self, message: str):
        super().__init__(message, TelegramErrorType.FILE_PROCESSING_FAILED)


class UnsupportedFileTypeError(TelegramBotError):
    """Raised when an unsupported file type is received."""

    def __init__(self, message: str):
        super().__init__(message, TelegramErrorType.UNSUPPORTED_FILE_TYPE)


class TempFileError(TelegramBotError):
    """Raised when temporary file operations fail."""

    def __init__(self, message: str):
        super().__init__(message, TelegramErrorType.TEMP_FILE_OPERATION_FAILED)
