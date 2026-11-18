# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import anvil.server
import anvil.users


def _is_staff(user):
    return bool(user and user["is_staff"])


@anvil.server.callable(require_user=_is_staff)
def spike_staff_only():
    return "staff-ok"


@anvil.server.callable
def spike_force_login(email):
    """Probe helper: log the existing user row for this address in on this session."""
    from anvil.tables import app_tables

    row = app_tables.users.get(email=email)
    if row is None:
        row = app_tables.users.add_row(email=email, enabled=True, is_staff=False)
    anvil.users.force_login(row)
    return row["email"]
