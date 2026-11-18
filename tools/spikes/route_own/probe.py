# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""S2 and S3: a plain @anvil.server.route owns /<slug> and returns AppResponder.

Two variants. route has a pathed Routing Route on /:slug as well as the plain
server route, so the evidence shows whether the two collide. fallback has no
pathed Route for the slug and uses Routing's default not-found route to show
the form, so there is nothing to collide with.
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
VARIANTS = ["route", "fallback"]

SLUG = "spikeslug"
VALUE = "spike-value-1"


def _spans(page):
    nodes = page.locator("span")
    return [nodes.nth(i).inner_text() for i in range(nodes.count())]


def _load(chromium, url, expect, timeout):
    """Cold load url in a fresh context. Returns (status, spans, banner, error)."""
    context = chromium.new_context()
    page = context.new_page()
    seen = watch(page)
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        status = response.status if response else None
        error = wait_for_text(page, expect, timeout, seen)
        return status, _spans(page), banner_detail(page), error
    finally:
        context.close()


def _row(spike_id, prefix, ok, evidence):
    return (spike_id, "PASS" if ok else "FAIL", f"[{prefix}] {evidence}")


def run(base_url, variant):
    root = base_url.rstrip("/")
    rows = []
    with browser() as chromium:
        status, spans, banner, error = _load(
            chromium, f"{root}/{SLUG}", VALUE, FIRST_LOAD_TIMEOUT_MS
        )
        rows.append(
            _row(
                "S2a",
                variant,
                status == 200 and error is None and not banner,
                f"cold /{SLUG}: first response {status}, spans {spans}, "
                f"error banner {banner}, wait error {error}",
            )
        )
        status, spans, banner, error = _load(
            chromium, f"{root}/spikeinvalid", "no data", LOAD_TIMEOUT_MS
        )
        rows.append(
            _row(
                "S2b",
                variant,
                error is None and not banner,
                f"cold /spikeinvalid: first response {status}, spans {spans}, "
                f"error banner {banner}, wait error {error}",
            )
        )
        rows.append(_shadow_row(chromium, root, variant))
        rows.append(_calls_row(chromium, root, base_url, variant))
    rows += _raw_rows(root, variant)
    return rows


def _shadow_row(chromium, root, variant):
    status, headers, body = http_get(f"{root}/staff")
    answered = "staff route" if "staff-route-answered" in body else "something else"
    h_status, h_spans, h_banner, h_error = _load(
        chromium, f"{root}/", "Server check", LOAD_TIMEOUT_MS
    )
    ok = "staff-route-answered" in body and h_error is None and not h_banner
    return _row(
        "S2c",
        variant,
        ok,
        f"GET /staff: status {status}, answered by {answered}, "
        f"content-type {headers.get('content-type')}. "
        f"/: status {h_status}, error {h_error}, banner {h_banner}",
    )


def _calls_row(chromium, root, base_url, variant):
    try:
        with uplink(base_url) as server:
            server.call("spike_reset")
            _status, _spans_, _banner, error = _load(
                chromium, f"{root}/{SLUG}", VALUE, LOAD_TIMEOUT_MS
            )
            calls = server.call("spike_calls")
    except Exception as exc:
        return _row(
            "S2d", variant, False, f"uplink failed: {type(exc).__name__}: {exc}"
        )
    return _row(
        "S2d",
        variant,
        error is None and len(calls) == 1,
        f"lookup calls recorded for one cold load of /{SLUG}: {len(calls)} "
        f"{calls}, wait error {error}",
    )


def _raw_rows(root, variant):
    status, headers, body = http_get(f"{root}/raw/{SLUG}")
    content_type = headers.get("content-type", "")
    s3a = _row(
        "S3a",
        variant,
        status == 200 and content_type.startswith("text/html") and VALUE in body,
        f"GET /raw/{SLUG}: status {status}, content-type {content_type!r}, "
        f"body {body[:80]!r}",
    )
    status, headers, body = http_get(f"{root}/raw/spikeinvalid")
    s3b = _row(
        "S3b",
        variant,
        status == 404,
        f"GET /raw/spikeinvalid: status {status}, body {body[:80]!r}",
    )
    return [s3a, s3b]
