# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Slug and vdo_room rules for meeting links.

Loads on both sides (Skulpt in the browser, CPython on the server). Random
generation only runs on the server, so `secrets` is loaded inside the
function that needs it.
"""

from iris.services import limits  # pyright: ignore[reportAttributeAccessIssue]

# 31 characters: no i, l, o, 0 or 1, which are easy to misread aloud or in print.
# 31 ** 8 is about 8.5e11 slugs.
ONE_OFF_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
ONE_OFF_LENGTH = 8

VDO_ROOM_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
VDO_ROOM_LENGTH = 20

MIN_SLUG_LENGTH = 3
MAX_SLUG_LENGTH = limits.SLUG_MAX

# Slugs that may never name a room, so a permanent room cannot shadow a page
# and the router's own routes keep priority over /:slug.
RESERVED_SLUGS = frozenset(
    [
        "admin",
        "staff",
        "login",
        "logout",
        "signup",
        "api",
        "app",
        "assets",
        "static",
        "theme",
        "help",
        "about",
        "new",
        "create",
        "health",
        "ping",
        "robots",
        "sitemap",
    ]
)

_SLUG_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789-"


def normalise(slug):
    """Lower-case and trim a slug. None becomes the empty string."""
    if slug is None:
        return ""
    return str(slug).strip().lower()


def looks_like_slug(slug):
    """True when `slug` has the shape of a usable slug and is not reserved."""
    if not isinstance(slug, str):
        return False
    if not MIN_SLUG_LENGTH <= len(slug) <= MAX_SLUG_LENGTH:
        return False
    if slug.startswith("-") or slug.endswith("-"):
        return False
    if any(ch not in _SLUG_CHARS for ch in slug):
        return False
    return slug not in RESERVED_SLUGS


def clean_room_slug(text):
    """Turn an admin-typed room name into a readable slug, or raise ValueError.

    The text is trimmed and lower-cased, and each run of spaces or underscores
    becomes one "-". The messages are written for the admin who typed the
    name. Uniqueness is not checked here: it needs the table, so the room model
    does it.
    """
    name = normalise(text)
    out = []
    in_gap = False
    for ch in name:
        if ch == "_" or ch.isspace():
            in_gap = True
            continue
        if in_gap:
            out.append("-")
            in_gap = False
        out.append(ch)
    if in_gap:
        # Trailing whitespace was already trimmed, so this only fires for a
        # trailing "_"; keep it visible so the dash check below refuses it.
        out.append("-")
    slug = "".join(out)

    if len(slug) < MIN_SLUG_LENGTH:
        raise ValueError(
            "Use at least " + str(MIN_SLUG_LENGTH) + " characters for the name."
        )
    if len(slug) > MAX_SLUG_LENGTH:
        raise ValueError(
            "Use at most " + str(MAX_SLUG_LENGTH) + " characters for the name."
        )
    if any(ch not in _SLUG_CHARS for ch in slug):
        raise ValueError("Use only letters, numbers and dashes in the name.")
    if slug.startswith("-") or slug.endswith("-"):
        raise ValueError("The name can't start or end with a dash.")
    if slug in RESERVED_SLUGS:
        raise ValueError("That name is reserved.")
    return slug


def random_string(alphabet, length):
    """Draw `length` characters from `alphabet` with a cryptographic source."""
    # `secrets` is server-only: Skulpt lacks it, and `anvil validate` rejects a
    # static import of it in client_code. This function only ever runs on the
    # server, so the module is fetched by name here.
    secrets = __import__("secrets")
    return "".join(secrets.choice(alphabet) for _ in range(length))


def new_one_off_slug():
    return random_string(ONE_OFF_ALPHABET, ONE_OFF_LENGTH)


def new_vdo_room():
    """A random room name for vdo.ninja, not derived from any slug."""
    return random_string(VDO_ROOM_ALPHABET, VDO_ROOM_LENGTH)
