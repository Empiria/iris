import anvil.server

from ._anvil_designer import SlugSpikeTemplate


class SlugSpike(SlugSpikeTemplate):
    def __init__(self, routing_context=None, **properties):
        self.routing_context = routing_context
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)

    def form_show(self, **event_args):
        startup = anvil.server.startup_data
        found = startup.get("lookup") if startup else None
        if found is None:
            self.dom_nodes["spike_state"].textContent = "no data"
            return
        self.dom_nodes["spike_state"].textContent = "found"
        self.dom_nodes["spike_slug"].textContent = found["slug"]
        self.dom_nodes["spike_value"].textContent = found["value"]
