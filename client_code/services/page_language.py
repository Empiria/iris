# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Set the page's `lang` so screen readers pick the right voice.

Anvil's own page shell sends no `lang`, and a theme can't change it, so the
client sets it at startup. Loads on both sides, so `anvil.js` is imported inside
the function; on the server there is no page and nothing happens.
"""

LANGUAGE = "en-GB"


def apply(set_attribute=None):
    """Set `lang` on the document element. Returns True when it was set."""
    try:
        if set_attribute is None:
            from anvil.js import window

            root = getattr(window.document, "documentElement")
            set_attribute = root.setAttribute
        set_attribute("lang", LANGUAGE)
    except Exception:
        return False
    return True
