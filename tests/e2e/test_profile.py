"""Edit the vdo.ninja profile on the staff page (STAFF-05).

Runs against the live local stack after `just seed`. The tests change the
`vdo_profile` setting, so a fixture puts back whatever it held, over the
privileged uplink. Never waits for network idle. No assertion message contains
a password.
"""

import pytest
from playwright.sync_api import Page, expect

# The join helpers are shared with test_join.py, not copied, so the two files
# read the hand-off address the same way.
from test_join import (
    FIRST_LOAD_MS,
    SEEDED_SLUG,
    SEEDED_TITLE,
    VISIBLE_MS,
    _fill_and_join,
    _pairs,
    _stub_vdo,
    handed_off_url,
    join_path,
)

pytestmark = pytest.mark.e2e

ERROR_BANNER = "This app has experienced an error"
SAVED = "Saved. New joins use these settings."
MESHCAST_MESSAGE = "profile parameter 'meshcast' is not allowed"


@pytest.fixture
def restore_profile(uplink):
    """Put the `vdo_profile` setting back to what it was, after the test."""
    from anvil.tables import app_tables

    row = app_tables.setting.get(key="vdo_profile")
    before = None if row is None else row["value"]
    yield
    row = app_tables.setting.get(key="vdo_profile")
    if before is None:
        if row is not None:
            row.delete()
    elif row is None:
        app_tables.setting.add_row(key="vdo_profile", value=before)
    else:
        row["value"] = before


def _save_profile(page: Page, text: str):
    field = page.get_by_label("vdo.ninja parameters")
    expect(field).to_be_visible(timeout=VISIBLE_MS)
    field.fill(text)
    page.get_by_role("button", name="Save settings").click()


def test_staff_edits_profile_and_next_join_uses_it(
    staff_page: Page, page: Page, restore_profile
):
    _save_profile(staff_page, "&iristestparam=1")
    expect(staff_page.get_by_text(SAVED)).to_be_visible(timeout=VISIBLE_MS)

    # A fresh context, so nothing from the staff session carries over.
    _stub_vdo(page)
    join_path(page, SEEDED_SLUG)
    expect(page.get_by_role("heading", name=SEEDED_TITLE)).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    _fill_and_join(page, "Ann Lee")

    keys = [key for key, _ in _pairs(handed_off_url(page))]
    assert "iristestparam" in keys
    assert not staff_page.get_by_text(ERROR_BANNER).is_visible()


def test_rejected_profile_shows_message(staff_page: Page, restore_profile):
    _save_profile(staff_page, "iristestparam=2")
    expect(staff_page.get_by_text(SAVED)).to_be_visible(timeout=VISIBLE_MS)

    _save_profile(staff_page, "&meshcast")
    expect(staff_page.get_by_text(MESHCAST_MESSAGE)).to_be_visible(timeout=VISIBLE_MS)

    staff_page.reload(wait_until="domcontentloaded")
    expect(staff_page.get_by_label("vdo.ninja parameters")).to_have_value(
        "iristestparam=2", timeout=FIRST_LOAD_MS
    )
    assert not staff_page.get_by_text(ERROR_BANNER).is_visible()


def test_profile_card_hidden_when_signed_out(page: Page):
    page.goto("staff", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)

    expect(page.get_by_role("heading", name="Staff sign-in")).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    # The card is in the page but hidden, and label queries find hidden inputs.
    expect(page.get_by_label("vdo.ninja parameters")).to_be_hidden()
    expect(page.get_by_role("button", name="Save settings")).to_have_count(0)
