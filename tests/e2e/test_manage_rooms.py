# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Manage rooms from the admin page: list, edit title, rotate, delete (ADMIN-04).

Runs against the live local stack. Each test makes its own rooms through the
page, and a fixture deletes every room it made over the privileged uplink
afterwards, whatever the test did to it. Never waits for network idle. No
assertion message contains a passphrase.
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
    join_path,
)
from test_permanent_room import INCORRECT

pytestmark = pytest.mark.e2e

PASSPHRASE = "[a-hj-km-np-z2-9]{4}(-[a-hj-km-np-z2-9]{4}){2}"


@pytest.fixture
def made_slugs(uplink):
    """The slugs of rooms a test made, each deleted over the uplink afterwards."""
    from anvil.tables import app_tables

    slugs = []
    yield slugs
    for slug in slugs:
        row = app_tables.room.get(slug=slug)
        if row is not None:
            row.delete()


@pytest.fixture
def room_name(made_slugs):
    """A unique room name that is cleaned up after the test."""
    name = "e2e-" + secrets.token_hex(4)
    made_slugs.append(name)
    return name


def _create_permanent(page: Page, name: str, title: str):
    """Create a permanent room through the page and return its passphrase."""
    page.get_by_label("Permanent room").check()
    page.get_by_label("Room name, used in the link").fill(name)
    page.get_by_label("Meeting name (optional)").fill(title)
    page.get_by_role("button", name="Create room").click()
    passphrase = page.get_by_label("Passphrase")
    expect(passphrase).to_have_value(
        re.compile("^" + PASSPHRASE + "$"), timeout=VISIBLE_MS
    )
    return passphrase.input_value()


def _create_one_off(page: Page, title: str, made_slugs: list):
    """Create a one-off link through the page and return its slug."""
    page.get_by_label("One-off link").check()
    page.get_by_label("Meeting name (optional)").fill(title)
    link = page.get_by_label("Meeting link")
    # The field can still hold the last room's link, so wait for a new one.
    before = link.input_value() if link.count() else ""
    page.get_by_role("button", name="Create link").click()
    expect(link).to_have_value(re.compile("[a-z0-9]{8}$"), timeout=VISIBLE_MS)
    expect(link).not_to_have_value(before, timeout=VISIBLE_MS)
    slug = re.split("[/=]", link.input_value())[-1]
    made_slugs.append(slug)
    return slug


def _row(page: Page, slug: str):
    """The list row for `slug`, which is unique random text."""
    return page.locator(".iris-room").filter(has_text=slug)


def _unlock(page: Page, slug: str, passphrase: str):
    """Open `slug` as a client and submit `passphrase` without waiting for a result."""
    _stub_vdo(page)
    join_path(page, slug)
    expect(page.get_by_label("Passphrase")).to_be_visible(timeout=FIRST_LOAD_MS)
    page.get_by_label("Passphrase").fill(passphrase)
    page.get_by_label("Your name").fill("Ann Lee")
    page.get_by_role("button", name="Join meeting").click()


def _handed_off_password(page: Page):
    """The vdo.ninja password in the iframe address once the hand-off has happened."""
    frame = page.locator("iframe.iris-frame")
    expect(frame).to_have_attribute(
        "src", re.compile("^" + SEEDED_ORIGIN + "/"), timeout=VISIBLE_MS
    )
    source = frame.get_attribute("src")
    return dict(_pairs("#" + source.split("#", 1)[1]))["password"]


