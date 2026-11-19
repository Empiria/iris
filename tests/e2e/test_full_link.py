# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Per-visit overrides on the Iris link, and the Full link panel in the call.

Runs against the live local stack after `just seed`. A cold load of
`/<slug>?q=2` must reach the join page with the setting applied to the room
address, whether the room is embedded or the browser is redirected.
"""

import pytest
from playwright.sync_api import Browser, Page, expect
from test_join import (
    FIRST_LOAD_MS,
    SEEDED_ORIGIN,
    SEEDED_SLUG,
    SEEDED_TITLE,
    VISIBLE_MS,
    _fill_and_join,
    _pairs,
    _stub_vdo,
    handed_off_url,
    join_path,
)
from test_join_iframe import IPHONE_UA

pytestmark = pytest.mark.e2e


def _open(page: Page, query: str):
    _stub_vdo(page)
    join_path(page, SEEDED_SLUG + query)
    expect(page.get_by_role("heading", name=SEEDED_TITLE)).to_be_visible(
        timeout=FIRST_LOAD_MS
    )


def _values(url: str, key: str):
    return [value for name, value in _pairs(url) if name == key]


def test_a_cold_load_with_an_override_reaches_the_room_address(page: Page):
    _open(page, "?q=2&rbr=200")

    _fill_and_join(page, "Ann Lee")

    url = handed_off_url(page)
    assert url.startswith(SEEDED_ORIGIN)
    assert _values(url, "q") == ["2"]
    assert _values(url, "rbr") == ["200"]
    assert _values(url, "label") == ["Ann Lee"]


def test_an_override_reaches_the_redirect_too(browser: Browser, base_url: str):
    context = browser.new_context(base_url=base_url, user_agent=IPHONE_UA)
    page = context.new_page()
    try:
        _open(page, "?q=2")
        _fill_and_join(page, "Ann Lee")

        page.wait_for_url(SEEDED_ORIGIN + "/**", timeout=VISIBLE_MS)
        assert _values(page.url, "q") == ["2"]
    finally:
        context.close()


def test_keys_that_are_not_allowed_are_ignored_and_reported(page: Page):
    _open(page, "?q=2&password=x&room=evil&salt=s&foo=1")

    expect(page.get_by_text("Ignored in the link")).to_be_visible()
    _fill_and_join(page, "Ann Lee")

    url = handed_off_url(page)
    assert _values(url, "q") == ["2"]
    assert "evil" not in url
    assert _values(url, "password") == []
    assert _values(url, "salt") == []
    assert _values(url, "foo") == []


def test_the_full_link_panel_shows_the_link_without_password_or_salt(page: Page):
    _open(page, "?q=2")
    _fill_and_join(page, "Ann Lee")
    handed_off_url(page)

    page.get_by_role("button", name="Full link").click()

    shown = page.locator(".iris-fulllink input").input_value()
    assert shown.startswith(SEEDED_ORIGIN)
    assert _values(shown, "q") == ["2"]
    assert _values(shown, "label") == ["Ann Lee"]
    assert _values(shown, "room")
    assert _values(shown, "password") == []
    assert _values(shown, "salt") == []
    expect(page.get_by_text("left out on purpose")).to_be_visible()
    expect(page.get_by_text("?q=2&rbr=200")).to_be_visible()
    expect(page.get_by_role("button", name="Copy")).to_be_visible()
