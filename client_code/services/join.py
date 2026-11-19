# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Join logic for a meeting link: name check, slug check, lookup and address.

Loads on both sides (Skulpt in the browser, CPython on the server), so it
imports only the sibling modules below and does no data access. The server
call is passed in as an argument, which also keeps this module unit-testable.
"""

from iris.services import passphrase, slugs, vdo  # pyright: ignore[reportAttributeAccessIssue]

# Whether the room, label and salt go after the "#" in the join address. True
# puts them in the fragment and False in the query string. A unit test pins the value.
JOIN_IN_FRAGMENT = True

# Equals limits.DISPLAY_NAME_MAX. This module may import only passphrase, slugs and
# vdo (a unit test pins that), so tests/unit/test_limits.py keeps the two equal.
NAME_MAX = 60
NAME_REQUIRED_MESSAGE = "Enter your name to join."

# One fixed message per refused unlock. The server never sends text for these,
# and nothing typed or received is ever put into them.
UNLOCK_MESSAGES = {
    "incorrect": "Incorrect passphrase. Check it and try again.",
    "throttled": "Too many attempts. Try again in a few minutes.",
    "empty": "Enter the passphrase.",
    "missing": "This meeting no longer exists.",
}


def clean_display_name(text):
    """The typed name, trimmed and safe to put in an address, or ValueError.

    Control characters become spaces, runs of whitespace collapse to one space,
    and the result is cut to `NAME_MAX` characters. An empty result raises ValueError.
    """
    if not isinstance(text, str):
        raise ValueError(NAME_REQUIRED_MESSAGE)
    spaced = slugs.control_chars_to_spaces(text)
    name = " ".join(spaced.split())[:NAME_MAX].strip()
    if name == "":
        raise ValueError(NAME_REQUIRED_MESSAGE)
    return name


def is_joinable_slug(slug):
    """True when `slug` has the shape of a usable slug and is not reserved."""
    return slugs.looks_like_slug(slugs.normalise(slug))


def load_meeting(slug, call):
    """Look up the room for `slug` with `call`, and report only a state.

    Returns {"state": "ready", "found": <reply>}, {"state": "locked"} for a
    permanent room that needs its passphrase, {"state": "missing"} or
    {"state": "error"}. Any failure becomes "error" with nothing else, so no
    message text can reach a page. A slug that cannot be a room never calls.
    """
    if not is_joinable_slug(slug):
        return {"state": "missing"}
    try:
        found = call("lookup_room", slugs.normalise(slug))
    except Exception:
        return {"state": "error"}
    if not isinstance(found, dict):
        return {"state": "missing"}
    if found.get("kind") == "permanent":
        if found.get("locked") is True:
            return {"state": "locked"}
        return {"state": "missing"}
    return {"state": "ready", "found": found}


def unlock(slug, text, call):
    """Send a typed passphrase for a locked room, and report only a state.

    Returns {"state": "ready", "found": <reply>} on a match, otherwise one of
    "incorrect", "throttled", "empty", "missing" or "error". The passphrase is
    normalised here and goes only to the server call. It is never returned, put
    in a state or in an address. Nothing typed, or too long, makes no call.
    """
    if not is_joinable_slug(slug):
        return {"state": "missing"}
    if isinstance(text, str) and len(text) > passphrase.MAX_INPUT:
        return {"state": "incorrect"}
    try:
        normalised = passphrase.normalise(text)
    except ValueError:
        return {"state": "empty"}
    try:
        reply = call("unlock_room", slugs.normalise(slug), normalised)
    except Exception:
        return {"state": "error"}
    if not isinstance(reply, dict):
        return {"state": "error"}
    if reply.get("ok") is True:
        found = reply.get("found")
        if isinstance(found, dict):
            return {"state": "ready", "found": found}
        return {"state": "error"}
    reason = reply.get("reason")
    if reply.get("ok") is False and reason in UNLOCK_MESSAGES:
        return {"state": reason}
    return {"state": "error"}


def join_url(found, name, in_fragment=None):
    """The address that hands a client to the room, or ValueError.

    Built only by `vdo.build_join_url`, which checks the origin and the profile
    again, so this module is never a second place that forms an address. A
    permanent room's random vdo.ninja password goes in only when the address
    puts the identity after "#". The typed passphrase never reaches this far.
    """
    if in_fragment is None:
        in_fragment = JOIN_IN_FRAGMENT
    return vdo.build_join_url(
        found["origin"],
        found["vdo_room"],
        found["profile"],
        clean_display_name(name),
        salt=found["salt"],
        password=found.get("password"),
        in_fragment=in_fragment,
    )


def is_http_url(url):
    """True for an http or https address, so no other scheme is handed off."""
    if not isinstance(url, str):
        return False
    return url.startswith("https://") or url.startswith("http://")
