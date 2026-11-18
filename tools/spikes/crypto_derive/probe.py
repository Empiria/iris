"""S1 and S3: PBKDF2 in the browser through anvil.js and call_js, and on the server.

Run it on the host with `just spike crypto_derive`, then `just spike-down`. The
overlay app routes / to a DeriveSpike form with four buttons and an output <pre>.
This probe clicks each button, reads the output line and checks the derived hex
against Python's hashlib.pbkdf2_hmac for the same inputs.

    S1a  crypto.subtle through anvil.js, called from a form with no .then()
    S1b  the same through call_js (and, as a fallback, anvil.js.window.irisDerive)
    S1c  both results at the fixed inputs equal hashlib.pbkdf2_hmac
    S3   the server's own hashlib.pbkdf2_hmac timings for 100k, 300k, 600k

It prints one line per case (`S1a PASS|FAIL <evidence>`) through the runner and
always returns every row, so a failing case does not stop the others.

The fixed inputs are made up and used nowhere else.
"""

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import FIRST_LOAD_TIMEOUT_MS, banner_detail, browser, watch  # noqa: E402

NEEDS_STACK = True

PASSPHRASE = "spike-pass-1234"
SALT = "iris:spike"
FIXED_ITERATIONS = 1000
CLICK_TIMEOUT_MS = 180_000


def reference_hex(passphrase=PASSPHRASE, salt=SALT, iterations=FIXED_ITERATIONS):
    """What the browser must return: PBKDF2-HMAC-SHA-256, 32 bytes, as hex."""
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode(), salt.encode(), iterations, 32
    ).hex()


def parse_fields(text: str) -> dict:
    """The `key=value` tokens of an output line. The first token (the case name)
    is kept under "case". `DONE` and tokens without `=` are skipped."""
    fields = {}
    tokens = text.split()
    if tokens:
        fields["case"] = tokens[0]
    for token in tokens[1:]:
        if "=" in token:
            key, _, value = token.partition("=")
            fields[key] = value
    return fields


def format_line(case: str, verdict: str, evidence: str) -> str:
    return f"{case} {verdict} {' '.join(str(evidence).split())}"


def timings(fields: dict) -> dict:
    """{iterations: ms} from the `ms<iterations>=<ms>` tokens."""
    found = {}
    for key, value in fields.items():
        if key.startswith("ms") and key[2:].isdigit() and value.isdigit():
            found[int(key[2:])] = int(value)
    return found


def check_s1a(fields: dict, expected: str):
    """(verdict, evidence) for S1a from the output fields."""
    got = fields.get("hex")
    times = timings(fields)
    if got is None:
        errors = {k: v for k, v in fields.items() if "error" in k}
        return "FAIL", f"no result from anvil.js: {errors or fields}"
    match = got == expected
    return (
        "PASS" if match and times else "FAIL",
        f"returned without .then(): hex {got}, equals hashlib {expected}: "
        f"{match}; ms by iterations {times}",
    )


def check_s1b(fields: dict, expected: str):
    """(verdict, evidence) for S1b: which of call_js and window worked."""
    worked = [n for n in ("call_js", "window") if fields.get(n) == "ok"]
    status = {n: fields.get(n, "missing") for n in ("call_js", "window")}
    got = fields.get("hex")
    if not worked or got is None:
        return "FAIL", f"neither call_js nor window.irisDerive returned: {status}"
    match = got == expected
    return (
        "PASS" if match else "FAIL",
        f"works: {worked} (first success {fields.get('via')}); status {status}; "
        f"hex {got}, equals hashlib {expected}: {match}; "
        f"ms by iterations {timings(fields)}",
    )


def check_s1c(fields: dict, expected: str):
    """(verdict, evidence) for S1c: every browser result equals hashlib."""
    results = {k: fields[k] for k in ("anvil_js", "call_js") if k in fields}
    errors = {k: v for k, v in fields.items() if k.endswith("_error")}
    mismatched = [k for k, v in results.items() if v != expected]
    ok = bool(results) and not mismatched
    return (
        "PASS" if ok else "FAIL",
        f"hashlib reference {expected}; browser results {results}; "
        f"mismatched {mismatched}; errors {errors}",
    )


def check_s3(fields: dict):
    """(verdict, evidence) for S3: the server's timings."""
    times = timings(fields)
    if not all(n in times for n in (100000, 300000, 600000)):
        return "FAIL", f"no timings: {fields}"
    return (
        "PASS",
        f"server hashlib.pbkdf2_hmac median of 3, ms by iterations {times}",
    )


def _click(page, label: str, case: str) -> dict:
    """Click the button and return the output line's fields once it says DONE."""
    page.get_by_role("button", name=label).click()
    page.wait_for_function(
        "([want]) => { const t = document.querySelector('pre').innerText;"
        " return t.startsWith(want) && t.includes('DONE'); }",
        arg=[case],
        timeout=CLICK_TIMEOUT_MS,
    )
    return parse_fields(page.locator("pre").inner_text())


def _rows(page, expected: str) -> list:
    steps = (
        ("S1a", "S1a anvil.js", lambda f: check_s1a(f, expected)),
        ("S1b", "S1b call_js", lambda f: check_s1b(f, expected)),
        ("S1c", "S1c both", lambda f: check_s1c(f, expected)),
        ("S3", "S3 server", check_s3),
    )
    rows = []
    for case, label, check in steps:
        try:
            verdict, evidence = check(_click(page, label, case))
        except Exception as exc:
            verdict = "FAIL"
            evidence = f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
        rows.append((case, verdict, evidence))
    return rows


def run(base_url):
    expected = reference_hex()
    page = None
    seen = []
    try:
        with browser() as chromium:
            page = chromium.new_context().new_page()
            seen = watch(page)
            page.goto(
                base_url, wait_until="domcontentloaded", timeout=FIRST_LOAD_TIMEOUT_MS
            )
            page.wait_for_selector("pre", timeout=FIRST_LOAD_TIMEOUT_MS)
            return _rows(page, expected)
    except Exception as exc:
        banner = banner_detail(page) if page else ""
        reason = (
            f"page did not load: {type(exc).__name__}: "
            f"{str(exc).splitlines()[0][:120]}; banner {banner}; console {seen[:4]}"
        )
        return [(case, "FAIL", reason) for case in ("S1a", "S1b", "S1c", "S3")]
