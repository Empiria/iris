import anvil.users

from ._anvil_designer import SignupSpikeTemplate


class SignupSpike(SignupSpikeTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)

    def form_show(self, **event_args):
        node = self.dom_nodes["spike_signup"]
        try:
            anvil.users.signup_with_email(
                "client-attempt@example.invalid", "pw-spike-1"
            )
        except Exception as exc:
            node.textContent = "refused: " + str(exc)
            return
        node.textContent = "allowed"
