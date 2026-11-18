# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import anvil.server
import anvil.users
from anvil.tables import app_tables


def _is_staff(user):
    return bool(user and user["is_staff"])


@anvil.server.callable
def spike_signup(email, password):
    user = anvil.users.signup_with_email(email, password)
    return user["email"]


@anvil.server.callable(require_user=_is_staff)
def spike_staff_only():
    return "staff-ok"


@anvil.server.callable
def spike_add_row():
    row = app_tables.spike_row.add_row(name="callable", n=2)
    return row["name"]


@anvil.server.callable
def spike_force_login(email):
    """Probe helper: make sure a user row exists and log it in on this session."""
    row = app_tables.users.get(email=email)
    if row is None:
        row = app_tables.users.add_row(email=email, enabled=True, is_staff=False)
    anvil.users.force_login(row)
    return row["email"]
