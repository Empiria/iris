import anvil.server
from anvil.js import window
from anvil_reactive.main import render_effect

from iris.services import (
    links,  # pyright: ignore[reportAttributeAccessIssue]
    permissions,  # pyright: ignore[reportAttributeAccessIssue]
    staff_session,  # pyright: ignore[reportAttributeAccessIssue]
)

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

    def _show_create_message(self, text):
        message = self.dom_nodes["create_message"]
        message.textContent = text
        message.hidden = text == ""

    def _show_copy_message(self, text):
        message = self.dom_nodes["copy_message"]
        message.textContent = text
        message.hidden = text == ""

    def _copy_link(self):
        """Copy the link to the clipboard, or select it and say what to press."""
        output = self.dom_nodes["link_output"]
        try:
            window.navigator.clipboard.writeText(str(output.value))
        except Exception:
            output.select()
            self._show_copy_message(
                "Copy failed. The link is selected, so press Ctrl+C or Cmd+C."
            )
        else:
            self._show_copy_message("Link copied.")

    def _on_create(self, event, **properties):
        title = str(self.dom_nodes["title_input"].value or "")
        self._show_create_message("")
        self._show_copy_message("")
        button = self.dom_nodes["create_button"]
        button.disabled = True
        try:
            result = anvil.server.call("create_one_off_link", title)
            base = links.base_from_location(
                window.location.origin, window.location.pathname
            )
            link = links.link_for(base, result["slug"], links.ROUTE_OWNER)
            self.dom_nodes["link_output"].value = link
            self.dom_nodes["result_box"].hidden = False
            self._copy_link()
        except permissions.PermissionDenied:
            self._show_create_message("You are not signed in as staff.")
            staff_session.refresh()
        except Exception:
            self._show_create_message("Could not create the link. Try again.")
        finally:
            button.disabled = False

    def _on_copy(self, event, **properties):
        self._show_copy_message("")
        self._copy_link()
