# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from ._anvil_designer import MessageTemplate


class Message(MessageTemplate):
    """A line of feedback that screen readers announce when its text changes.

    The element stays in the page, empty, so the live region exists before the
    text arrives. Hiding it with `hidden` and filling it in one go is not
    announced reliably. `level` is "status" (polite) or "alert" (assertive).
    """

    def __init__(self, **properties):
        self.init_components(**properties)
        role = "alert" if properties.get("level") == "alert" else "status"
        self.dom_nodes["message"].setAttribute("role", role)

    def show(self, text):
        self.dom_nodes["message"].textContent = "" if text is None else str(text)

    def clear(self):
        self.show("")

    @property
    def text(self):
        return str(self.dom_nodes["message"].textContent or "")
