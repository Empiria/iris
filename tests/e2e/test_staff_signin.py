"""The /staff sign-in page on the local stack (STAFF-01).

Cold loads /staff, signs in with the dev accounts that `staff_login` and
`non_staff_login` make, and checks the refusals. Never waits for network idle:
Anvil holds connections open. No assertion message contains a password.
"""

import re

import pytest
from playwright.sync_api import Page, expect

FIRST_LOAD_MS = 120_000
VISIBLE_MS = 30_000

pytestmark = pytest.mark.e2e

ERROR_BANNER = "This app has experienced an error"


def _open_sign_in(page: Page):
    page.goto("staff", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
    expect(page.get_by_role("heading", name="Staff sign-in")).to_be_visible(
        timeout=FIRST_LOAD_MS
    )


def _sign_in(page: Page, email: str, password: str):
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


def _no_error_banner(page: Page):
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_staff_signs_in_and_out(page: Page, staff_login):
    email, password = staff_login
    _open_sign_in(page)

    _sign_in(page, email, password)

    expect(page.get_by_text("Signed in as " + email)).to_be_visible(timeout=VISIBLE_MS)
    page.get_by_role("button", name="Sign out").click()
    expect(page.get_by_role("heading", name="Staff sign-in")).to_be_visible(
        timeout=VISIBLE_MS
    )
    _no_error_banner(page)


def test_wrong_password_is_refused(page: Page, staff_login):
    email, _password = staff_login
    _open_sign_in(page)

    _sign_in(page, email, "not-the-right-password")

    expect(page.get_by_text("Email or password not recognised.")).to_be_visible(
        timeout=VISIBLE_MS
    )
    expect(page.get_by_label("Password")).to_have_value("")
    _no_error_banner(page)


def test_non_staff_account_is_refused(page: Page, non_staff_login):
    email, password = non_staff_login
    _open_sign_in(page)

    _sign_in(page, email, password)

    expect(page.get_by_text("This account is not a staff account.")).to_be_visible(
        timeout=VISIBLE_MS
    )
    expect(page.get_by_role("heading", name="Staff sign-in")).to_be_visible()
    _no_error_banner(page)


def test_no_sign_up_control(page: Page):
    _open_sign_in(page)

    pattern = re.compile(r"sign[ -]?up|register|create account", re.IGNORECASE)

    assert page.get_by_text(pattern).count() == 0
    assert page.get_by_role("link", name=pattern).count() == 0
    assert page.get_by_role("button", name=pattern).count() == 0
    _no_error_banner(page)
