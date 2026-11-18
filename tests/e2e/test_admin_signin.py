# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""The /admin sign-in page on the local stack (ADMIN-01).

Cold loads /admin, signs in with the dev accounts that `admin_login` and
`non_admin_login` make, and checks the refusals. Never waits for network idle:
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
    page.goto("admin", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
    expect(page.get_by_role("heading", name="Admin sign-in")).to_be_visible(
        timeout=FIRST_LOAD_MS
    )


def _sign_in(page: Page, email: str, password: str):
    page.get_by_label("Email").first.fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()


def _no_error_banner(page: Page):
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_admin_signs_in_and_out(page: Page, admin_login):
    email, password = admin_login
    _open_sign_in(page)

    _sign_in(page, email, password)

    expect(page.get_by_text("Signed in as " + email)).to_be_visible(timeout=VISIBLE_MS)
    page.get_by_role("button", name="Sign out").click()
    expect(page.get_by_role("heading", name="Admin sign-in")).to_be_visible(
        timeout=VISIBLE_MS
    )
    _no_error_banner(page)


def test_wrong_password_is_refused(page: Page, admin_login):
    email, _password = admin_login
    _open_sign_in(page)

    _sign_in(page, email, "not-the-right-password")

    expect(page.get_by_text("Email or password not recognised.")).to_be_visible(
        timeout=VISIBLE_MS
    )
    expect(page.get_by_label("Password")).to_have_value("")
    _no_error_banner(page)


def test_non_admin_account_is_refused(page: Page, non_admin_login):
    email, password = non_admin_login
    _open_sign_in(page)

    _sign_in(page, email, password)

    expect(page.get_by_text("This account is not an admin account.")).to_be_visible(
        timeout=VISIBLE_MS
    )
    expect(page.get_by_role("heading", name="Admin sign-in")).to_be_visible()
    _no_error_banner(page)


def test_no_sign_up_control(page: Page):
    _open_sign_in(page)

    pattern = re.compile(r"sign[ -]?up|register|create account", re.IGNORECASE)

    assert page.get_by_text(pattern).count() == 0
    assert page.get_by_role("link", name=pattern).count() == 0
    assert page.get_by_role("button", name=pattern).count() == 0
    _no_error_banner(page)


def test_old_staff_path_still_opens_the_admin_page(page: Page):
    """Bookmarks to /staff, the page's path before the rename, keep working."""
    page.goto("staff", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)

    expect(page.get_by_role("heading", name="Admin sign-in")).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    _no_error_banner(page)
