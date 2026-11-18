# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Client-side state for the admin tools: the rooms, the call settings, the new result.

Each piece is a reactive signal, so the components that show it re-render when it
changes. The functions here are the only code that calls the server for these
tools, and they run from event handlers, never from a render effect. They never
raise: each returns the text to show when something went wrong, or "".

`result` is the latest link the admin made or rotated, `{"slug", "passphrase"}`.
The passphrase is "" once it has been cleared, and `reset` drops all of it.
"""

import anvil.server
from anvil_reactive.main import signal

from iris.services import (
    admin_session,  # pyright: ignore[reportAttributeAccessIssue]
    errors,  # pyright: ignore[reportAttributeAccessIssue]
    permissions,  # pyright: ignore[reportAttributeAccessIssue]
)

# The wording the page already uses when a call is refused.
SIGNED_OUT_TEXT = "You are not signed in as admin."


class _State:
    rooms = signal(None)  # None until loaded, then the list of room summaries
    rooms_message = signal("")
    profile = signal(None)  # None until loaded, then the saved text
    profile_message = signal("")
    result = signal(None)


state = _State()


def reset():
    """Drop everything, when signed out."""
    state.rooms = None
    state.rooms_message = ""
    state.profile = None
    state.profile_message = ""
    state.result = None


def clear_secret():
    """Forget the passphrase, and keep the link beside it."""
    current = state.result
    if current is not None and current["passphrase"] != "":  # pyright: ignore[reportIndexIssue]
        state.result = {"slug": current["slug"], "passphrase": ""}  # pyright: ignore[reportIndexIssue]


def _failure(error, fallback):
    """The text for a failed call. A refusal also re-checks who is signed in.

    Anything else gets the server's own message when it wrote one for the person
    who asked, and `fallback` when it did not.
    """
    if isinstance(error, permissions.PermissionDenied):
        admin_session.refresh()
        return SIGNED_OUT_TEXT
    return errors.user_message(error) or fallback


def load_rooms():
    try:
        state.rooms = anvil.server.call("list_rooms")
    except Exception as error:
        state.rooms_message = _failure(
            error, "Could not load the rooms. Reload the page."
        )


def load_profile():
    state.profile_message = ""
    try:
        state.profile = anvil.server.call("get_profile")
    except Exception as error:
        state.profile_message = _failure(
            error, "Could not load the settings. Reload the page."
        )


def load_all():
    """Load both after sign-in, or when the page opens already signed in."""
    state.rooms_message = ""
    load_rooms()
    load_profile()


def create(permanent, name, title):
    """Make a room or a one-off link. Returns the text for a failure, or "".

    The caller reloads the rooms, after it has copied the new link.
    """
    clear_secret()
    try:
        if permanent:
            reply = anvil.server.call("create_permanent_room", name, title)
        else:
            reply = anvil.server.call("create_one_off_link", title)
    except Exception as error:
        # A name that is taken, reserved or badly formed: the server's message is
        # written for the person who typed it.
        fallback = (
            "Could not create the room. Try again."
            if permanent
            else "Could not create the link. Try again."
        )
        return _failure(error, fallback)
    state.result = {
        "slug": reply["slug"],
        "passphrase": str(reply["passphrase"]) if permanent else "",
    }
    return ""


def save_profile(text):
    """Save the call settings. The saved text, normalised, replaces the stored one."""
    state.profile_message = ""
    try:
        state.profile = anvil.server.call("update_profile", text)
    except Exception as error:
        state.profile_message = _failure(
            error, "Could not save the settings. Try again."
        )
        return
    state.profile_message = "Saved. New joins use these settings."


def _room_action(name, *args):
    """Call the server for one room action. Returns the reply, or None."""
    state.rooms_message = ""
    clear_secret()
    try:
        return anvil.server.call(name, *args)
    except Exception as error:
        # An unknown room or a refused title: written for the person who asked.
        # The list may be stale, so it is loaded again.
        state.rooms_message = _failure(error, "Could not change the room. Try again.")
        if errors.user_message(error):
            load_rooms()
    return None


def update_room(slug, title):
    if _room_action("update_room", slug, title) is not None:
        load_rooms()


def delete_room(slug):
    if _room_action("delete_room", slug) is not None:
        load_rooms()


def rotate_passphrase(slug):
    reply = _room_action("rotate_passphrase", slug)
    if reply is None:
        return
    # The new passphrase shows in the same box a new room's passphrase uses.
    state.result = {"slug": reply["slug"], "passphrase": str(reply["passphrase"])}
    state.rooms_message = (
        "New passphrase for " + str(reply["slug"]) + " is in the box above."
    )
    load_rooms()
