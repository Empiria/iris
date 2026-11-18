import anvil.server

from ._anvil_designer import ScriptSpikeTemplate


class ScriptSpike(ScriptSpikeTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)

    def form_show(self, **event_args):
        node = self.dom_nodes["spike_launch"]
        try:
            anvil.server.launch_background_task(
                "script:CreateStaff", "client-attempt@example.invalid", "pw-spike-1"
            )
        except Exception as exc:
            node.textContent = "refused: " + str(exc)
            return
        node.textContent = "allowed"
