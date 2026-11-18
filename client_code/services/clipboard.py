# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Copy text to the clipboard, and say whether the browser took it.

Loads on both sides, so `anvil.js` is imported inside the function that needs it.
`writeText` returns a Promise that anvil.js awaits for us, so a refusal (no
permission, or an insecure page with no `navigator.clipboard`) raises here and
is caught. `write` lets a test pass a fake.
"""


def copy(text, write=None):
    """Return True when the text was copied, False when the browser refused."""
    try:
        if write is None:
            from anvil.js import window

            write = window.navigator.clipboard.writeText
        write(str(text))
    except Exception:
        return False
    return True
