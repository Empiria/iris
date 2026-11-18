# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""S7: can a script create the first staff user, and how do its inputs arrive?

Scripts live in the top-level scripts/ directory. anvil-app-server 1.17.0 has no
way to run one from a command line: it registers each as a background task named
script:<Name>, which only server code or an uplink can launch. So this probe
uses the uplink purely as the launcher and checks what the script itself does.
The addresses and passwords are made up and live only in the throwaway database.

One variant per way of getting the email and password in: args, declared (args,
with the script listed in .anvil_editor.yaml), env and secret (no launch
arguments at all) and generated (email argument, password printed); prompt probes
input().
"""

import os
import re
import subprocess
import time

from common import FIRST_LOAD_TIMEOUT_MS, browser, uplink

NEEDS_STACK = True
VARIANTS = ["args", "declared", "env", "secret", "generated", "prompt"]

EMAIL = "first-staff@example.invalid"
OTHER = "second-staff@example.invalid"
PLAIN = "plain-user@example.invalid"
CLIENT_EMAIL = "client-attempt@example.invalid"
ARG_PASSWORD = "arg-pass-12345"
ENV_PASSWORD = "env-pass-12345"
SECRET_PASSWORD = "secret-pass-12345"
WAIT_S = 60


def container_options(variant):
    if variant == "env":
        return {"IRIS_STAFF_EMAIL": EMAIL, "IRIS_STAFF_PASSWORD": ENV_PASSWORD}, []
    if variant == "secret":
        return {}, [
            "--secret",
            f"iris_staff_email={EMAIL}",
            "--secret",
            f"iris_staff_password={SECRET_PASSWORD}",
        ]
    return {}, []


def _short(exc):
    text = str(exc).splitlines()[0][:220] if str(exc) else ""
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


def _row(spike_id, ok, evidence):
    return (spike_id, "PASS" if ok else "FAIL", evidence)


def _logs():
    name = os.environ.get("IRIS_SPIKE_ACTIVE_CONTAINER", "")
    if not name:
        return ""
    out = subprocess.run(["podman", "logs", name], capture_output=True, text=True)
    raw = (out.stdout or "") + (out.stderr or "")
    # The app server puts each argument of a script's print() on its own log
    # line behind a [SERVER] tag. Joined back up, the text reads as printed.
    parts = [
        re.sub(r"^\[\w+ +[^\]]*\] \[SERVER\] ?", "", ln) for ln in raw.splitlines()
    ]
    return " ".join(" ".join(parts).split())


def _launch(server, script, *args):
    """Launch script:<script> and wait. Returns (status, error text, seconds)."""
    started = time.time()
    try:
        task = server.launch_background_task(f"script:{script}", *args)
    except Exception as exc:
        return "launch-raised", _short(exc), 0.0
    status = None
    while time.time() - started < WAIT_S:
        try:
            status = task.get_termination_status()
        except Exception as exc:
            return "status-raised", _short(exc), time.time() - started
        if status is not None:
            break
        time.sleep(1)
    error = ""
    if status not in (None, "completed"):
        try:
            error = str(task.get_error())[:220]
        except Exception as exc:
            error = f"get_error raised {_short(exc)}"
    return status or "still-running", error, time.time() - started


def _log_pass(logs, password):
    return "yes" if password in logs else "no"


def _create_rows(server, ids, password, source, launch_args):
    """Launch the script for EMAIL and check the user, the login and the refusal."""
    from anvil.tables import app_tables

    status, error, took = _launch(server, "CreateStaff", *launch_args)
    row = app_tables.users.get(email=EMAIL)
    created = row is not None
    staff = bool(created and row["is_staff"])
    has_hash = bool(created and row["password_hash"])
    shown = password
    if source == "generated":
        match = re.search(r"generated password: (\S+)", _logs())
        shown = match.group(1) if match else None
    rows = [
        _row(
            ids[0],
            status == "completed" and created and staff and has_hash,
            f"script:CreateStaff launched over the uplink with "
            f"{len(launch_args)} argument(s): termination status {status!r} "
            f"after {took:.0f}s{', error ' + error if error else ''}. users row "
            f"exists: {created}, is_staff: {staff}, password hash stored: "
            f"{has_hash}. Password source reported by the script: "
            f"{_source_line(_logs())}",
        )
    ]
    if shown is None:
        rows.append(_row(ids[1], False, "no generated password found in the log"))
        return rows, False
    rows.append(_login_row(server, ids[1], shown, source))
    return rows, created and staff


def _source_line(logs):
    match = re.search(r"created staff user \S+ password from (\w+)", logs)
    return match.group(1) if match else "(not in the container log)"


def _login_row(server, spike_id, password, source):
    import anvil.users

    try:
        user = anvil.users.login_with_email(EMAIL, password)
        staff_call = server.call("spike_staff_only")
        ok = user is not None and staff_call == "staff-ok"
        text = (
            f"login_with_email with the {source} password ok; staff-only call "
            f"returned {staff_call!r}"
        )
    except Exception as exc:
        ok, text = False, f"login or staff-only call raised {_short(exc)}"
    try:
        server.call("spike_force_login", PLAIN)
        plain = server.call("spike_staff_only")
        refused = False
        plain_text = f"ALLOWED ({plain!r})"
    except Exception as exc:
        refused = True
        plain_text = f"refused ({_short(exc)})"
    return _row(
        spike_id,
        ok and refused,
        f"{text}. A user row with is_staff false calling the same staff-only "
        f"callable: {plain_text}",
    )


def _second_run_row(server, spike_id):
    from anvil.tables import app_tables

    status, error, took = _launch(server, "CreateStaff", OTHER, "other-pass-12345")
    created = app_tables.users.get(email=OTHER) is not None
    staff_count = len([u for u in app_tables.users.search() if u["is_staff"]])
    return _row(
        spike_id,
        status != "completed" and not created and staff_count == 1,
        f"second launch with a staff user already present: status {status!r}, "
        f"error {error!r}; row for the second address exists: {created}; staff "
        f"users: {staff_count}",
    )


def _client_row(base_url, spike_id):
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
            text = page.get_by_text("Client launch of the script").first.inner_text()
    except Exception as exc:
        return _row(spike_id, False, f"browser attempt failed to report: {_short(exc)}")
    created = app_tables.users.get(email=CLIENT_EMAIL) is not None
    return _row(
        spike_id,
        "refused" in text and not created,
        f"client launch_background_task('script:CreateStaff') page text "
        f"{text!r}; user row for the attempted address exists: {created}",
    )


def _prompt_row(server, spike_id):
    from anvil.tables import app_tables

    status, error, took = _launch(server, "PromptProbe")
    logs = _logs()
    line = re.search(r"PROMPT-PROBE (.*?)(?: \[INFO|$)", logs)
    wrote = app_tables.spike_row.get(name="prompt") is not None
    reported = line.group(1) if line else "(nothing in the log)"
    return _row(
        spike_id,
        status == "completed" and wrote,
        f"PromptProbe: termination status {status!r} after {took:.0f}s, error "
        f"{error!r}; script reported {reported}; "
        f"it reached its last line: {wrote}",
    )


def _body(server, base_url, variant):
    if variant == "prompt":
        return [_prompt_row(server, "S7i")]
    if variant in ("args", "declared"):
        ids = ("S7a", "S7b") if variant == "args" else ("S7e", "S7e2")
        rows, made = _create_rows(
            server, ids, ARG_PASSWORD, "argument", (EMAIL, ARG_PASSWORD)
        )
        rows[0] = _append(
            rows[0],
            " Password string in the container log: "
            f"{_log_pass(_logs(), ARG_PASSWORD)}.",
        )
        if variant == "args":
            rows.append(_second_run_row(server, "S7c"))
            rows.append(_client_row(base_url, "S7d"))
        return rows
    if variant == "env":
        rows, _ = _create_rows(server, ("S7f", "S7f2"), ENV_PASSWORD, "environment", ())
        return rows
    if variant == "secret":
        rows, _ = _create_rows(server, ("S7g", "S7g2"), SECRET_PASSWORD, "secret", ())
        return rows
    rows, _ = _create_rows(server, ("S7h", "S7h2"), None, "generated", (EMAIL,))
    return rows


def _append(row, text):
    return (row[0], row[1], row[2] + text)


def run(base_url, variant):
    try:
        with uplink(base_url) as server:
            return _body(server, base_url, variant)
    except Exception as exc:
        return [(f"S7-{variant}", "FAIL", f"probe failed: {_short(exc)}")]
