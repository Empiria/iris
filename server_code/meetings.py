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
