"""Create a permanent room on the admin page and join it (ADMIN-03, JOIN-02).

Runs against the live local stack. Each test makes a room with a unique name,
and a fixture deletes it over the privileged uplink afterwards. Never waits for
network idle. No assertion message contains a passphrase.
"""

import re
import secrets

import pytest
from playwright.sync_api import Browser, Page, expect
from test_join import (
    ERROR_BANNER,
    FIRST_LOAD_MS,
    SEEDED_ORIGIN,
    VISIBLE_MS,
    _pairs,
    _stub_vdo,
)

pytestmark = pytest.mark.e2e

PASSPHRASE = "[a-hj-km-np-z2-9]{4}(-[a-hj-km-np-z2-9]{4}){2}"
TAKEN = "That name is taken."
RESERVED = "That name is reserved."


@pytest.fixture
def room_name(uplink):
    """A unique room name, with its room row removed after the test."""
    from anvil.tables import app_tables

    name = "e2e-" + secrets.token_hex(4)
    yield name
    row = app_tables.room.get(slug=name)
    if row is not None:
        row.delete()


def _create_permanent(page: Page, name: str, title: str = ""):
    page.get_by_label("Permanent room").check()
    page.get_by_label("Room name, used in the link").fill(name)
    page.get_by_label("Meeting name (optional)").fill(title)
    page.get_by_role("button", name="Create room").click()


def test_admin_creates_permanent_room_and_sees_passphrase_once(
    admin_page: Page, room_name
):
    page = admin_page
    origin = page.evaluate("location.origin")

    _create_permanent(page, room_name, "Weekly sync")

    link = page.get_by_label("Meeting link")
    expect(link).to_have_value(
        re.compile("^" + re.escape(origin) + "(/|/[?]m=)" + room_name + "$"),
        timeout=VISIBLE_MS,
    )
    passphrase = page.get_by_label("Passphrase")
    expect(passphrase).to_have_value(re.compile("^" + PASSPHRASE + "$"))
    shown = passphrase.input_value()

    page.get_by_role("button", name="Copy passphrase").click()
    expect(page.get_by_text("Passphrase copied.")).to_be_visible(timeout=VISIBLE_MS)
    assert page.evaluate("navigator.clipboard.readText()") == shown

    # A second one-off link clears it, and so does a reload: it is never shown again.
    page.get_by_label("One-off link").check()
    page.get_by_role("button", name="Create link").click()
    expect(page.get_by_label("Meeting link")).not_to_have_value(
        re.compile(room_name), timeout=VISIBLE_MS
    )
    expect(page.get_by_label("Passphrase")).to_be_hidden()
    assert shown not in page.locator("body").inner_text()
    assert not page.get_by_text(ERROR_BANNER).is_visible()

    page.reload(wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
    expect(page.get_by_text("Signed in as")).to_be_visible(timeout=FIRST_LOAD_MS)
    expect(page.get_by_label("Passphrase")).to_be_hidden()
    assert shown not in page.locator("body").inner_text()


def test_duplicate_name_is_refused(admin_page: Page, room_name):
    page = admin_page

    _create_permanent(page, room_name)
    expect(page.get_by_label("Passphrase")).to_have_value(
        re.compile("^" + PASSPHRASE + "$"), timeout=VISIBLE_MS
    )
    first = page.get_by_label("Passphrase").input_value()

    _create_permanent(page, room_name)

    expect(page.get_by_text(TAKEN)).to_be_visible(timeout=VISIBLE_MS)
    # The refused attempt shows no passphrase, and the first one is not repeated.
    expect(page.get_by_label("Passphrase")).to_be_hidden()
    assert first not in page.locator("body").inner_text()
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_reserved_name_is_refused(admin_page: Page, uplink):
    from anvil.tables import app_tables

    page = admin_page

    _create_permanent(page, "admin")

    expect(page.get_by_text(RESERVED)).to_be_visible(timeout=VISIBLE_MS)
    expect(page.get_by_label("Passphrase")).to_be_hidden()
    assert app_tables.room.get(slug="admin") is None
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_client_joins_new_permanent_room_with_shown_passphrase(
    admin_page: Page, browser: Browser, base_url: str, room_name
):
    _create_permanent(admin_page, room_name, "Client check")
    passphrase = admin_page.get_by_label("Passphrase")
    expect(passphrase).to_have_value(
        re.compile("^" + PASSPHRASE + "$"), timeout=VISIBLE_MS
    )
    shown = passphrase.input_value()
    link = admin_page.get_by_label("Meeting link").input_value()

    context = browser.new_context(base_url=base_url)
    client = context.new_page()
    try:
        _stub_vdo(client)
        client.goto(link, wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
        field = client.get_by_label("Passphrase")
        expect(field).to_be_visible(timeout=FIRST_LOAD_MS)
        assert "Client check" not in client.locator("body").inner_text()

        # Typed in capitals and without the dashes, which is still the same passphrase.
        field.fill(shown.replace("-", "").upper())
        client.get_by_label("Your name").fill("Ann Lee")
        client.get_by_role("button", name="Join meeting").click()

        frame = client.locator("iframe.iris-frame")
        expect(frame).to_have_attribute(
            "src", re.compile("^" + SEEDED_ORIGIN + "/"), timeout=VISIBLE_MS
        )
        source = frame.get_attribute("src")
        fragment = dict(_pairs("#" + source.split("#", 1)[1]))
        assert re.fullmatch("[a-z0-9]{20}", fragment["room"])
        assert re.fullmatch("[0-9a-f]{24}", fragment["password"])
        lowered = source.lower()
        assert shown not in lowered and shown.replace("-", "") not in lowered
        assert shown not in client.url and shown.replace("-", "") not in client.url
    finally:
        context.close()
