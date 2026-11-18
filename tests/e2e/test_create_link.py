"""Create a one-off link on /admin and copy it (ADMIN-02).

Runs against the live local stack. Never waits for network idle. No assertion
message contains a password.
"""

import re

import pytest
from playwright.sync_api import Page, expect

FIRST_LOAD_MS = 120_000
VISIBLE_MS = 30_000

pytestmark = pytest.mark.e2e

ERROR_BANNER = "This app has experienced an error"
SLUG = "[a-hj-km-np-z2-9]{8}"


def _create(page: Page, title: str = ""):
    page.get_by_label("Meeting name (optional)").fill(title)
    page.get_by_role("button", name="Create link").click()


def test_admin_creates_and_copies_link(admin_page: Page):
    page = admin_page
    origin = page.evaluate("location.origin")

    _create(page, "Kickoff")

    link = page.get_by_label("Meeting link")
    pattern = re.compile("^" + re.escape(origin) + "(/|/[?]m=)" + SLUG + "$")
    expect(link).to_have_value(pattern, timeout=VISIBLE_MS)
    expect(page.get_by_text("Link copied.")).to_be_visible(timeout=VISIBLE_MS)
    assert page.evaluate("navigator.clipboard.readText()") == link.input_value()
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_two_links_differ(admin_page: Page):
    page = admin_page
    link = page.get_by_label("Meeting link")

    _create(page)
    expect(link).to_have_value(re.compile(SLUG + "$"), timeout=VISIBLE_MS)
    first = link.input_value()
    _create(page)
    expect(link).not_to_have_value(first, timeout=VISIBLE_MS)

    assert link.input_value() != first
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_create_card_hidden_when_signed_out(page: Page):
    page.goto("admin", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)

    expect(page.get_by_role("heading", name="Admin sign-in")).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    # The card is in the page but hidden, and role queries skip hidden elements.
    expect(page.get_by_role("button", name="Create link")).to_have_count(0)


def test_anonymous_uplink_call_is_refused(uplink):
    with pytest.raises(Exception) as refused:
        uplink.call("create_one_off_link", "x")

    text = type(refused.value).__name__ + " " + str(refused.value)
    assert "Permission" in text or "not allowed" in text or "logged in" in text
