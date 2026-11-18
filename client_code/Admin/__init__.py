# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from anvil_reactive.main import render_effect

from iris.services import (
    admin_session,  # pyright: ignore[reportAttributeAccessIssue]
    rooms_state,  # pyright: ignore[reportAttributeAccessIssue]
)

from ._anvil_designer import AdminTemplate


class Admin(AdminTemplate):
    """The admin page: it picks the card to show, and the cards do the work.

    SignInCard, CreateMeeting, RoomsList and CallSettings share the state in
    `rooms_state`. This form loads it when an admin is signed in, and the render
    effect drops it when no one is.
    """

    def __init__(self, **properties):
        self.init_components(**properties)
        self.signin_card.visible = False
        self.signin_card.add_event_handler("signed_in", self._on_signed_in)
        self.rooms_list.add_event_handler("rotated", self._on_rotated)
        self.add_event_handler("show", self.form_show)
        self.add_event_handler("hide", self.form_hide)

    def form_show(self, **event_args):
        if admin_session.state.status is None:
            admin_session.refresh()
        if admin_session.is_admin():
            rooms_state.load_all()

    def form_hide(self, **event_args):
        # Leaving the page drops the passphrase from it.
        rooms_state.clear_secret()

    @render_effect
    def _render(self):
        # Reads the signal, so it runs again whenever the sign-in state changes.
        # It only changes what shows: the server calls are in the handlers.
        known = admin_session.is_known()
        is_admin = admin_session.is_admin()
        self.loading_card.visible = not known
        self.signin_card.visible = known and not is_admin
        self.dom_nodes["signed_in_card"].hidden = not is_admin
        if is_admin:
            self.dom_nodes["signed_in_as"].textContent = "Signed in as " + str(
                admin_session.admin_email()
            )
        else:
            # Signed out: drop the rooms, the saved text and any passphrase.
            rooms_state.reset()

    def _on_signed_in(self, **event_args):
        rooms_state.load_all()

    def _on_rotated(self, **event_args):
        self.create_meeting.scroll_to_result()

    def _on_sign_out(self, event, **properties):
        admin_session.sign_out()
