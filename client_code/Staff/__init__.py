from anvil_reactive.main import render_effect

from iris.services import staff_session  # pyright: ignore[reportAttributeAccessIssue]

from ._anvil_designer import StaffTemplate


class Staff(StaffTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)

    def form_show(self, **event_args):
        if staff_session.state.status is None:
            staff_session.refresh()

    @render_effect
    def _render(self):
        # Reads the signal, so it runs again whenever the sign-in state changes.
        known = staff_session.is_known()
        is_staff = staff_session.is_staff()
        self.dom_nodes["loading_card"].hidden = known
        self.dom_nodes["signin_card"].hidden = (not known) or is_staff
        self.dom_nodes["signed_in_card"].hidden = not is_staff
        if is_staff:
            self.dom_nodes["signed_in_as"].textContent = "Signed in as " + str(
                staff_session.staff_email()
            )

    def _show_message(self, text):
        message = self.dom_nodes["signin_message"]
        message.textContent = text
        message.hidden = text == ""

    def _on_submit(self, event, **properties):
        event.preventDefault()
        email = str(self.dom_nodes["email_input"].value or "").strip()
        password = str(self.dom_nodes["password_input"].value or "")
        if email == "" or password == "":
            self._show_message("Enter your email and password.")
            return
        self._show_message("")
        button = self.dom_nodes["signin_button"]
        button.disabled = True
        try:
            staff_session.sign_in(email, password)
        except staff_session.SignInError as error:
            self._show_message(str(error))
        finally:
            self.dom_nodes["password_input"].value = ""
            button.disabled = False

    def _on_sign_out(self, event, **properties):
        staff_session.sign_out()
