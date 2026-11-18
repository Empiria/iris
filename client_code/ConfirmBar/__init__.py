# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from ._anvil_designer import ConfirmBarTemplate


class ConfirmBar(ConfirmBarTemplate):
    """An in-place "are you sure" for a destructive action.

    Hidden until `ask()`. Raises `confirm` or `cancel` and hides itself, so
    the page that holds it only decides what to do next.
    """

    def __init__(self, **properties):
        self.init_components(**properties)
        self.visible = False

    def ask(self, text, confirm_label, cancel_label="Keep it"):
        self.dom_nodes["text"].textContent = str(text)
        self.dom_nodes["confirm_button"].textContent = str(confirm_label)
        self.dom_nodes["cancel_button"].textContent = str(cancel_label)
        self.visible = True
        self.dom_nodes["cancel_button"].focus()

    def dismiss(self):
        self.visible = False

    def _on_confirm(self, event, **properties):
        self.dismiss()
        self.raise_event("confirm")

    def _on_cancel(self, event, **properties):
        self.dismiss()
        self.raise_event("cancel")
