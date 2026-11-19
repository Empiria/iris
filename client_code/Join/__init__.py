# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import anvil.server
from anvil_reactive.main import render_effect, signal

from iris.services import (
    handoff,  # pyright: ignore[reportAttributeAccessIssue]
    join,  # pyright: ignore[reportAttributeAccessIssue]
    vdo,  # pyright: ignore[reportAttributeAccessIssue]
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
    """The join page. One `state` signal says what the page shows.

    "loading" until the lookup answers, then "ready", "locked", "missing" or
    "error". "joined" once the room is on screen in the page. `_render` is the
    only code that shows or hides a card, and the only place focus moves when
    the state changes.
    """

    state = signal("loading")

    def __init__(self, routing_context=None, **properties):
        self.routing_context = routing_context
        self.found = None
        self.overrides = ""
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)

    @render_effect
    def _render(self):
        state = self.state
        card_up = state in ("ready", "locked")
        self.dom_nodes["join_main"].hidden = state == "joined"
        self.dom_nodes["frame_shell"].hidden = state != "joined"
        self.dom_nodes["join_card"].hidden = not card_up
        self.loading_card.visible = state == "loading"
        self.missing_card.visible = state == "missing"
        self.error_card.visible = state == "error"
        locked = state == "locked"
        self.passphrase_input.visible = locked
        if card_up:
            self.dom_nodes["meeting_title"].textContent = self._title
            self.dom_nodes["join_lede"].textContent = (
                LOCKED_LEDE if locked else READY_LEDE
            )
            (self.passphrase_input if locked else self.name_input).focus()
        elif state == "missing":
            self.missing_card.focus()
        elif state == "error":
            self.error_card.focus()
        elif state == "joined":
            self.meeting_frame.focus()

    _title = ""

    def _route_data(self):
        """The route's loaded state, or a fresh lookup when there is none."""
        context = self.routing_context
        data = context.data if context else None
        if data is not None:
            return data
        slug = context.params["slug"] if context else None
        return join.load_meeting(slug, anvil.server.call)

    def _slug(self):
        context = self.routing_context
        return context.params["slug"] if context else None

    def _read_overrides(self):
        """Take the page address's query as settings for this visit's room link.

        Read from the raw address, because the router turns `q=2` into a number.
        Anything not allowed is dropped, and the person is told which keys.
        """
        try:
            from anvil.js import window

            self.overrides, ignored = vdo.parse_overrides(window.location.search)
        except Exception:
            self.overrides, ignored = "", []
        self._notice = vdo.override_notice(ignored)
        self.override_note.show(self._notice)

    _notice = ""

    def form_show(self, **event_args):
        self._read_overrides()
        try:
            data = self._route_data()
            state = data["state"]
            if state == "ready":
                self.found = data["found"]
                title = str(self.found["title"] or "").strip()
                self._title = title or "Your meeting"
            elif state == "locked":
                self._title = LOCKED_HEADING
        except Exception:
            state = "error"
        if state not in ("ready", "locked", "missing"):
            state = "error"
        self.state = state

    def _show_message(self, text):
        self.join_message.show(text)

    def _unlock(self):
        """Send the typed passphrase and return the room's details, or None.

        The field is cleared as soon as the call returns, so the passphrase is
        in the page only for as long as the person is typing it. A refusal shows
        its fixed message and puts the cursor back in the field.
        """
        field = self.passphrase_input
        result = join.unlock(self._slug(), field.value, anvil.server.call)
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
            name = join.clean_display_name(self.name_input.value)
        except ValueError as error:
            self._show_message(str(error))
            self.name_input.focus()
            return
        button = self.dom_nodes["join_button"]
        button.disabled = True
        try:
            if self.state == "locked" and self.found is None:
                self.found = self._unlock()
                if self.found is None:
                    return
            # Same call stack as the click, so the frame is made by a user gesture.
            url = join.join_url(self.found, name, overrides=self.overrides)
            # Built before the hand-off so a bad override fails here, not mid-call.
            self.full_link.value = join.display_url(
                self.found, name, overrides=self.overrides
            )
            self.fulllink_ignored.show(self._notice)
            how = handoff.start(url, self.meeting_frame)
            if how == "iframe":
                self.state = "joined"
        except ValueError:
            self._show_message(NOT_SET_UP_MESSAGE)
        except Exception:
            self._show_message(UNLOCK_ERROR_MESSAGE)
        finally:
            button.disabled = False

    def _on_fulllink_toggle(self, event, **properties):
        panel = self.dom_nodes["fulllink_panel"]
        panel.hidden = not panel.hidden
        self.dom_nodes["fulllink_toggle"].setAttribute(
            "aria-expanded", "false" if panel.hidden else "true"
        )
