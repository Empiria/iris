# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""The shared form components, checked in a real browser.

Covers what unit tests can't: the ConfirmBar's cancel path, the Message live
region roles, and the TextField/CopyField secret handling. Runs against the live
local stack and reuses the room helpers from test_manage_rooms.
"""

import pytest
from playwright.sync_api import Page, expect
from test_join import VISIBLE_MS
from test_manage_rooms import (
    _create_permanent,
    _row,
    made_slugs,  # noqa: F401  # pyright: ignore[reportUnusedImport]
    room_name,  # noqa: F401  # pyright: ignore[reportUnusedImport]
)

pytestmark = pytest.mark.e2e


def test_keep_it_leaves_the_room_alone(admin_page: Page, room_name):  # noqa: F811
    page = admin_page
    _create_permanent(page, room_name, "Cancel check")
    row = _row(page, room_name)
    expect(row).to_be_visible(timeout=VISIBLE_MS)

    row.get_by_role("button", name="Delete", exact=True).click()
    expect(row).to_contain_text("Its link stops working for good")
    expect(row.get_by_role("button", name="Delete", exact=True)).to_be_hidden()

    row.get_by_role("button", name="Keep it").click()
    expect(row.get_by_text("Its link stops working for good")).to_be_hidden()
    expect(row.get_by_role("button", name="Delete now")).to_be_hidden()
    expect(row.get_by_role("button", name="Delete", exact=True)).to_be_visible()
    expect(_row(page, room_name)).to_have_count(1)


def test_passphrase_field_is_secret(admin_page: Page, room_name):  # noqa: F811
    page = admin_page
    _create_permanent(page, room_name, "Secret check")
    field = page.get_by_label("Passphrase")
    expect(field).to_have_attribute("readonly", "")
    expect(page.get_by_role("button", name="Copy passphrase")).to_be_visible()


def test_empty_sign_in_message_is_an_alert(page: Page, base_url: str):
    page.goto(base_url)
    page.get_by_role("button", name="Sign in").click(timeout=VISIBLE_MS)
    expect(page.get_by_role("alert")).to_contain_text(
        "Enter your email and password.", timeout=VISIBLE_MS
    )
