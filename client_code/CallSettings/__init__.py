# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from anvil_reactive.main import render_effect

from iris.services import (
    rooms_state,  # pyright: ignore[reportAttributeAccessIssue]
)

from ._anvil_designer import CallSettingsTemplate


class CallSettings(CallSettingsTemplate):
    """The vdo.ninja parameters added to every meeting link.

    Shows `rooms_state.state.profile`. The box is locked until the saved text
    has arrived, so a late answer can't overwrite what the admin has typed.
    """

    def __init__(self, **properties):
        self.init_components(**properties)

    @render_effect
    def _render_saved(self):
        # Reads only the saved text, so a message alone never rewrites the box.
        saved = rooms_state.state.profile
        loaded = saved is not None
        self.dom_nodes["profile_input"].value = str(saved) if loaded else ""
        self.dom_nodes["profile_input"].disabled = not loaded
        self.dom_nodes["profile_save"].disabled = not loaded

    @render_effect
    def _render_message(self):
        self.profile_message.show(rooms_state.state.profile_message)

    def _on_save(self, event, **properties):
        text = str(self.dom_nodes["profile_input"].value or "")
        button = self.dom_nodes["profile_save"]
        button.disabled = True
        try:
            rooms_state.save_profile(text)
        finally:
            button.disabled = False
        # The server's normalised text, even when it equals the stored one.
        saved = rooms_state.state.profile
        if saved is not None:
            self.dom_nodes["profile_input"].value = str(saved)
