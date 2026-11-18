"""Client-side admin sign-in state for the /admin page.

`state.status` is a reactive signal: None while unknown, then the dict that the
`admin_status` callable returns. The server decides who is admin; this module
only mirrors the answer so the page can show the right card. The password is a
parameter of `sign_in` and is never stored.
"""

import anvil.server
import anvil.users
from anvil_reactive.main import signal

from iris.services import password_reset  # pyright: ignore[reportAttributeAccessIssue]

SIGNED_OUT = {"signed_in": False, "is_admin": False, "email": None}


class SignInError(Exception):
    """A sign-in that failed, with a message that is safe to show."""


class _State:
    status = signal(None)


state = _State()


def refresh():
    """Ask the server who is signed in and store the answer."""
    if state.status is None:
        # First load. A visitor from a password-reset email gets the Users
        # service's own reset dialog here, before the sign-in form shows.
        password_reset.offer_pending_reset()
    try:
        state.status = anvil.server.call("admin_status")
    except Exception:
        # Show the sign-in form rather than wait forever. A real server problem
        # then shows up when the person tries to sign in.
        state.status = dict(SIGNED_OUT)


def _field(name):
    status = state.status
    if status is None:
        return None
    # The signal's value is the dict the server returned. The Anvil type stubs
    # model `signal` as the descriptor itself, hence the ignore.
    return status[name]  # pyright: ignore[reportIndexIssue]


def is_known():
    """False until the first answer from the server arrives."""
    return state.status is not None


def is_admin():
    return bool(_field("is_admin"))


def admin_email():
    return _field("email")


def sign_in(email, password):
    """Sign in, and sign straight back out if the account is not admin."""
    try:
        anvil.users.login_with_email(email, password, remember=False)
    except anvil.users.TooManyPasswordFailures:
        raise SignInError("Too many failed attempts. Try again later.")
    except (anvil.users.EmailNotConfirmed, anvil.users.AccountIsNotEnabled):
        raise SignInError(
            "This account cannot sign in yet. Ask a deployer to check it."
        )
    except anvil.users.AuthenticationFailed:
        raise SignInError("Email or password not recognised.")
    refresh()
    if not is_admin():
        anvil.users.logout()
        refresh()
        raise SignInError("This account is not an admin account.")


def sign_out():
    anvil.users.logout()
    refresh()
