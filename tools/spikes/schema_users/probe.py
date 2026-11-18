# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""S4 and S5: schema auto-migrate and Users sign-up controls, on a fresh database.

The container is removed afterwards. The addresses and passwords here are made
up and only ever exist in that throwaway database.
"""

from common import FIRST_LOAD_TIMEOUT_MS, browser, uplink

NEEDS_STACK = True

EMAIL = "spike-user@example.invalid"
PASSWORD = "spike-pass-1"
CLIENT_EMAIL = "client-attempt@example.invalid"


def _short(exc):
    return (
        f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}"
        if str(exc)
        else type(exc).__name__
    )


def _row(spike_id, ok, evidence):
    return (spike_id, "PASS" if ok else "FAIL", evidence)


def _s4a(server):
    from anvil.tables import app_tables

    try:
        added = app_tables.spike_row.add_row(name="x", n=1)
        count = len(list(app_tables.spike_row.search()))
        via_callable = server.call("spike_add_row")
    except Exception as exc:
        return _row("S4a", False, f"add_row on spike_row failed: {_short(exc)}")
    return _row(
        "S4a",
        True,
        f"fresh database, no manual table creation: add_row returned a row "
        f"(name={added['name']!r}), {count} row(s) found, callable add returned "
        f"{via_callable!r}. The image entrypoint always passes --auto-migrate and "
        f"--ignore-invalid-schema, so this does not show whether the second flag "
        f"was needed",
    )


def _signup_direct(server):
    import anvil.users

    try:
        user = anvil.users.signup_with_email(EMAIL, PASSWORD)
    except Exception as exc:
        return False, f"signup_with_email over uplink raised {_short(exc)}"
    return True, f"signup_with_email over uplink succeeded, user {user['email']!r}"


def _signup_callable(server, address):
    try:
        email = server.call("spike_signup", address, PASSWORD)
    except Exception as exc:
        return False, f"spike_signup callable over uplink raised {_short(exc)}"
    return True, f"spike_signup callable over uplink succeeded, user {email!r}"


def _s5c(base_url, server):
    from anvil.tables import app_tables

    try:
        with browser() as chromium:
            page = chromium.new_context().new_page()
            page.goto(
                base_url, wait_until="domcontentloaded", timeout=FIRST_LOAD_TIMEOUT_MS
            )
            page.wait_for_function(
                "/refused|allowed/.test(document.body.innerText)",
                timeout=FIRST_LOAD_TIMEOUT_MS,
            )
            text = page.get_by_text("Client sign-up attempt").first.inner_text()
    except Exception as exc:
        return _row("S5c", False, f"browser attempt failed to report: {_short(exc)}")
    created = app_tables.users.get(email=CLIENT_EMAIL) is not None
    refused = "refused" in text and not created
    return _row(
        "S5c",
        refused,
        f"client signup page text {text!r}; user row for the attempted address "
        f"exists: {created}",
    )


def _s5d(server, have_user):
    import anvil.users

    if not have_user:
        return _row(
            "S5d", False, "no user was created by S5a or S5b, so no login to test"
        )
    try:
        user = anvil.users.login_with_email(EMAIL, PASSWORD)
    except Exception as exc:
        return _row("S5d", False, f"login_with_email over uplink raised {_short(exc)}")
    return _row(
        "S5d",
        user is not None,
        f"login_with_email over uplink returned {user['email']!r}",
    )


def _s5e(server, logged_in):
    how = "login from S5d"
    if not logged_in:
        try:
            server.call("spike_force_login", EMAIL)
            how = "spike_force_login (no S5d login available)"
        except Exception as exc:
            return _row("S5e", False, f"could not log a user in: {_short(exc)}")
    try:
        before = server.call("spike_staff_only")
        refused_first = False
    except Exception as exc:
        before = _short(exc)
        refused_first = True
    from anvil.tables import app_tables

    row = app_tables.users.get(email=EMAIL)
    if row is None:
        return _row("S5e", False, f"no users row for {EMAIL}; first call: {before!r}")
    row["is_staff"] = True
    try:
        after = server.call("spike_staff_only")
        accepted = after == "staff-ok"
    except Exception as exc:
        after = _short(exc)
        accepted = False
    return _row(
        "S5e",
        refused_first and accepted,
        f"user via {how}. is_staff false: "
        f"{'refused' if refused_first else 'ALLOWED'} ({before!r}). is_staff true: "
        f"{'accepted' if accepted else 'REFUSED'} ({after!r})",
    )


def run(base_url):
    rows = []
    try:
        with uplink(base_url) as server:
            rows.append(_s4a(server))
            ok_a, text_a = _signup_direct(server)
            rows.append(_row("S5a", ok_a, text_a))
            # S5a may already have made EMAIL, so S5b uses its own address then.
            ok_b, text_b = _signup_callable(
                server, "spike-user-2@example.invalid" if ok_a else EMAIL
            )
            rows.append(_row("S5b", ok_b, text_b))
            rows.append(_s5c(base_url, server))
            logged = False
            d_row = _s5d(server, ok_a or ok_b)
            rows.append(d_row)
            logged = d_row[1] == "PASS"
            rows.append(_s5e(server, logged))
    except Exception as exc:
        rows.append(("S4a", "FAIL", f"uplink failed: {_short(exc)}"))
    seen = {r[0] for r in rows}
    expected = ("S4a", "S5a", "S5b", "S5c", "S5d", "S5e")
    rows.extend((i, "FAIL", "not reached") for i in expected if i not in seen)
    return sorted(rows, key=lambda r: r[0])
