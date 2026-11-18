# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from iris.services import (
    clipboard,  # pyright: ignore[reportAttributeAccessIssue]
)

from ._anvil_designer import CopyFieldTemplate


class CopyField(CopyFieldTemplate):
    """A read-only value with a Copy button that reports what really happened.

    Raises `copied` after a successful copy. `secret` styles the value as a
    passphrase. `clear()` empties the value and the message together.
    """

    def __init__(self, **properties):
        self.init_components(**properties)
        self._copied_text = str(properties.get("copied_text") or "Copied.")
        self._failed_text = str(
            properties.get("failed_text")
            or "Copy failed. It is selected, so press Ctrl+C or Cmd+C."
        )
        self.dom_nodes["label"].textContent = str(properties.get("label") or "")
        self.dom_nodes["copy_button"].textContent = str(
            properties.get("button_text") or "Copy"
        )
        if properties.get("secret"):
            self.dom_nodes["output"].classList.add("iris-secret-value")

    @property
    def value(self):
        return str(self.dom_nodes["output"].value or "")

    @value.setter
    def value(self, text):
        self.dom_nodes["output"].value = "" if text is None else str(text)

    def clear(self):
        self.value = ""
        self.result.clear()

    def copy(self):
        """Copy the value. On refusal, select it and say what to press."""
        self.result.clear()
        if clipboard.copy(self.value):
            self.result.show(self._copied_text)
            self.raise_event("copied")
        else:
            self.dom_nodes["output"].select()
            self.result.show(self._failed_text)

    def _on_copy(self, event, **properties):
        self.copy()
