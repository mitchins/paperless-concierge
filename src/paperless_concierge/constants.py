"""
Constants for Paperless-NGX Telegram Concierge
"""

from enum import IntEnum


# HTTP Status Codes
class HTTPStatus(IntEnum):
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405


# Keep backward compatibility
HTTP_OK = HTTPStatus.OK
HTTP_CREATED = HTTPStatus.CREATED
HTTP_ACCEPTED = HTTPStatus.ACCEPTED
HTTP_NOT_FOUND = HTTPStatus.NOT_FOUND
HTTP_METHOD_NOT_ALLOWED = HTTPStatus.METHOD_NOT_ALLOWED

# Time constants (in seconds)
CACHE_EXPIRE_TIME = 86400  # 24 hours
CONTENT_PREVIEW_LENGTH = 200
CONTENT_PREVIEW_TRUNCATE_LENGTH = 100
AI_PROCESSING_TIMEOUT = 120  # 2 minutes
CONSUMPTION_TIMEOUT = 60  # 1 minute
AI_TRIGGER_MAX_RETRIES = 5

# Default limits
DEFAULT_SEARCH_RESULTS = 5
DEFAULT_RECENT_DOCS = 50
DEFAULT_PAGE_SIZE = 20
MAX_BRANCHES_ALLOWED = 12  # For function complexity

# File and content limits
MIN_CONFIDENCE_THRESHOLD = 80  # For vulture dead code detection
