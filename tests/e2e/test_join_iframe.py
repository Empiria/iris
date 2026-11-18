# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""The room opens in an iframe on Join, except where the decision says redirect.

JOIN-07. Desktop Chromium is not in the redirect list, so Join embeds the room and
the page stays on Iris. An iPhone user agent is "safari-ios", which redirects.
The seeded VDO origin is answered by a stub, so the browser never leaves the machine.
"""

import re

import pytest
from playwright.sync_api import Browser, Page, expect
from test_join import (
    FIRST_LOAD_MS,
    SEEDED_ORIGIN,
    SEEDED_SLUG,
    SEEDED_TITLE,
    SEEDED_VDO_ROOM,
    VISIBLE_MS,
    _fill_and_join,
    _stub_vdo,
    join_path,
)

pytestmark = pytest.mark.e2e

IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
)
# Looks like Brave to the page's own check. Shared with test_permanent_room.py.
BRAVE_INIT_SCRIPT = (
    "Object.defineProperty(navigator, 'brave', "
    "{ value: { isBrave: () => Promise.resolve(true) } });"
)


def _ready(page: Page):
    _stub_vdo(page)
    join_path(page, SEEDED_SLUG)
    expect(page.get_by_role("heading", name=SEEDED_TITLE)).to_be_visible(
        timeout=FIRST_LOAD_MS
    )


def test_no_room_frame_has_a_source_before_join(page: Page):
    _ready(page)

    assert page.locator("iframe[src]").count() == 0


def test_desktop_join_embeds_the_room_and_stays_on_iris(page: Page):
    _ready(page)
    start = page.url

    _fill_and_join(page, "Ann Lee")

    frame = page.locator("iframe.iris-frame")
    expect(frame).to_have_attribute(
        "src", re.compile("^" + SEEDED_ORIGIN + "/"), timeout=VISIBLE_MS
    )
    assert SEEDED_VDO_ROOM in frame.get_attribute("src")
    assert frame.get_attribute("allow") == (
        "camera; microphone; autoplay; display-capture"
    )
    assert frame.get_attribute("referrerpolicy") == "strict-origin-when-cross-origin"
    expect(frame).to_be_visible()
    assert page.url == start
    expect(page.get_by_label("Your name")).to_be_hidden()


def test_iphone_join_redirects_instead_of_embedding(browser: Browser, base_url: str):
    context = browser.new_context(base_url=base_url, user_agent=IPHONE_UA)
    page = context.new_page()
    try:
        _ready(page)
        _fill_and_join(page, "Ann Lee")

        page.wait_for_url(SEEDED_ORIGIN + "/**", timeout=VISIBLE_MS)
        assert page.locator("iframe.iris-frame[src]").count() == 0
    finally:
        context.close()


def test_brave_join_redirects_instead_of_embedding(browser: Browser, base_url: str):
    """Brave looks like Chrome but its Shields break the room inside an iframe."""
    context = browser.new_context(base_url=base_url)
    context.add_init_script(BRAVE_INIT_SCRIPT)
    page = context.new_page()
    try:
        _ready(page)
        _fill_and_join(page, "Ann Lee")

        page.wait_for_url(SEEDED_ORIGIN + "/**", timeout=VISIBLE_MS)
        assert page.locator("iframe.iris-frame[src]").count() == 0
    finally:
        context.close()
