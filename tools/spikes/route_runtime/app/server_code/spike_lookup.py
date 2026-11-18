# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import anvil.server
from anvil.tables import app_tables

# Calls are counted in a table, not a module variable: the route handler and the
# callables are not guaranteed to share one Python process or its globals.


@anvil.server.callable
def lookup(slug):
    """Return a dict for the one known slug and None otherwise. Logs each call."""
    app_tables.spike_call.add_row(slug=slug)
    if slug == "spikeslug":
        return {"slug": slug, "value": "spike-value-1"}
    return None


@anvil.server.callable
def spike_calls():
    return [row["slug"] for row in app_tables.spike_call.search()]


@anvil.server.callable
def spike_reset():
    app_tables.spike_call.delete_all_rows()
