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
