import datetime

import anvil.server
from anvil.tables import app_tables

from iris.services import permissions, slugs  # pyright: ignore[reportAttributeAccessIssue]
from iris.services.model.setting import Setting

_SLUG_ATTEMPTS = 10


class Room(app_tables.room.Row, buffered=True, attrs=True):
    """A meeting room. Both methods return plain dicts, not rows.

    The `room` table has no client access, so a client could not read a returned
    row. The dict carries only the fields the caller may see.
    """

    @anvil.server.server_method
    @classmethod
    def lookup(cls, slug):
        """Everything a join needs for `slug`, or None.

        Public by design: it is how a meeting link is opened. It returns None
        for a slug no staff member created, and for an inactive row, so an
        invented slug releases no vdo_room.
        """
        slug = slugs.normalise(slug)
        if not slugs.looks_like_slug(slug):
            return None
        row = app_tables.room.get(slug=slug)
        if row is None or row["active"] is not True:
            return None
        config = Setting.vdo_config()
        return {
            "vdo_room": row["vdo_room"],
            "title": row["title"],
            "origin": config["origin"],
            "profile": config["profile"],
            "salt": config["salt"],
        }

    @anvil.server.server_method
    @classmethod
    def create_one_off(cls, title=""):
        """Create a one-off room. Staff only. Returns its slug and title."""
        user = permissions.require_staff()
        slug = None
        for _ in range(_SLUG_ATTEMPTS):
            candidate = slugs.new_one_off_slug()
            if candidate in slugs.RESERVED_SLUGS:
                continue
            if app_tables.room.get(slug=candidate) is None:
                slug = candidate
                break
        if slug is None:
            raise RuntimeError("Could not find a free slug")
        # The table has no uniqueness constraint, so two staff creating links
        # at the same instant could in theory draw the same slug. At 31 ** 8
        # slugs the odds are negligible.
        app_tables.room.add_row(
            slug=slug,
            vdo_room=slugs.new_vdo_room(),
            title=title,
            kind="one-off",
            active=True,
            created_by=user["email"],
            created=datetime.datetime.now(),
        )
        return {"slug": slug, "title": title}
