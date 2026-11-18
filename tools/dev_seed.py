#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["anvil-uplink>=0.7.1"]
# ///
"""Seed the local stack over the dev uplink.

Connect to the running app server, call the ping callable, expect "pong", then
seed the rows the local stack needs. The app has tables now, so rows go in from
this script on the privileged uplink. Today that is the two dev accounts (a staff
user and a non-staff viewer, made by the same code as `just create-staff --dev`).
Later phases add their seed data here, each in its own function.

The uplink key is a local-only value that matches the Containerfile. It is never
printed.
"""

import os
import sys
import threading

import anvil.server
import anvil.users
import create_staff  # a sibling in tools/, first on sys.path when run by path
from anvil.tables import app_tables

KEY = os.environ.get("IRIS_UPLINK_KEY", "dev-uplink")
URL = os.environ.get("IRIS_UPLINK_URL", "ws://localhost:3030/_/uplink")

# How long to wait for the uplink to come up before giving up.
CONNECT_TIMEOUT_S = 20


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


def main() -> int:
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
    finally:
        anvil.server.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
