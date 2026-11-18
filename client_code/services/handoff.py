"""The one place that hands a person from Iris to the room.

Plan 02-06 applies the recorded iframe decision here. Until then the hand-off is
a top-level redirect to the address `join.join_url` built from the server reply.
"""

from iris.services import join  # pyright: ignore[reportAttributeAccessIssue]


def start(url):
    """Send the browser to `url`, which must be an http or https address."""
    if not join.is_http_url(url):
        raise ValueError("The address to hand off to is not an http address")
    # Imported here so this module also loads on the server, which has no window.
    from anvil.js import window

    window.location.href = url
