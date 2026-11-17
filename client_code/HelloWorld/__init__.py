import anvil.server

from ._anvil_designer import HelloWorldTemplate


class HelloWorld(HelloWorldTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)

    def form_show(self, **event_args):
        try:
            reply = anvil.server.call("ping")
        except Exception:
            reply = "unavailable"
        self.dom_nodes["server_status"].textContent = "Server check: " + reply
