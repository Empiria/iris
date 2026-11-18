"""The "Forgot password?" link on the sign-in form (local stack).

The local app server has no mail delivery configured, so these tests check the
request and its confirmation, not the emailed link. The same text must show for
an account that exists and one that does not.
"""

import pytest
from playwright.sync_api import Page, expect

FIRST_LOAD_MS = 120_000
VISIBLE_MS = 30_000

pytestmark = pytest.mark.e2e

SENT = "If that email belongs to an admin account"


def _open_request_form(page: Page):
    page.goto("/", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
    page.get_by_role("button", name="Forgot password?").click(timeout=FIRST_LOAD_MS)


@pytest.mark.parametrize("who", ["known", "unknown"])
def test_request_shows_one_message(page: Page, admin_login, who):
    email = admin_login[0] if who == "known" else "nobody@example.invalid"
    _open_request_form(page)

    page.get_by_label("Email").last.fill(email)
    page.get_by_role("button", name="Send reset link").click()

    expect(page.get_by_text(SENT)).to_be_visible(timeout=VISIBLE_MS)
    assert not page.get_by_text("This app has experienced an error").is_visible()
