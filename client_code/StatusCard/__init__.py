# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from ._anvil_designer import StatusCardTemplate


class StatusCard(StatusCardTemplate):
    """A card with an optional heading and one line of text.

    For the page states that only inform: loading, no such meeting, an error.
    Show and hide it with `visible`.
    """

    def __init__(self, **properties):
        self.init_components(**properties)
        self.set_content(properties.get("heading"), properties.get("text"))

    def set_content(self, heading, text):
        title = self.dom_nodes["heading"]
        title.textContent = "" if heading is None else str(heading)
        title.hidden = not title.textContent
        self.dom_nodes["body"].textContent = "" if text is None else str(text)
