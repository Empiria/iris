# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from anvil.js import window
from anvil_reactive.main import render_effect, signal

from iris.services import (
    clipboard,  # pyright: ignore[reportAttributeAccessIssue]
    links,  # pyright: ignore[reportAttributeAccessIssue]
    rooms_state,  # pyright: ignore[reportAttributeAccessIssue]
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

    # What the row is doing: "idle", "editing", or "rotate" / "delete" while it
    # waits for confirmation. `_show_mode` is the only code that acts on it.
    mode = signal("idle")
    # The button that opened the current mode, so focus can go back to it.
    _opener = ""

    def __init__(self, **properties):
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)
        self.confirm_bar.set_event_handler("confirm", self._on_confirm)
        self.confirm_bar.set_event_handler("cancel", self._on_cancel)

    def form_show(self, **event_args):
        # `item` is set by the panel after construction, so this is the first
        # point where the row can be drawn.
        self._render()

    @render_effect
    def _show_mode(self):
        mode = self.mode
        asking = mode in ("rotate", "delete")
        self.dom_nodes["edit_box"].hidden = mode != "editing"
        self.dom_nodes["room_actions"].hidden = mode != "idle"
        if mode == "rotate":
            self.confirm_bar.ask(ROTATE_WARNING, "Rotate now")
        elif mode == "delete":
            self.confirm_bar.ask(DELETE_WARNING, "Delete now")
        elif not asking:
            self.confirm_bar.dismiss()
        if mode == "editing":
            self.title_input.focus()
        elif mode == "idle" and self._opener:
            # Back to the plain row: put the cursor on the button that was used.
            opener = self._opener
            self._opener = ""
            if opener == "edit_button":
                self.dom_nodes["edit_button"].focus()
            elif opener == "rotate_button":
                self.dom_nodes["rotate_button"].focus()
            elif opener == "delete_button":
                self.dom_nodes["delete_button"].focus()

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
        self.dom_nodes["reveal_button"].hidden = not permanent

    def _tell_parent(self, name, **event_args):
        """Raise an event on the panel that holds this row, if it has one."""
        parent = self.parent
        if parent is not None:
            parent.raise_event(name, **event_args)

    def _show_message(self, text):
        self.row_message.show(text)

    def _on_copy(self, event, **properties):
        link = str(self.dom_nodes["room_link"].textContent or "")
        if clipboard.copy(link):
            self._show_message("Link copied.")
        else:
            self._show_message(
                "Copy failed. Select the link and press Ctrl+C or Cmd+C."
            )

    def _on_reveal(self, event, **properties):
        self._show_message("")
        status, text = rooms_state.reveal_passphrase(self._slug())
        if status != "ok":
            # A room with no stored passphrase, or a failure: the message says
            # which, and for the first it points at Rotate.
            self._show_message(text)
            return
        self.reveal_field.value = text
        self.dom_nodes["reveal_box"].hidden = False
        self.dom_nodes["reveal_button"].hidden = True
        self.dom_nodes["hide_button"].focus()

    def _on_hide(self, event, **properties):
        self.reveal_field.clear()
        self.dom_nodes["reveal_box"].hidden = True
        self.dom_nodes["reveal_button"].hidden = False
        self.dom_nodes["reveal_button"].focus()

    def _on_edit(self, event, **properties):
        self._show_message("")
        self.title_input.value = str(self._room().get("title") or "")
        self._opener = "edit_button"
        self.mode = "editing"

    def _on_save(self, event, **properties):
        title = self.title_input.value
        self.mode = "idle"
        self._tell_parent("x-edit", slug=self._slug(), title=title)

    def _on_rotate(self, event, **properties):
        self._show_message("")
        self._opener = "rotate_button"
        self.mode = "rotate"

    def _on_delete(self, event, **properties):
        self._show_message("")
        self._opener = "delete_button"
        self.mode = "delete"

    def _on_cancel(self, event=None, **properties):
        self.mode = "idle"

    def _on_confirm(self, event=None, **properties):
        kind = self.mode
        self._opener = ""
        self.mode = "idle"
        if kind == "rotate":
            self._tell_parent("x-rotate", slug=self._slug())
        elif kind == "delete":
            self._tell_parent("x-delete", slug=self._slug())
