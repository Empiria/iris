# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Glue for the Users service's own password reset.

The service sends the email, hosts the emailed link and shows its own
"Reset password" dialog. This module only starts a reset and lets that dialog
appear. It holds no token and no password.
"""

import anvil.users

SENT = (
    "If that email belongs to an admin account, a reset link is on its way. "
    "It expires in ten minutes."
)
ENTER_EMAIL = "Enter your email address."


def request_reset(email):
    """Ask the Users service to email a reset link. Returns the text to show.

    The service refuses an unknown or disabled address with AuthenticationFailed.
    The same text is shown either way, so the form does not reveal which
    addresses have an account.
    """
    email = str(email or "").strip()
    if email == "":
        return ENTER_EMAIL
    try:
        anvil.users.send_password_reset_email(email)
    except anvil.users.AuthenticationFailed:
        pass
    return SENT


def offer_pending_reset():
    """Show the service's reset dialog if the visitor arrived by a reset link.

    The link lands on the app root with a session that has a reset pending.
    `anvil.users.get_user()` is the call that notices this and opens the dialog,
    and it waits until the dialog is closed.
    """
    try:
        anvil.users.get_user()
    except Exception:
        # Any problem here must not stop the sign-in form from loading.
        pass
