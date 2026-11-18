"""S1: does a Routing Route with load_data serve /<slug> as a cold load?

Four variants of the same app. The first three answer assumption A7 and declare
the /:slug route first, the worst case for /staff and /. control leaves the
routes module at Routing's default name ("routes"), which Iris does not have.
config points Routing at services.routes through the dependency's config.
shim adds a root routes.py that imports services.routes. staff_first is the
shim with /staff and / declared before /:slug. none_data is staff_first with
load_data returning None for an unknown slug instead of raising NotFound.
"""

from common import (
    FIRST_LOAD_TIMEOUT_MS,
    LOAD_TIMEOUT_MS,
    banner_detail,
    browser,
    http_get,
    uplink,
    wait_for_text,
    watch,
)

NEEDS_STACK = True
VARIANTS = ["control", "config", "shim", "staff_first", "none_data"]

SLUG = "spikeslug"
VALUE = "spike-value-1"


def _state(page):
    nodes = page.locator("span")
    return [nodes.nth(i).inner_text() for i in range(nodes.count())]


def _load(chromium, url, expect, timeout):
    """Cold load url in a fresh context. Returns (status, state, banner, error)."""
    context = chromium.new_context()
    page = context.new_page()
    seen = watch(page)
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        status = response.status if response else None
        error = wait_for_text(page, expect, timeout, seen)
        return status, _state(page), banner_detail(page), error
    finally:
        context.close()


def _row(spike_id, prefix, ok, evidence):
    return (spike_id, "PASS" if ok else "FAIL", f"[{prefix}] {evidence}")


def run(base_url, variant):
    rows = []
    root = base_url.rstrip("/")
    prefix = variant
    with browser() as chromium:
        status, state, banner, error = _load(
            chromium, f"{root}/{SLUG}", VALUE, FIRST_LOAD_TIMEOUT_MS
        )
        raw_status, _headers, raw_body = http_get(f"{root}/{SLUG}")
        rows.append(
            _row(
                "S1a",
                prefix,
                error is None and not banner and raw_status == 200,
                f"cold /{SLUG}: first response {status}, spans {state}, "
                f"error banner {banner}, wait error {error}. Plain GET status "
                f"{raw_status}, {len(raw_body)} bytes, "
                f"value in server HTML {VALUE in raw_body}",
            )
        )
        status, state, banner, error = _load(
            chromium, f"{root}/spikeinvalid", "no data", LOAD_TIMEOUT_MS
        )
        rows.append(
            _row(
                "S1b",
                prefix,
                error is None and not banner,
                f"cold /spikeinvalid: first response {status}, spans {state}, "
                f"error banner {banner}, wait error {error}",
            )
        )
        s_status, s_state, s_banner, s_error = _load(
            chromium, f"{root}/staff", "Staff spike page", LOAD_TIMEOUT_MS
        )
        h_status, h_state, h_banner, h_error = _load(
            chromium, f"{root}/", "Server check", LOAD_TIMEOUT_MS
        )
        rows.append(
            _row(
                "S1c",
                prefix,
                s_error is None and h_error is None and not s_banner and not h_banner,
                f"/staff: status {s_status}, error {s_error}, banner {s_banner}. "
                f"/: status {h_status}, error {h_error}, banner {h_banner}",
            )
        )
        rows.append(_calls_row(root, chromium, prefix, base_url))
    return rows


def _calls_row(root, chromium, prefix, base_url):
    try:
        with uplink(base_url) as server:
            server.call("spike_reset")
            _status, _state_, _banner, error = _load(
                chromium, f"{root}/{SLUG}", VALUE, LOAD_TIMEOUT_MS
            )
            calls = server.call("spike_calls")
    except Exception as exc:
        return _row("S1d", prefix, False, f"uplink failed: {type(exc).__name__}: {exc}")
    return _row(
        "S1d",
        prefix,
        error is None and len(calls) == 1,
        f"lookup calls recorded for one cold load of /{SLUG}: {len(calls)} "
        f"{calls}, wait error {error}",
    )
