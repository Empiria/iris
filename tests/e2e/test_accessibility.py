# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Accessibility: axe-core finds no WCAG 2.1 A/AA violation on the main pages.

Runs the axe-core build that axe-playwright-python bundles, so it needs no
network. Covers the join page, the admin sign-in and the signed-in admin page
with its sections. Never waits for network idle (Anvil holds connections open).
"""

import pytest
from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import Page, expect

FIRST_LOAD_MS = 120_000
VISIBLE_MS = 30_000
# This repeats DEV_ROOM_SLUG in tools/dev_seed.py, as in test_join.py.
SEEDED_SLUG = "testslug"

pytestmark = pytest.mark.e2e

AXE_OPTIONS = {
    "runOnly": {
        "type": "tag",
        "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
    }
}


# Anvil adds this "Built with Anvil" badge to the page itself, and its link has no
# accessible name (axe `link-name`). It is not Iris markup, so it is left out.
CONTEXT = {"exclude": [["#anvil-badge"]]}


def assert_no_violations(page: Page):
    results = Axe().run(page, context=CONTEXT, options=AXE_OPTIONS)
    found = [
        f"{v['id']} ({v['impact']}): "
        + ", ".join(n["target"][0] for n in v["nodes"][:5])
        for v in results.response["violations"]
    ]
    assert not found, "axe violations:\n" + "\n".join(found)


def test_page_language_is_set(page: Page):
    page.goto("", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
    expect(page.get_by_role("heading", name="Admin sign-in")).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    expect(page.locator("html")).to_have_attribute("lang", "en-GB")


def test_join_page_has_no_violations(page: Page):
    page.goto(SEEDED_SLUG, wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
    expect(page.get_by_label("Your name")).to_be_visible(timeout=FIRST_LOAD_MS)
    assert_no_violations(page)


def test_admin_sign_in_has_no_violations(page: Page):
    page.goto("admin", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
    expect(page.get_by_role("heading", name="Admin sign-in")).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    assert_no_violations(page)


def test_signed_in_admin_has_no_violations(admin_page: Page):
    expect(admin_page.get_by_role("heading", name="Call settings")).to_be_visible(
        timeout=VISIBLE_MS
    )
    assert_no_violations(admin_page)
