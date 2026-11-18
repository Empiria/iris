#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["anvil-uplink>=0.7.1"]
# ///
"""Seed the local stack over the dev uplink.

Connect to the running app server, call the ping callable, expect "pong", then
seed the rows the local stack needs. The app has tables now, so rows go in from
this script on the privileged uplink. Today that is the two dev accounts (a staff
user and a non-staff viewer, made by the same code as `just create-staff --dev`),
and one known join room with its two VDO.Ninja settings, so the join e2e tests
have a meeting to open. Later phases add their seed data here, each in its own
function.

The uplink key is a local-only value that matches the Containerfile. It is never
printed.
"""

import datetime
import os
import sys
import threading

import anvil.server
import anvil.users
import create_staff  # a sibling in tools/, first on sys.path when run by path
import stack_url
from anvil.tables import app_tables

KEY = os.environ.get("IRIS_UPLINK_KEY", "dev-uplink")
# The uplink URL comes from IRIS_UPLINK_URL, IRIS_URL or .anvil/stack-url (the stack's
# host port is random). Set by main(), so a missing stack is a clear error.
URL = ""

# How long to wait for the uplink to come up before giving up.
CONNECT_TIMEOUT_S = 20

# The join room the local stack always has. tests/e2e/test_join.py repeats these
# values, and a unit test keeps the two copies equal.
# The slug people open: /testslug. Not a generated one-off slug.
DEV_ROOM_SLUG = "testslug"
DEV_ROOM_TITLE = "Seeded test meeting"
# The VDO.Ninja room it hands off to: 20 characters, a-z and 0-9.
DEV_ROOM_VDO = "kdvx2p8wmq5rt7hzn3cj"
# A dev-only VDO.Ninja origin, not the default. http is allowed for 127.0.0.1.
# Its host differs from the page host (localhost), so a hand-off to it is easy
# to tell from a stay on the page.
DEV_VDO_ORIGIN = "http://127.0.0.1:3030"
# A dev copy of the room profile settings, stored as the vdo_profile setting.
DEV_VDO_PROFILE = (
    "ssq=-1&sharperscreen&rbr=50000&trb=50000&crb&codec=av1,vp9,vp8,h264&q=0"
)


def _unreachable_message() -> str:
    return (
        f"seed: could not reach the app server at {URL}; start the stack with 'just up'"
    )


def _give_up() -> None:
    """Watchdog: exit if the connection attempt hangs instead of failing."""
    print(_unreachable_message(), file=sys.stderr, flush=True)
    os._exit(1)


def _connect() -> bool:
    watchdog = threading.Timer(CONNECT_TIMEOUT_S, _give_up)
    watchdog.daemon = True
    watchdog.start()
    try:
        anvil.server.connect(KEY, url=URL)
    except Exception:
        print(_unreachable_message(), file=sys.stderr)
        return False
    finally:
        watchdog.cancel()
    return True


def _seed_accounts() -> None:
    """Ensure the dev staff and viewer accounts. Safe to run again."""
    staff = create_staff.ensure_staff(
        create_staff.DEV_STAFF_EMAIL,
        create_staff.DEV_STAFF_PASSWORD,
        anvil.server,
        app_tables,
    )
    print(f"seed: staff account ready ({create_staff.DEV_STAFF_EMAIL}, {staff})")
    viewer = create_staff.ensure_viewer(
        create_staff.DEV_VIEWER_EMAIL,
        create_staff.DEV_VIEWER_PASSWORD,
        anvil.users,
        app_tables,
    )
    print(f"seed: viewer account ready ({create_staff.DEV_VIEWER_EMAIL}, {viewer})")


def _put_setting(app_tables, key: str, value: str) -> None:
    row = app_tables.setting.get(key=key)
    if row is None:
        app_tables.setting.add_row(key=key, value=value)
    else:
        row["value"] = value


def seed_join_room(app_tables) -> str:
    """Ensure the known join room and the vdo origin and profile settings.

    Safe to run again: the room is found by slug and set to the constants, and
    each setting is updated or added. No vdo_salt row is written. Returns
    "created" when the room row was new, else "updated".
    """
    row = app_tables.room.get(slug=DEV_ROOM_SLUG)
    if row is None:
        app_tables.room.add_row(
            slug=DEV_ROOM_SLUG,
            vdo_room=DEV_ROOM_VDO,
            title=DEV_ROOM_TITLE,
            kind="one-off",
            active=True,
            created_by=create_staff.DEV_STAFF_EMAIL,
            created=datetime.datetime.now(),
        )
        result = "created"
    else:
        row["vdo_room"] = DEV_ROOM_VDO
        row["title"] = DEV_ROOM_TITLE
        row["kind"] = "one-off"
        row["active"] = True
        result = "updated"
    _put_setting(app_tables, "vdo_origin", DEV_VDO_ORIGIN)
    _put_setting(app_tables, "vdo_profile", DEV_VDO_PROFILE)
    return result


def main() -> int:
    global URL
    try:
        URL = stack_url.uplink_url(os.environ)
    except stack_url.NoStack as error:
        print(f"seed: {error}", file=sys.stderr)
        return 1
    # anvil-uplink retries a dropped connection on a non-daemon thread, which
    # keeps the process alive after the work is done. Turn that off.
    anvil.server.reconnect = lambda closed_connection: None
    try:
        if not _connect():
            return 1
        reply = anvil.server.call("ping")
        if reply != "pong":
            print(f"seed: unexpected ping reply {reply!r}")
            return 1
        print("seed: uplink round trip ok (ping -> pong)")
        _seed_accounts()
        result = seed_join_room(app_tables)
        print(f"seed: join room ready ({DEV_ROOM_SLUG}, {result})")
    finally:
        anvil.server.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
