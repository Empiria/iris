# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Build the shareable link for a meeting slug.

Loads on both sides (Skulpt in the browser, CPython on the server), so it has no
server-only import and does no data access.
"""

from iris.services import slugs  # pyright: ignore[reportAttributeAccessIssue]

# Who owns the meeting route. One of "runtime" (a Routing route), "own" (an
# @anvil.server.route) or "query" (/?m=<slug>). The first two give
# <base>/<slug>, "query" gives <base>/?m=<slug>.
ROUTE_OWNER = "runtime"

_PATH_OWNERS = ("runtime", "own")
_OWNERS = _PATH_OWNERS + ("query",)


def link_for(base, slug, owner):
    """The link for `slug` under `base`, shaped by who owns the route.

    The slug is lower-cased and trimmed, then must be letters, digits or "-", so
    plain concatenation is safe with no URL quoting.
    """
    if owner not in _OWNERS:
        raise ValueError("Unknown route owner")
    clean = slugs.normalise(slug)
    if clean == "":
        raise ValueError("Slug is empty")
    for char in clean:
        if char not in slugs.SLUG_CHARS:
            raise ValueError("Slug has a character that is not allowed")
    root = str(base or "").rstrip("/")
    if root == "":
        raise ValueError("Base is empty")
    if owner in _PATH_OWNERS:
        return root + "/" + clean
    return root + "/?m=" + clean


def base_from_location(origin, pathname):
    """The app root from a page location: the origin plus any app-key prefix.

    Drops a trailing "/admin" (or the older "/staff") and trailing slashes from
    the pathname, so ("https://x.anvil.app", "/KEY/admin") gives
    "https://x.anvil.app/KEY".
    """
    path = str(pathname or "").rstrip("/")
    for suffix in ("/admin", "/staff"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    path = path.rstrip("/")
    return str(origin or "").rstrip("/") + path
