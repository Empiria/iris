# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from iris.services import (
    admin_session,  # pyright: ignore[reportAttributeAccessIssue]
)

from ._anvil_designer import SignInCardTemplate


class SignInCard(SignInCardTemplate):
    """The admin sign-in form and its password-reset entry.

    Raises `signed_in` once an admin has signed in. The password is read from the
    box, handed to the session and emptied again at once, whatever the outcome.
    """

    def __init__(self, **properties):
        self.init_components(**properties)

    def _on_submit(self, event, **properties):
        event.preventDefault()
        email = self.email_input.value.strip()
        password = self.password_input.value
        if email == "" or password == "":
            self.signin_message.show("Enter your email and password.")
            return
        self.signin_message.clear()
        button = self.dom_nodes["signin_button"]
        button.disabled = True
        signed_in = False
        try:
            admin_session.sign_in(email, password)
            signed_in = True
        except admin_session.SignInError as error:
            self.signin_message.show(str(error))
        finally:
            self.password_input.value = ""
            button.disabled = False
        if signed_in:
            self.raise_event("signed_in")
