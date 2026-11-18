"""Open a permanent room with its passphrase (JOIN-02, JOIN-03, JOIN-05).

Runs against the live local stack after `just seed`, which makes the permanent
room `test-room` with a made-up passphrase.
"""

import pytest

pytestmark = pytest.mark.e2e

# These repeat the constants in tools/dev_seed.py. A unit test keeps them equal.
SEEDED_PERMANENT_SLUG = "test-room"
SEEDED_PERMANENT_TITLE = "Seeded permanent room"
SEEDED_PERMANENT_VDO_ROOM = "q7wn4hx2cvb9mz5dk3tp"
SEEDED_PERMANENT_VDO_PASSWORD = "0123456789abcdef01234567"
SEEDED_PASSPHRASE = "test-room-pass"
