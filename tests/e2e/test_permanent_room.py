# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Open a permanent room with its passphrase.

Runs against the live local stack after `just seed`, which makes the permanent
room `test-room` with a made-up passphrase and points the vdo_origin setting at
SEEDED_ORIGIN. The browser never reaches that origin: a route stub answers it
with an empty page, so the test can read the address Iris handed off to. Never
waits for network idle. No assertion message contains a passphrase.

The seeded room's unlock throttle is cleared before and after each test over the
privileged uplink, so the order of the tests does not matter.
"""

import re
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Browser, Page, expect
from test_join import (
    ERROR_BANNER,
    FIRST_LOAD_MS,
    SEEDED_ORIGIN,
    VISIBLE_MS,
    _pairs,
    _stub_vdo,
    handed_off_url,
    join_path,
)
from test_join_iframe import BRAVE_INIT_SCRIPT, IPHONE_UA

pytestmark = pytest.mark.e2e

# These repeat the constants in tools/dev_seed.py. A unit test keeps them equal.
SEEDED_PERMANENT_SLUG = "test-room"
SEEDED_PERMANENT_TITLE = "Seeded permanent room"
SEEDED_PERMANENT_VDO_ROOM = "q7wn4hx2cvb9mz5dk3tp"
SEEDED_PERMANENT_VDO_PASSWORD = "0123456789abcdef01234567"
SEEDED_PASSPHRASE = "test-room-pass"

# Typed in capitals with odd spacing, to check that it is normalised.
TYPED_PASSPHRASE = "  TEST-room  PASS "
WRONG_PASSPHRASE = "test-room-wrong"
INCORRECT = "Incorrect passphrase. Check it and try again."
THROTTLED = "Too many attempts"
# The spellings of the passphrase that must never appear in an address.
FORBIDDEN = (SEEDED_PASSPHRASE, "testroompass")


def _reset_throttle():
    from anvil.tables import app_tables

    row = app_tables.room.get(slug=SEEDED_PERMANENT_SLUG)
    if row is None:
        pytest.fail("the seeded permanent room is missing: run `just seed`")
    row["failed_unlocks"] = 0
    row["locked_until"] = None


@pytest.fixture(autouse=True)
def clean_throttle(uplink):
    _reset_throttle()
    yield
    _reset_throttle()


def _open_locked(page: Page):
    _stub_vdo(page)
    join_path(page, SEEDED_PERMANENT_SLUG)
    expect(page.get_by_label("Passphrase")).to_be_visible(timeout=FIRST_LOAD_MS)


def _submit(page: Page, passphrase: str, name: str = "Ann Lee"):
    page.get_by_label("Passphrase").fill(passphrase)
    page.get_by_label("Your name").fill(name)
    page.get_by_role("button", name="Join meeting").click()


def _submit_refused(page: Page, passphrase: str):
    """Submit and wait until the form is ready for another try."""
    _submit(page, passphrase)
    expect(page.get_by_role("button", name="Join meeting")).to_be_enabled(
        timeout=VISIBLE_MS
    )


def _assert_handed_off_with_password(url: str):
    """The room address carries the vdo.ninja password after #, and no passphrase."""
    parts = urlsplit(url)
    fragment = dict(_pairs("#" + parts.fragment))
    assert url.startswith(SEEDED_ORIGIN + "/")
    assert fragment["room"] == SEEDED_PERMANENT_VDO_ROOM
    assert fragment["password"] == SEEDED_PERMANENT_VDO_PASSWORD
    lowered = url.lower()
    assert not [text for text in FORBIDDEN if text in lowered]


def _assert_iris_address_is_clean(page: Page):
    # The Iris address bar still holds only the slug.
    assert page.url.endswith("/" + SEEDED_PERMANENT_SLUG)
    lowered = page.url.lower()
    assert not [text for text in FORBIDDEN if text in lowered]


