"""Paperless-NGX Telegram Concierge package."""

__version__ = "1.0.0"
__author__ = "Mitchell Currie"
__email__ = "your.email@example.com"
__description__ = (
    "A Telegram bot for uploading documents and querying your Paperless-NGX instance"
)

from .bot import main
from .config import *
from .constants import *

__all__ = ["main"]
