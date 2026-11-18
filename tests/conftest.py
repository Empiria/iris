# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Keep the hermetic unit suite and the live (stack-backed) suites apart.

tests/unit/conftest.py replaces the real `anvil` modules with stubs. Collecting
it in the same process as a suite that talks to the live stack leaves one of
them running against the wrong `anvil`. See the vault note
learning/unit-stubs-and-live-uplink-collide.md.
"""

from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent


def pytest_collection_modifyitems(session, config, items):
    suites = {Path(item.path).resolve().relative_to(TESTS).parts[0] for item in items}
    if "unit" in suites and len(suites) > 1:
        pytest.exit(
            "Unit and live tests collected in one process. "
            "Run `just unit` and `just e2e` separately.",
            returncode=4,
        )
