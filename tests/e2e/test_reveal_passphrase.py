# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""An admin shows a permanent room's passphrase again (D-19).

Runs against the live local stack, whose app server holds the dev encryption key
`iris_passphrase_key` (`just up`). The seeded permanent room is made over the
uplink, which cannot use secrets, so it holds no stored passphrase: it stands for
a room made before this feature. No assertion message contains a passphrase.
"""

import re

import pytest
from playwright.sync_api import Page, expect
from test_join import VISIBLE_MS
from test_manage_rooms import (  # noqa: F401 (fixtures)
    _create_permanent,
    _row,
    made_slugs,
    room_name,
)

pytestmark = pytest.mark.e2e

SEEDED_SLUG = "test-room"
NOT_STORED = "This room was made before passphrases were kept"


def test_reveal_shows_the_passphrase_shown_at_creation(
    admin_page: Page,
    room_name,  # noqa: F811
):
    page = admin_page
    created = _create_permanent(page, room_name, "Reveal check")
    row = _row(page, room_name)

    row.get_by_role("button", name="Show passphrase").click()

    field = row.get_by_label("Join phrase")
    expect(field).to_have_value(created, timeout=VISIBLE_MS)
    # Hiding forgets it again and puts the button back.
    row.get_by_role("button", name="Hide passphrase").click()
    expect(field).to_be_hidden()
    expect(row.get_by_role("button", name="Show passphrase")).to_be_visible()


def test_rotate_then_reveal_shows_the_new_passphrase(
    admin_page: Page,
    room_name,  # noqa: F811
):
    page = admin_page
    old = _create_permanent(page, room_name, "Reveal after rotate")
    row = _row(page, room_name)
    row.get_by_role("button", name="Rotate passphrase").click()
    row.get_by_role("button", name="Rotate now").click()
    passphrase = page.get_by_label("Passphrase", exact=True)
    expect(passphrase).not_to_have_value(old, timeout=VISIBLE_MS)
    expect(passphrase).to_have_value(
        re.compile("^[a-hj-km-np-z2-9]{4}(-[a-hj-km-np-z2-9]{4}){2}$")
    )
    new = passphrase.input_value()
    # The rows are redrawn once the rotation is announced; a click before then
    # lands on a row that is about to be replaced.
    expect(
        page.get_by_role("alert").filter(has_text="is in the box above")
    ).to_be_visible(timeout=VISIBLE_MS)

    row = _row(page, room_name)
    row.get_by_role("button", name="Show passphrase").click()

    expect(row.get_by_label("Join phrase")).to_have_value(new, timeout=VISIBLE_MS)


def test_an_older_room_says_it_cannot_be_shown_and_offers_rotate(admin_page: Page):
    page = admin_page
    row = _row(page, SEEDED_SLUG)
    expect(row).to_be_visible(timeout=VISIBLE_MS)

    row.get_by_role("button", name="Show passphrase").click()

    expect(row).to_contain_text(NOT_STORED, timeout=VISIBLE_MS)
    expect(row).to_contain_text("Rotate the passphrase")
    expect(row.get_by_label("Join phrase")).to_be_hidden()
    expect(row.get_by_role("button", name="Rotate passphrase")).to_be_visible()


def test_a_one_off_link_has_no_show_button(admin_page: Page, made_slugs):  # noqa: F811
    from test_manage_rooms import _create_one_off

    page = admin_page
    slug = _create_one_off(page, "No passphrase here", made_slugs)

    expect(_row(page, slug)).to_be_visible(timeout=VISIBLE_MS)
    expect(
        _row(page, slug).get_by_role("button", name="Show passphrase")
    ).to_be_hidden()
