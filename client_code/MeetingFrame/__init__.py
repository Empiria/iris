# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from anvil_reactive.main import render_effect, signal

from ._anvil_designer import MeetingFrameTemplate


class MeetingFrame(MeetingFrameTemplate):
    """The one iframe that holds the room.

    `src` is the component's declared property, held as a signal. It is empty
    until the Join page sets it after a person has pressed Join, so nothing asks
    for the camera or microphone before then. The effect copies it onto the
    iframe whenever it changes, once the form is on the page.
    """

    # The designer types the declared property as `property`, hence the ignore.
    src = signal("")  # pyright: ignore[reportAssignmentType]

    @render_effect
    def _apply(self):
        value = self.src
        if value:
            self.dom_nodes["frame"].setAttribute("src", str(value))

    def focus(self):
        """Move focus into the room, so the keyboard works there at once."""
        self.dom_nodes["frame"].focus()
