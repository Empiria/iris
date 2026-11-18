from iris.services import (
    password_reset,  # pyright: ignore[reportAttributeAccessIssue]
)

from ._anvil_designer import ForgotPasswordTemplate


class ForgotPassword(ForgotPasswordTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)

    def _on_open(self, event, **properties):
        self.dom_nodes["reset_form"].hidden = False
        self.dom_nodes["open_button"].hidden = True

    def _on_submit(self, event, **properties):
        event.preventDefault()
        message = self.dom_nodes["reset_message"]
        button = self.dom_nodes["reset_button"]
        button.disabled = True
        try:
            text = password_reset.request_reset(self.dom_nodes["reset_email"].value)
        except Exception:
            text = "Could not send the reset link. Try again later."
        finally:
            button.disabled = False
        message.textContent = text
        message.hidden = False
