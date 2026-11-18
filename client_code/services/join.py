"""Join logic for a meeting link: name check, slug check, lookup and address.

Loads on both sides (Skulpt in the browser, CPython on the server), so it
imports only the two sibling modules below and does no data access. The server
call is passed in as an argument, which also keeps this module unit-testable.
"""

from iris.services import slugs, vdo  # pyright: ignore[reportAttributeAccessIssue]

# Whether the room, label and salt go after the "#" in the join address. Read
# from the "Join URL parameters:" line of the Decisions block in
# 02-SPIKE-RESULTS.md: "fragment" gives True, "query" gives False.
JOIN_IN_FRAGMENT = True

NAME_MAX = 60
NAME_REQUIRED_MESSAGE = "Enter your name to join."


def clean_display_name(text):
    """The typed name, trimmed and safe to put in an address, or ValueError.

    Control characters become spaces, runs of whitespace collapse to one space,
    and the result is cut to 60 characters. An empty result raises ValueError.
    """
    if not isinstance(text, str):
        raise ValueError(NAME_REQUIRED_MESSAGE)
    spaced = "".join(" " if ord(ch) < 32 or ord(ch) == 127 else ch for ch in text)
    name = " ".join(spaced.split())[:NAME_MAX].strip()
    if name == "":
        raise ValueError(NAME_REQUIRED_MESSAGE)
    return name


def is_joinable_slug(slug):
    """True when `slug` has the shape of a usable slug and is not reserved."""
    return slugs.looks_like_slug(slugs.normalise(slug))


def load_meeting(slug, call):
    """Look up the room for `slug` with `call`, and report only a state.

    Returns {"state": "ready", "found": <reply>}, {"state": "missing"} or
    {"state": "error"}. Any failure becomes "error" with nothing else, so no
    message text can reach a page. A slug that cannot be a room never calls.
    """
    if not is_joinable_slug(slug):
        return {"state": "missing"}
    try:
        found = call("lookup_room", slugs.normalise(slug))
    except Exception:
        return {"state": "error"}
    if isinstance(found, dict):
        return {"state": "ready", "found": found}
    return {"state": "missing"}


def join_url(found, name, in_fragment=None):
    """The address that hands a client to the room, or ValueError.

    Built only by `vdo.build_join_url`, which checks the origin and the profile
    again, so this module is never a second place that forms an address.
    """
    if in_fragment is None:
        in_fragment = JOIN_IN_FRAGMENT
    return vdo.build_join_url(
        found["origin"],
        found["vdo_room"],
        found["profile"],
        clean_display_name(name),
        salt=found["salt"],
        in_fragment=in_fragment,
    )


def is_http_url(url):
    """True for an http or https address, so no other scheme is handed off."""
    if not isinstance(url, str):
        return False
    return url.startswith("https://") or url.startswith("http://")
