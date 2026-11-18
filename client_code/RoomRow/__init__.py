# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from anvil.js import window

from iris.services import (
    clipboard,  # pyright: ignore[reportAttributeAccessIssue]
    links,  # pyright: ignore[reportAttributeAccessIssue]
)

from ._anvil_designer import RoomRowTemplate

DELETE_WARNING = "Delete this room? Its link stops working for good."
ROTATE_WARNING = (
    "Rotate the passphrase? The old passphrase stops working at once,"
    " and anyone in the room has to rejoin with the new one."
)


def _date_text(moment):
    """A plain "YYYY-MM-DD" for a datetime, or "" when there is none."""
    if moment is None:
        return ""
    year = str(moment.year).zfill(4)
    month = str(moment.month).zfill(2)
    day = str(moment.day).zfill(2)
    return year + "-" + month + "-" + day


class RoomRow(RoomRowTemplate):
    """One line of the rooms list.

    A RepeatingPanel creates it with `item` set to the room summary: the slug,
    title, kind and created time, and nothing secret. The buttons raise
    `x-edit`, `x-rotate` and `x-delete` on the parent panel, and the page that
    holds the list calls the server and reloads it. The row itself never calls
    the server.
    """

    _pending = ""

    def __init__(self, **properties):
        self.init_components(**properties)
        self._pending = ""
        self.add_event_handler("show", self.form_show)
        self.confirm_bar.set_event_handler("confirm", self._on_confirm)
        self.confirm_bar.set_event_handler("cancel", self._on_cancel)
        self._render()

    def form_show(self, **event_args):
        self._render()

    def _room(self):
        found = getattr(self, "item", None)
        return found if found else {}

    def _slug(self):
        return str(self._room().get("slug") or "")

    def _is_permanent(self):
        return self._room().get("kind") == "permanent"

    def _render(self):
        room = self._room()
        slug = self._slug()
        if slug == "":
            return
        base = links.base_from_location(
            window.location.origin, window.location.pathname
        )
        link = links.link_for(base, slug, links.ROUTE_OWNER)
        anchor = self.dom_nodes["room_link"]
        anchor.textContent = link
        anchor.setAttribute("href", link)
        title = str(room.get("title") or "")
        self.dom_nodes["room_title"].textContent = title or "No meeting name"
        permanent = self._is_permanent()
        self.dom_nodes["room_kind"].textContent = (
            "Permanent room" if permanent else "One-off link"
        )
        created = _date_text(room.get("created"))
        self.dom_nodes["room_created"].textContent = (
            "Created " + created if created else ""
        )
        self.dom_nodes["rotate_button"].hidden = not permanent

    def _tell_parent(self, name, **event_args):
        """Raise an event on the panel that holds this row, if it has one."""
        parent = self.parent
        if parent is not None:
            parent.raise_event(name, **event_args)

    def _show_message(self, text):
        self.row_message.show(text)

    def _reset(self):
        """Back to the plain row: no edit box, no confirmation."""
        self._pending = ""
        self.dom_nodes["edit_box"].hidden = True
        self.confirm_bar.dismiss()
        self.dom_nodes["room_actions"].hidden = False

    def _ask(self, kind, warning, button_text):
        self._reset()
        self._pending = kind
        self.dom_nodes["room_actions"].hidden = True
        self.confirm_bar.ask(warning, button_text)

    def _on_copy(self, event, **properties):
        link = str(self.dom_nodes["room_link"].textContent or "")
        if clipboard.copy(link):
            self._show_message("Link copied.")
        else:
            self._show_message(
                "Copy failed. Select the link and press Ctrl+C or Cmd+C."
            )

    def _on_edit(self, event, **properties):
        self._show_message("")
        self._reset()
        field = self.title_input
        field.value = str(self._room().get("title") or "")
        self.dom_nodes["room_actions"].hidden = True
        self.dom_nodes["edit_box"].hidden = False
        field.focus()

    def _on_save(self, event, **properties):
        title = self.title_input.value
        self._reset()
        self._tell_parent("x-edit", slug=self._slug(), title=title)

    def _on_rotate(self, event, **properties):
        self._show_message("")
        self._ask("rotate", ROTATE_WARNING, "Rotate now")

    def _on_delete(self, event, **properties):
        self._show_message("")
        self._ask("delete", DELETE_WARNING, "Delete now")

    def _on_cancel(self, event=None, **properties):
        self._reset()

    def _on_confirm(self, event=None, **properties):
        kind = self._pending
        self._reset()
        if kind == "rotate":
            self._tell_parent("x-rotate", slug=self._slug())
        elif kind == "delete":
            self._tell_parent("x-delete", slug=self._slug())
