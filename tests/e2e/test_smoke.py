"""Smoke test: the app root loads on the local stack and shows the staff sign-in.

Follows the vault's playwright-patterns note: goto(""), explicit visibility waits
and a long first-load timeout. Anvil holds connections open, so never wait for the
network to go quiet.
"""

import pytest
from playwright.sync_api import Page, expect

FIRST_LOAD_MS = 120_000
VISIBLE_MS = 30_000

pytestmark = pytest.mark.e2e


def test_root_opens_staff_sign_in_and_server_call_succeeds(page: Page):
    page.goto("", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)

    # Logged out, "/" shows the staff sign-in form. The page asks the server for
    # the sign-in state before it shows the form, so seeing the form means a
    # server call round-tripped.
    expect(page.get_by_role("heading", name="Staff sign-in")).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    expect(page.get_by_label("Email")).to_be_visible(timeout=VISIBLE_MS)
    expect(page.get_by_label("Password")).to_be_visible(timeout=VISIBLE_MS)

    # Anvil keeps its error banner in the DOM and toggles visibility.
    assert not page.get_by_text("This app has experienced an error").is_visible()
