# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria


def user_message(error):
    """Return the message of a server error written for the person, or None.

    The server raises `ValueError` with a message meant to be shown. The browser
    client receives it as `anvil.server.AnvilWrappedError`, whose `args[0]` is
    that message and which has no `error_obj`. A plain `ValueError` (the
    uplink, or code that runs in the same process) is read the same way.
    Anything else gets None, so the caller shows its own generic text.
    """
    if isinstance(error, ValueError):
        return str(error)
    if type(error).__name__ == "AnvilWrappedError" and error.args:
        return str(error.args[0]) or None
    return None
