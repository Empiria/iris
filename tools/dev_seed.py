#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["anvil-uplink>=0.7.1"]
# ///
"""Seed the local stack over the dev uplink.

Phase 1 has no tables, so the round trip is the whole job here: connect to the
running app server, call the ping callable, expect "pong" and disconnect. That
is how the roadmap's "just seed" criterion is met for this phase.

Once the app has tables, rows go in from this script through app_tables on this
privileged uplink. Later phases add their seed data here.

The uplink key is a local-only value that matches the Containerfile. It is never
printed.
"""

import os
import sys
import threading

import anvil.server

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
    finally:
        anvil.server.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
