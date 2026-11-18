# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from anvil_reactive.main import render_effect

from iris.services import (
    rooms_state,  # pyright: ignore[reportAttributeAccessIssue]
)

from ._anvil_designer import RoomsListTemplate


class RoomsList(RoomsListTemplate):
    """The admin's rooms, one RoomRow each.

    Shows `rooms_state.state.rooms` and its message, and raises `rotated` after
    a new passphrase is in the result box. The rows raise `x-edit`, `x-rotate`
    and `x-delete` on the panel, and the handlers pass them to `rooms_state`,
    which calls the server and updates the state.
    """

    def __init__(self, **properties):
        self.init_components(**properties)
        self.rooms_panel.add_event_handler("x-edit", self._on_row_edit)
        self.rooms_panel.add_event_handler("x-rotate", self._on_row_rotate)
        self.rooms_panel.add_event_handler("x-delete", self._on_row_delete)

    @render_effect
    def _render_rooms(self):
        rooms = rooms_state.state.rooms
        items = [] if rooms is None else list(rooms)
        self.rooms_panel.items = items
        self.dom_nodes["rooms_empty"].hidden = rooms is None or len(items) > 0

    @render_effect
    def _render_message(self):
        self.rooms_message.show(rooms_state.state.rooms_message)

    def _on_row_edit(self, slug=None, title="", **event_args):
        rooms_state.update_room(slug, title)

    def _on_row_delete(self, slug=None, **event_args):
        rooms_state.delete_room(slug)

    def _on_row_rotate(self, slug=None, **event_args):
        rooms_state.rotate_passphrase(slug)
        if rooms_state.state.result is not None:
            self.raise_event("rotated")
