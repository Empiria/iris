# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from anvil.js import window
from anvil_reactive.main import render_effect

from iris.services import (
    links,  # pyright: ignore[reportAttributeAccessIssue]
    rooms_state,  # pyright: ignore[reportAttributeAccessIssue]
)

from ._anvil_designer import CreateMeetingTemplate


class CreateMeeting(CreateMeetingTemplate):
    """The form that makes a one-off link or a permanent room, and shows the result.

    The link and passphrase box shows `rooms_state.state.result`, so a rotated
    passphrase from the rooms list lands in the same box. Clearing the state
    clears the box, which is how a passphrase never outlives its room.
    """

    _shown = None

    def __init__(self, **properties):
        self.init_components(**properties)
        self._shown = None
        self.room_name_input.visible = False

    @render_effect
    def _render(self):
        self._show_result(rooms_state.state.result)

    def _show_result(self, result):
        # Compared by content: the state may hand back a wrapped copy.
        key = (
            None if result is None else (str(result["slug"]), str(result["passphrase"]))
        )
        if key == self._shown:
            return
        previous = self._shown
        self._shown = key
        if key is None:
            self.link_field.clear()
            self.passphrase_field.clear()
            self.dom_nodes["passphrase_box"].hidden = True
            self.dom_nodes["result_box"].hidden = True
            return
        slug, passphrase = key
        if passphrase != "" or previous is None or previous[0] != slug:
            self.link_field.result.clear()
        base = links.base_from_location(
            window.location.origin, window.location.pathname
        )
        self.link_field.value = links.link_for(base, slug, links.ROUTE_OWNER)
        if passphrase != "":
            self.passphrase_field.value = passphrase
        else:
            self.passphrase_field.clear()
        self.dom_nodes["passphrase_box"].hidden = passphrase == ""
        self.dom_nodes["result_box"].hidden = False

    def _wants_permanent(self):
        return bool(self.dom_nodes["kind_permanent"].checked)

    def _on_kind_change(self, event, **properties):
        permanent = self._wants_permanent()
        self.room_name_input.visible = permanent
        self.dom_nodes["create_button"].textContent = (
            "Create room" if permanent else "Create link"
        )
        self.create_message.clear()

    def _on_create(self, event, **properties):
        permanent = self._wants_permanent()
        self.create_message.clear()
        self.link_field.result.clear()
        button = self.dom_nodes["create_button"]
        button.disabled = True
        try:
            failure = rooms_state.create(
                permanent, self.room_name_input.value, self.title_input.value
            )
        finally:
            button.disabled = False
        if failure:
            self.create_message.show(failure)
            return
        # Effects run a moment after the write, and the copy needs the value now.
        self._show_result(rooms_state.state.result)
        self.link_field.copy()
        rooms_state.load_rooms()

    def scroll_to_result(self):
        """Bring the link and passphrase box into view."""
        self.dom_nodes["result_box"].scrollIntoView()
