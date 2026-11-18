# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""S6: does a vdo.ninja URL fragment win over the query, and which names does it read?

No stack is needed. The origin comes from IRIS_VDO_ORIGIN (default
https://vdo.ninja), so a self-hosted build can be measured the same way.
"""

import os
import re

from common import LOAD_TIMEOUT_MS, browser, http_get

NEEDS_STACK = False

WANTED = (
    "room",
    "label",
    "relay",
    "privacy",
    "private",
    "icefilter",
    "tcp",
    "turn",
    "stun",
)
REQUIRED = ("room", "label", "relay", "privacy", "icefilter")
CALL = re.compile(r"""urlParams\.(?:get|has)\(\s*["']([A-Za-z0-9_]+)["']""")
EXPRESSION = 'urlParams.get("label")'


def _origin() -> str:
    return os.environ.get("IRIS_VDO_ORIGIN", "https://vdo.ninja").rstrip("/")


def _parsed_label(page, url):
    """Load url and return (value, error). error is None when the read worked."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT_MS)
        page.wait_for_function(
            "typeof urlParams !== 'undefined'", timeout=LOAD_TIMEOUT_MS
        )
        return page.evaluate(EXPRESSION), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"


def _label_row(spike_id, page, url, expect):
    value, error = _parsed_label(page, url)
    if error:
        return (spike_id, "FAIL", f"{url} could not be read ({error})")
    verdict = "PASS" if value == expect else "FAIL"
    return (
        spike_id,
        verdict,
        f"{url} -> {EXPRESSION} = {value!r}, expected {expect!r}",
    )


def _names_row(origin):
    try:
        status, _headers, body = http_get(f"{origin}/main.js", timeout=60)
    except Exception as exc:
        return (
            "S6c",
            "FAIL",
            f"fetching {origin}/main.js failed: {type(exc).__name__}: {exc}",
        )
    found = sorted(set(CALL.findall(body)))
    wanted = [n for n in found if n in WANTED]
    meshcast = [n for n in found if n.startswith("meshcast")]
    missing = [n for n in REQUIRED if n not in found]
    not_found = [n for n in WANTED if n not in found]
    verdict = "PASS" if status == 200 and not missing else "FAIL"
    return (
        "S6c",
        verdict,
        f"{origin}/main.js status {status}, {len(body)} bytes. "
        f"Wanted names found: {wanted}. Not found: {not_found}. "
        f"meshcast names: {meshcast}. Required missing: {missing}",
    )


def run(base_url):
    origin = _origin()
    rows = []
    try:
        with browser() as chromium:
            page = chromium.new_context().new_page()
            rows.append(
                _label_row(
                    "S6a",
                    page,
                    f"{origin}/?room=irisspike#label=FragmentName",
                    "FragmentName",
                )
            )
            rows.append(
                _label_row(
                    "S6b",
                    page,
                    f"{origin}/?room=irisspike&label=QueryName#label=FragmentName",
                    "FragmentName",
                )
            )
    except Exception as exc:
        reason = (
            f"browser failed: {type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
        )
        rows += [
            (i, "FAIL", reason) for i in ("S6a", "S6b") if i not in [r[0] for r in rows]
        ]
    rows.append(_names_row(origin))
    return rows
