# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Length limits, in one place.

Loads on both sides. The HTML form templates repeat these numbers as `maxlength`,
because a template can't import Python; tests/unit/test_limits.py keeps them equal.
"""

# Longest raw passphrase or join input accepted. It bounds the work a hostile
# caller can hand the server's key derivation.
PASSPHRASE_INPUT_MAX = 200
# A display name typed on the join page.
DISPLAY_NAME_MAX = 60
# A meeting name (title) stored on a room.
TITLE_MAX = 80
# The room name that becomes the link slug.
SLUG_MAX = 64
# The VDO.Ninja profile text an admin may save.
PROFILE_MAX = 2000
