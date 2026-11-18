"""Tell a refusal written for a person apart from a real failure.

A server callable raises `ValueError("That name is taken.")` with a message
meant for whoever typed the name. The Anvil runtime may hand the client that
error as the `ValueError` itself or wrapped in `AnvilWrappedError`, which
carries the original type and message in `error_obj`, so a client reads it
through `user_message` rather than catching `ValueError` alone.
"""


def user_message(error):
    """Return the message of a server `ValueError`, or None for anything else."""
    if isinstance(error, ValueError):
        return str(error)
    details = getattr(error, "error_obj", None)
    if isinstance(details, dict) and details.get("type") == "ValueError":
        return str(details.get("message") or "")
    return None
