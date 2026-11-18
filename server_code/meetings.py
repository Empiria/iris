import anvil.server

from iris.services import permissions  # pyright: ignore[reportAttributeAccessIssue]
from iris.services.model.room import Room

MAX_TITLE_LENGTH = 80


def clean_title(text):
    """A meeting name safe to store: text, no control characters, at most 80 long."""
    if text is None:
        return ""
    if not isinstance(text, str):
        raise ValueError("Title must be text")
    spaced = "".join(" " if ord(ch) < 32 or ord(ch) == 127 else ch for ch in text)
    return spaced.strip()[:MAX_TITLE_LENGTH].strip()


@anvil.server.callable
def lookup_room(slug):
    """The room details a client needs to join `slug`, or None.

    Public on purpose: this is how a meeting link opens for someone who is not
    signed in. The reply is released only for an active recorded room, it holds
    only what a person with the link needs (the separate vdo_room, the title,
    the vdo.ninja origin, profile and salt), and `Room.lookup` enforces that.
    The callable exists so client code never imports a model whose table the
    client cannot read. A bad stored setting raises ValueError, which is not
    caught here and never reaches a page: the client turns any failure into a
    fixed error state.
    """
    if not isinstance(slug, str):
        return None
    return Room.lookup(slug)


@anvil.server.callable(require_user=permissions.is_staff)
def create_one_off_link(title=""):
    """Create a one-off meeting room and return its slug and title.

    Staff only. The runtime enforces `require_user`, and `Room.create_one_off`
    repeats the check, because a model method is callable on its own. The reply
    carries the slug and title only: the separate vdo_room never leaves the server.
    """
    return Room.create_one_off(title=clean_title(title))


@anvil.server.callable(require_user=permissions.is_staff)
def create_permanent_room(slug, title=""):
    """Create a permanent room with a readable slug and return its passphrase.

    Admins only. The runtime enforces `require_user`, and `Room.create_permanent`
    repeats the check. The reply carries the slug, the title and the generated
    passphrase, which this call shows exactly once: the table keeps only a slow
    hash. Slug problems raise ValueError with a message written for the person
    who typed the name.
    """
    if not isinstance(slug, str):
        raise ValueError("Enter a name for the room.")
    return Room.create_permanent(slug, title=clean_title(title))


@anvil.server.callable
def unlock_room(slug, passphrase):
    """Check a passphrase for a permanent room and return its join info.

    Public on purpose: a client without an account opens a permanent room here.
    The reply is {"ok": True, "found": {...}} for the right passphrase, or
    {"ok": False, "reason": ...} otherwise. `Room.unlock` does the checking and
    the throttling. The passphrase is never logged, stored or put in an error.
    """
    if not isinstance(slug, str):
        return {"ok": False, "reason": "missing"}
    return Room.unlock(slug, passphrase)
