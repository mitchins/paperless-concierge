#!/usr/bin/env python3
import os
import pytest


@pytest.mark.asyncio
async def test_cli_get_user_id_main(monkeypatch):
    # Ensure token exists
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    # Import and call main; telegram stubs in conftest provide no-op Application
    from paperless_concierge.cli.get_user_id import main

    # Should not raise; run_polling is a no-op in stubs
    main()


@pytest.mark.asyncio
async def test_cli_get_my_id_handler():
    # Import the handler
    from paperless_concierge.cli.get_user_id import get_my_id

    class _User:
        id = 123
        username = "tester"
        first_name = "Test"

    class _Msg:
        async def reply_text(self, text):
            assert "User ID: 123" in text

    class _Update:
        effective_user = _User()
        message = _Msg()

    class _Ctx:
        pass

    await get_my_id(_Update(), _Ctx())
