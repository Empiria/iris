# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import sys


def test_ping_returns_pong(load_server_module):
    health = load_server_module("health")

    assert health.ping() == "pong"


def test_anvil_server_is_the_stub():
    # The real uplink has a `connect`. If this fails, the unit suite is running
    # against the live package instead of the stubs.
    assert not hasattr(sys.modules["anvil.server"], "connect")
