"""Slug and vdo_room rules for meeting links.

Loads on both sides (Skulpt in the browser, CPython on the server). Random
generation only runs on the server, so `secrets` is imported inside the
function that needs it.
"""

# 31 characters: no i, l, o, 0 or 1, which are easy to misread aloud or in print.
# 31 ** 8 is about 8.5e11 slugs.
ONE_OFF_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
ONE_OFF_LENGTH = 8

VDO_ROOM_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
VDO_ROOM_LENGTH = 20

MIN_SLUG_LENGTH = 3
MAX_SLUG_LENGTH = 64

# Slugs that may never name a room, so a permanent room cannot shadow a page
# and the router's own routes keep priority over /:slug.
RESERVED_SLUGS = frozenset(
    [
        "staff",
        "admin",
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


def random_string(alphabet, length):
    """Draw `length` characters from `alphabet` with a cryptographic source."""
    import secrets

    return "".join(secrets.choice(alphabet) for _ in range(length))


def new_one_off_slug():
    return random_string(ONE_OFF_ALPHABET, ONE_OFF_LENGTH)


def new_vdo_room():
    """A random room name for vdo.ninja, not derived from any slug."""
    return random_string(VDO_ROOM_ALPHABET, VDO_ROOM_LENGTH)
