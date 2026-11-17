"""Smoke test: the app loads on the local stack and a server call succeeds.

Follows the vault's playwright-patterns note: goto(""), explicit visibility waits
and a long first-load timeout. Anvil holds connections open, so never wait for the
network to go quiet.
"""

import pytest
from playwright.sync_api import Page, expect

FIRST_LOAD_MS = 120_000
VISIBLE_MS = 30_000

pytestmark = pytest.mark.e2e


def test_home_loads_and_server_call_succeeds(page: Page):
    page.goto("", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)

    expect(page.get_by_role("heading", name="Iris")).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    expect(page.get_by_text("Server check: pong")).to_be_visible(timeout=VISIBLE_MS)

    # Anvil keeps its error banner in the DOM and toggles visibility.
    assert not page.get_by_text("This app has experienced an error").is_visible()
