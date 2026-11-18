"""Join a meeting from its link (JOIN-01, JOIN-04, JOIN-06, DEPL-01).

Runs against the live local stack after `just seed`, which makes the room
`testslug` and points the vdo_origin setting at DEV_VDO_ORIGIN. The browser never
reaches that origin: a route stub answers it with an empty page, so the test can
read the address Iris handed off to. Never waits for network idle. Playwright's
`wait_until` is "domcontentloaded" because Anvil holds connections open.
"""

import re
import time
from urllib.parse import unquote, urlsplit

import pytest
from playwright.sync_api import Page, expect

FIRST_LOAD_MS = 120_000
VISIBLE_MS = 30_000

pytestmark = pytest.mark.e2e

# These repeat the DEV_* constants in tools/dev_seed.py. A unit test keeps them equal.
SEEDED_SLUG = "testslug"
SEEDED_TITLE = "Seeded test meeting"
SEEDED_VDO_ROOM = "kdvx2p8wmq5rt7hzn3cj"
SEEDED_ORIGIN = "http://127.0.0.1:3030"

ERROR_BANNER = "This app has experienced an error"
VDO_ROOM = "[a-z0-9]{20}"
NAME_MESSAGE = "Enter your name to join."


def _stub_vdo(page: Page):
    """Answer the seeded origin with an empty page, in the page or any frame."""
    page.route(
        SEEDED_ORIGIN + "/**",
        lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body="<!doctype html><title>vdo</title>",
        ),
    )


def join_path(page: Page, slug: str):
    page.goto(slug, wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)


def handed_off_url(page: Page, timeout_ms: int = VISIBLE_MS) -> str:
    """The address Iris sent the person to: the page itself, or an iframe on it.

    The hand-off is a top-level redirect today and becomes an iframe in a later
    plan. Either way the address is the one that starts with the seeded origin.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if page.url.startswith(SEEDED_ORIGIN):
            return page.url
        sources = page.locator("iframe[src]").evaluate_all(
            "frames => frames.map(frame => frame.src)"
        )
        for source in sources:
            if source.startswith(SEEDED_ORIGIN):
                return source
        page.wait_for_timeout(200)
    pytest.fail(f"no hand-off to {SEEDED_ORIGIN} within {timeout_ms} ms")


def _pairs(url: str):
    """Every key and decoded value from the query and the fragment of `url`."""
    parts = urlsplit(url)
    found = []
    for piece in (parts.query + "&" + parts.fragment).split("&"):
        if piece:
            key, _, value = piece.partition("=")
            found.append((unquote(key).lower(), unquote(value)))
    return found


def _fill_and_join(page: Page, name: str):
    page.get_by_label("Your name").fill(name)
    page.get_by_role("button", name="Join meeting").click()


def test_join_hands_off_to_the_seeded_origin(page: Page):
    _stub_vdo(page)

    join_path(page, SEEDED_SLUG)
    expect(page.get_by_role("heading", name=SEEDED_TITLE)).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    _fill_and_join(page, "Ann Lee")

    url = handed_off_url(page)
    pairs = _pairs(url)
    keys = [key for key, _ in pairs]
    assert url.startswith(SEEDED_ORIGIN + "/")
    assert dict(pairs)["room"] == SEEDED_VDO_ROOM
    assert dict(pairs)["label"] == "Ann Lee"
    assert keys.count("room") == 1
    assert keys.count("label") == 1
    assert ("rbr", "50000") in pairs
    assert not [key for key in keys if key.startswith(("meshcast", "relay"))]
    assert SEEDED_SLUG not in url


def test_unknown_slug_says_no_such_meeting(page: Page):
    join_path(page, "zzzzzzzz")

    expect(page.get_by_role("heading", name="No such meeting")).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    expect(page.get_by_label("Your name")).to_have_count(0)
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_empty_name_is_refused_and_nothing_is_handed_off(page: Page):
    _stub_vdo(page)

    join_path(page, SEEDED_SLUG)
    expect(page.get_by_role("heading", name=SEEDED_TITLE)).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    before = page.url
    page.get_by_role("button", name="Join meeting").click()

    expect(page.get_by_text(NAME_MESSAGE)).to_be_visible(timeout=VISIBLE_MS)
    page.wait_for_timeout(500)
    assert page.url == before
    assert page.locator("iframe[src]").count() == 0
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_home_and_staff_still_load_cold(page: Page):
    page.goto("", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
    expect(page.get_by_text("Server check: pong")).to_be_visible(timeout=FIRST_LOAD_MS)
    assert page.get_by_role("heading", name="No such meeting").count() == 0

    page.goto("staff", wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
    expect(page.get_by_role("heading", name="Staff sign-in")).to_be_visible(
        timeout=FIRST_LOAD_MS
    )
    assert page.get_by_role("heading", name="No such meeting").count() == 0
    assert not page.get_by_text(ERROR_BANNER).is_visible()


def test_a_link_made_by_staff_opens_for_a_client(staff_page: Page, browser):
    staff = staff_page
    staff.get_by_label("Meeting name (optional)").fill("Client call")
    staff.get_by_role("button", name="Create link").click()
    link = staff.get_by_label("Meeting link")
    expect(link).to_have_value(re.compile("/[a-z0-9]{8}$"), timeout=VISIBLE_MS)
    url = link.input_value()
    slug = url.rsplit("/", 1)[1]

    context = browser.new_context()
    try:
        client = context.new_page()
        _stub_vdo(client)
        client.goto(url, wait_until="domcontentloaded", timeout=FIRST_LOAD_MS)
        expect(client.get_by_role("heading", name="Client call")).to_be_visible(
            timeout=FIRST_LOAD_MS
        )
        _fill_and_join(client, "Ben Client")

        handed = handed_off_url(client)
        pairs = dict(_pairs(handed))
        assert re.fullmatch(VDO_ROOM, pairs["room"])
        assert pairs["room"] != slug
        assert pairs["label"] == "Ben Client"
        assert slug not in handed
    finally:
        context.close()
