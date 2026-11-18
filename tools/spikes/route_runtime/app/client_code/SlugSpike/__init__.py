# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from ._anvil_designer import SlugSpikeTemplate


class SlugSpike(SlugSpikeTemplate):
    def __init__(self, routing_context=None, **properties):
        self.routing_context = routing_context
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)

    def form_show(self, **event_args):
        data = self.routing_context.data if self.routing_context else None
        if data is None:
            self.dom_nodes["spike_state"].textContent = "no data"
            return
        self.dom_nodes["spike_state"].textContent = "found"
        self.dom_nodes["spike_slug"].textContent = data["slug"]
        self.dom_nodes["spike_value"].textContent = data["value"]