def test_locked_room_shows_passphrase_and_no_title(page: Page):
    _open_locked(page)

    expect(page.get_by_label("Your name")).to_be_visible()
    expect(page.get_by_label("Passphrase")).to_have_attribute("type", "password")
    expect(page.get_by_label("Passphrase")).to_have_attribute("autocomplete", "off")
    assert SEEDED_PERMANENT_TITLE not in page.locator("body").inner_text()
    assert page.locator("iframe[src]").count() == 0
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_wrong_passphrase_says_incorrect_and_stays(page: Page):
    reached = []
    page.on(
        "request",
        lambda request: (
            reached.append(request.url)
            if request.url.startswith(SEEDED_ORIGIN)
            else None
        ),
    )
    _open_locked(page)

    _submit_refused(page, WRONG_PASSPHRASE)

    expect(page.get_by_text(INCORRECT)).to_be_visible(timeout=VISIBLE_MS)
    # The field is cleared after the submit, and the page has not moved.
    expect(page.get_by_label("Passphrase")).to_have_value("")
    _assert_iris_address_is_clean(page)
    expect(page.locator("iframe[src]")).to_have_count(0)
    assert reached == []
    assert SEEDED_PERMANENT_TITLE not in page.locator("body").inner_text()
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_correct_passphrase_embeds_on_desktop(page: Page):
    _open_locked(page)

    _submit(page, TYPED_PASSPHRASE)

    frame = page.locator("iframe.iris-frame")
    expect(frame).to_have_attribute(
        "src", re.compile("^" + SEEDED_ORIGIN + "/"), timeout=VISIBLE_MS
    )
    _assert_handed_off_with_password(frame.get_attribute("src"))
    expect(frame).to_be_visible()
    _assert_iris_address_is_clean(page)
    expect(page.get_by_label("Passphrase")).to_have_value("")


def test_correct_passphrase_redirects_on_iphone(browser: Browser, base_url: str):
    context = browser.new_context(base_url=base_url, user_agent=IPHONE_UA)
    page = context.new_page()
    try:
        _open_locked(page)

        _submit(page, TYPED_PASSPHRASE)

        page.wait_for_url(SEEDED_ORIGIN + "/**", timeout=VISIBLE_MS)
        _assert_handed_off_with_password(page.url)
        assert page.locator("iframe.iris-frame[src]").count() == 0
    finally:
        context.close()


def test_correct_passphrase_redirects_on_brave(browser: Browser, base_url: str):
    """Brave looks like Chrome but its Shields break the room inside an iframe."""
    context = browser.new_context(base_url=base_url)
    context.add_init_script(BRAVE_INIT_SCRIPT)
    page = context.new_page()
    try:
        _open_locked(page)

        _submit(page, TYPED_PASSPHRASE)

        page.wait_for_url(SEEDED_ORIGIN + "/**", timeout=VISIBLE_MS)
        _assert_handed_off_with_password(page.url)
        assert page.locator("iframe.iris-frame[src]").count() == 0
    finally:
        context.close()


def test_password_never_in_query(page: Page):
    _open_locked(page)

    _submit(page, TYPED_PASSPHRASE)

    source = handed_off_url(page)
    query = parse_qs(urlsplit(source).query)
    assert not [key for key in query if key.lower() in ("password", "pw", "p")]
    # It is in the fragment, which never reaches the vdo.ninja host's logs.
    assert "password=" in urlsplit(source).fragment


def test_throttle_message_after_ten_wrong(page: Page):
    _open_locked(page)

    for _ in range(10):
        _submit_refused(page, WRONG_PASSPHRASE)
    expect(page.get_by_text(INCORRECT)).to_be_visible(timeout=VISIBLE_MS)

    # Even the right passphrase is refused while the room is locked.
    _submit_refused(page, SEEDED_PASSPHRASE)

    expect(page.get_by_text(THROTTLED)).to_be_visible(timeout=VISIBLE_MS)
    assert page.locator("iframe[src]").count() == 0
    _assert_iris_address_is_clean(page)