def test_list_shows_created_rooms(admin_page: Page, room_name, made_slugs):
    page = admin_page

    _create_permanent(page, room_name, "List check permanent")
    one_off = _create_one_off(page, "List check one-off", made_slugs)

    permanent_row = _row(page, room_name)
    expect(permanent_row).to_be_visible(timeout=VISIBLE_MS)
    expect(permanent_row).to_contain_text("Permanent room")
    expect(permanent_row).to_contain_text("List check permanent")
    expect(
        permanent_row.get_by_role("button", name="Rotate passphrase")
    ).to_be_visible()
    one_off_row = _row(page, one_off)
    expect(one_off_row).to_be_visible(timeout=VISIBLE_MS)
    expect(one_off_row).to_contain_text("One-off link")
    expect(one_off_row).to_contain_text("List check one-off")
    # A one-off link has no passphrase to rotate.
    expect(one_off_row.get_by_role("button", name="Rotate passphrase")).to_be_hidden()
    expect(permanent_row.get_by_role("link")).to_have_attribute(
        "href", re.compile("/" + room_name + "$")
    )
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_edit_title(
    admin_page: Page, browser: Browser, base_url: str, room_name, made_slugs
):
    page = admin_page
    passphrase = _create_permanent(page, room_name, "Before the edit")
    row = _row(page, room_name)
    expect(row).to_contain_text("Before the edit", timeout=VISIBLE_MS)

    row.get_by_role("button", name="Edit title").click()
    row.get_by_label("Meeting name").fill("After the edit")
    row.get_by_role("button", name="Save title").click()
    expect(row).to_contain_text("After the edit", timeout=VISIBLE_MS)

    page.reload(wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
    expect(_row(page, room_name)).to_contain_text(
        "After the edit", timeout=FIRST_LOAD_MS
    )

    # The slug did not change, so the same passphrase still hands off. The title
    # is not shown to a client before the passphrase.
    context = browser.new_context(base_url=base_url)
    client = context.new_page()
    try:
        _stub_vdo(client)
        join_path(client, room_name)
        expect(client.get_by_label("Passphrase")).to_be_visible(timeout=FIRST_LOAD_MS)
        assert "After the edit" not in client.locator("body").inner_text()
        client.get_by_label("Passphrase").fill(passphrase)
        client.get_by_label("Your name").fill("Ann Lee")
        client.get_by_role("button", name="Join meeting").click()
        assert re.fullmatch("[0-9a-f]{24}", _handed_off_password(client))
    finally:
        context.close()


def test_rotate_passphrase_old_fails_new_works(
    admin_page: Page, browser: Browser, base_url: str, room_name
):
    page = admin_page
    old = _create_permanent(page, room_name, "Rotate check")

    before = browser.new_context(base_url=base_url)
    try:
        first = before.new_page()
        _unlock(first, room_name, old)
        old_password = _handed_off_password(first)
    finally:
        before.close()

    row = _row(page, room_name)
    row.get_by_role("button", name="Rotate passphrase").click()
    # The row asks first, and says what happens.
    expect(row).to_contain_text("The old passphrase stops working at once")
    row.get_by_role("button", name="Rotate now").click()
    passphrase = page.get_by_label("Passphrase")
    expect(passphrase).to_have_value(
        re.compile("^" + PASSPHRASE + "$"), timeout=VISIBLE_MS
    )
    new = passphrase.input_value()
    assert new != old

    after = browser.new_context(base_url=base_url)
    try:
        refused = after.new_page()
        _unlock(refused, room_name, old)
        expect(refused.get_by_text(INCORRECT)).to_be_visible(timeout=VISIBLE_MS)
    finally:
        after.close()

    working = browser.new_context(base_url=base_url)
    try:
        client = working.new_page()
        _unlock(client, room_name, new)
        new_password = _handed_off_password(client)
        # The room's password was replaced too, so the old one is no use.
        assert new_password != old_password
        assert re.fullmatch("[0-9a-f]{24}", new_password)
    finally:
        working.close()


def test_delete_room_then_no_such_meeting(
    admin_page: Page, browser: Browser, base_url: str, room_name
):
    page = admin_page
    _create_permanent(page, room_name, "Delete check")
    row = _row(page, room_name)
    expect(row).to_be_visible(timeout=VISIBLE_MS)

    row.get_by_role("button", name="Delete", exact=True).click()
    expect(row).to_contain_text("Its link stops working for good")
    row.get_by_role("button", name="Delete now").click()
    expect(_row(page, room_name)).to_have_count(0, timeout=VISIBLE_MS)

    context = browser.new_context(base_url=base_url)
    try:
        client = context.new_page()
        join_path(client, room_name)
        expect(client.get_by_role("heading", name="No such meeting")).to_be_visible(
            timeout=FIRST_LOAD_MS
        )
    finally:
        context.close()


def test_delete_one_off_link(
    admin_page: Page, browser: Browser, base_url: str, made_slugs
):
    page = admin_page
    slug = _create_one_off(page, "One-off delete check", made_slugs)
    row = _row(page, slug)
    expect(row).to_be_visible(timeout=VISIBLE_MS)

    row.get_by_role("button", name="Delete", exact=True).click()
    row.get_by_role("button", name="Delete now").click()
    expect(_row(page, slug)).to_have_count(0, timeout=VISIBLE_MS)

    context = browser.new_context(base_url=base_url)
    try:
        client = context.new_page()
        join_path(client, slug)
        expect(client.get_by_role("heading", name="No such meeting")).to_be_visible(
            timeout=FIRST_LOAD_MS
        )
    finally:
        context.close()


def test_management_hidden_for_signed_out(page: Page):
    page.goto("/", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
    expect(page.get_by_label("Email")).to_be_visible(timeout=FIRST_LOAD_MS)

    # The list and its controls are in the page but hidden, and no room is shown.
    expect(page.get_by_role("heading", name="Rooms")).to_be_hidden()
    expect(page.locator(".iris-room-list")).to_be_hidden()
    assert page.locator(".iris-room").count() == 0
    assert not page.get_by_text(ERROR_BANNER).is_visible()
