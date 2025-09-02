import pytest
import httpx
import sys
import types

# Provide minimal stubs for python-telegram-bot if it's not installed in the env
try:  # pragma: no cover
    import telegram  # noqa: F401
    from telegram.error import TelegramError  # noqa: F401
    import telegram.ext  # noqa: F401
except Exception:  # pragma: no cover
    telegram = types.ModuleType("telegram")

    class TelegramError(Exception):
        pass

    class InlineKeyboardButton:
        def __init__(self, text, callback_data=None):
            self.text = text
            self.callback_data = callback_data

    class InlineKeyboardMarkup:
        def __init__(self, keyboard):
            self.keyboard = keyboard

    class _Filter:
        def __or__(self, _other):
            return self

    class Update:
        ALL_TYPES = []

    telegram.InlineKeyboardButton = InlineKeyboardButton
    telegram.InlineKeyboardMarkup = InlineKeyboardMarkup
    telegram.Update = Update

    error_mod = types.ModuleType("telegram.error")
    error_mod.TelegramError = TelegramError

    ext_mod = types.ModuleType("telegram.ext")

    class Application:
        @classmethod
        def builder(_cls):
            class _B:
                def token(self, *_a, **_k):
                    return self

                def build(self):
                    return Application()

            return _B()

        # no-op methods to avoid attribute errors if used inadvertently
        def add_handler(self, *_a, **_k):
            return None

        def run_polling(self, *_a, **_k):
            return None

    class _Handler:
        def __init__(self, *_a, **_k):
            pass

    class ContextTypes:
        DEFAULT_TYPE = object

    class filters:
        PHOTO = _Filter()

        class Document:
            ALL = _Filter()

    ext_mod.Application = Application
    ext_mod.CallbackQueryHandler = _Handler
    ext_mod.CommandHandler = _Handler
    ext_mod.MessageHandler = _Handler
    ext_mod.ContextTypes = ContextTypes
    ext_mod.filters = filters

    sys.modules["telegram"] = telegram
    sys.modules["telegram.error"] = error_mod
    sys.modules["telegram.ext"] = ext_mod


@pytest.fixture(autouse=True)
def block_httpx_network(request, monkeypatch):
    """Prevent accidental real HTTP calls in tests.

    - If a test uses the `httpx_mock` fixture, we allow httpx to operate as the
      fixture intercepts all requests.
    - Otherwise, we patch AsyncClient.send to fail fast with a clear message.
    """
    if "httpx_mock" in request.fixturenames:
        return  # handled by pytest-httpx

    async def _blocked_send(self, *_args, **_kwargs):  # pragma: no cover
        raise AssertionError(
            "Unexpected HTTP request. Use the `httpx_mock` fixture to stub calls."
        )

    monkeypatch.setattr(httpx.AsyncClient, "send", _blocked_send, raising=True)
