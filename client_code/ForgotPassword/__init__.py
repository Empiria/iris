# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from anvil_reactive.main import render_effect, signal

from iris.services import (
    password_reset,  # pyright: ignore[reportAttributeAccessIssue]
)

from ._anvil_designer import ForgotPasswordTemplate


class ForgotPassword(ForgotPasswordTemplate):
    """The sign-in form's password-reset entry.

    `opened` is False until the person asks to reset, then the email form
    replaces the "Forgot password?" button and takes focus.
    """

    opened = signal(False)

    @render_effect
    def _render(self):
        opened = bool(self.opened)
        self.dom_nodes["reset_form"].hidden = not opened
        self.dom_nodes["open_button"].hidden = opened
        if opened:
            self.reset_email.focus()

    def __init__(self, **properties):
        self.init_components(**properties)

    def _on_open(self, event, **properties):
        self.opened = True

    def _on_submit(self, event, **properties):
        event.preventDefault()
        button = self.dom_nodes["reset_button"]
        button.disabled = True
        try:
            text = password_reset.request_reset(self.reset_email.value)
        except Exception:
            text = "Could not send the reset link. Try again later."
        finally:
            button.disabled = False
        self.reset_message.show(text)
