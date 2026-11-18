# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import anvil.server

from iris.services import (
    handoff,  # pyright: ignore[reportAttributeAccessIssue]
    join,  # pyright: ignore[reportAttributeAccessIssue]
)

from ._anvil_designer import JoinTemplate

NOT_SET_UP_MESSAGE = "This meeting is not set up correctly. Ask your host."
UNLOCK_ERROR_MESSAGE = "Could not open the meeting. Try again in a moment."
# A permanent room's card never shows its title: the title is released only with
# the passphrase, so this generic heading is all a locked room can show.
LOCKED_HEADING = "Join meeting"
LOCKED_LEDE = "Enter the passphrase you were given and your name to join."
READY_LEDE = "Enter your name to join the meeting."


class Join(JoinTemplate):
    def __init__(self, routing_context=None, **properties):
        self.routing_context = routing_context
        self.found = None
        self.slug = None
        self.locked = False
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)

    def _route_data(self):
        """The route's loaded state, or a fresh lookup when there is none."""
        context = self.routing_context
        data = context.data if context else None
        if data is not None:
            return data
        slug = context.params["slug"] if context else None
        return join.load_meeting(slug, anvil.server.call)

    def _show_only(self, card):
        for name in ("loading_card", "join_card", "missing_card", "error_card"):
            self.dom_nodes[name].hidden = name != card

    def _show_locked(self, locked):
        self.locked = locked
        self.dom_nodes["passphrase_field"].hidden = not locked
        self.dom_nodes["join_lede"].textContent = LOCKED_LEDE if locked else READY_LEDE

    def form_show(self, **event_args):
        data = self._route_data()
        state = data["state"]
        if state == "ready":
            self.found = data["found"]
            title = str(self.found["title"] or "").strip()
            self.dom_nodes["meeting_title"].textContent = title or "Your meeting"
            self._show_locked(False)
            self._show_only("join_card")
        elif state == "locked":
            context = self.routing_context
            self.slug = context.params["slug"] if context else None
            self.dom_nodes["meeting_title"].textContent = LOCKED_HEADING
            self._show_locked(True)
            self._show_only("join_card")
        elif state == "missing":
            self._show_only("missing_card")
        else:
            self._show_only("error_card")

    def _show_message(self, text):
        message = self.dom_nodes["join_message"]
        message.textContent = text
        message.hidden = text == ""

    def _unlock(self):
        """Send the typed passphrase and return the room's details, or None.

        The field is cleared as soon as the call returns, so the passphrase is
        in the page only for as long as the person is typing it. A refusal shows
        its fixed message and puts the cursor back in the field.
        """
        field = self.dom_nodes["passphrase_input"]
        result = join.unlock(self.slug, str(field.value or ""), anvil.server.call)
        field.value = ""
        state = result["state"]
        if state == "ready":
            return result["found"]
        self._show_message(join.UNLOCK_MESSAGES.get(state, UNLOCK_ERROR_MESSAGE))
        field.focus()
        return None

    def _on_submit(self, event, **properties):
        event.preventDefault()
        self._show_message("")
        try:
            name = join.clean_display_name(
                str(self.dom_nodes["name_input"].value or "")
            )
        except ValueError as error:
            self._show_message(str(error))
            return
        button = self.dom_nodes["join_button"]
        button.disabled = True
        if self.locked and self.found is None:
            self.found = self._unlock()
            if self.found is None:
                button.disabled = False
                return
        try:
            # Same call stack as the click, so the frame is made by a user gesture.
            how = handoff.start(join.join_url(self.found, name), self.meeting_frame)
        except ValueError:
            self._show_message(NOT_SET_UP_MESSAGE)
            button.disabled = False
            return
        if how == "iframe":
            self.dom_nodes["join_main"].hidden = True
            self.dom_nodes["frame_shell"].hidden = False
