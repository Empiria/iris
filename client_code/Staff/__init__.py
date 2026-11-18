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
    # A class default, so the render effect can read it however early it first runs.
    _profile_loaded = False

    def __init__(self, **properties):
        self.init_components(**properties)
        self._profile_loaded = False
        self.add_event_handler("show", self.form_show)
        self.add_event_handler("hide", self.form_hide)

    def form_show(self, **event_args):
        if staff_session.state.status is None:
            staff_session.refresh()

    def form_hide(self, **event_args):
        # Leaving the page drops the passphrase from it.
        self._clear_passphrase()

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
            if not self._profile_loaded:
                self._profile_loaded = True
                self._load_profile()
        else:
            # Signed out: drop the saved text from the page, and load it again
            # the next time a staff member signs in.
            self._profile_loaded = False
            self.dom_nodes["profile_input"].value = ""
            self._show_profile_message("")
            self._clear_passphrase()

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

    def _clear_passphrase(self):
        """Empty the passphrase box and hide it, so it never outlives its room."""
        self.dom_nodes["passphrase_output"].value = ""
        self.dom_nodes["passphrase_box"].hidden = True
        message = self.dom_nodes["passphrase_copy_message"]
        message.textContent = ""
        message.hidden = True

    def _wants_permanent(self):
        return bool(self.dom_nodes["kind_permanent"].checked)

    def _on_kind_change(self, event, **properties):
        permanent = self._wants_permanent()
        self.dom_nodes["room_name_field"].hidden = not permanent
        self.dom_nodes["create_button"].textContent = (
            "Create room" if permanent else "Create link"
        )
        self._show_create_message("")

    def _create(self, permanent, title):
        """Make the room on the server and return its reply."""
        if permanent:
            name = str(self.dom_nodes["room_name_input"].value or "")
            return anvil.server.call("create_permanent_room", name, title)
        return anvil.server.call("create_one_off_link", title)

    def _show_created(self, result, permanent):
        base = links.base_from_location(
            window.location.origin, window.location.pathname
        )
        link = links.link_for(base, result["slug"], links.ROUTE_OWNER)
        self.dom_nodes["link_output"].value = link
        if permanent:
            self.dom_nodes["passphrase_output"].value = str(result["passphrase"])
            self.dom_nodes["passphrase_box"].hidden = False
        self.dom_nodes["result_box"].hidden = False
        self._copy_link()

    def _on_create(self, event, **properties):
        permanent = self._wants_permanent()
        title = str(self.dom_nodes["title_input"].value or "")
        self._show_create_message("")
        self._show_copy_message("")
        self._clear_passphrase()
        button = self.dom_nodes["create_button"]
        button.disabled = True
        try:
            self._show_created(self._create(permanent, title), permanent)
        except permissions.PermissionDenied:
            self._show_create_message("You are not signed in as staff.")
            staff_session.refresh()
        except ValueError as error:
            # A room name that is taken, reserved or badly formed: the server's
            # message is written for the person who typed it.
            self._show_create_message(str(error))
        except Exception:
            self._show_create_message(
                "Could not create the room. Try again."
                if permanent
                else "Could not create the link. Try again."
            )
        finally:
            button.disabled = False

    def _on_copy(self, event, **properties):
        self._show_copy_message("")
        self._copy_link()

    def _on_copy_passphrase(self, event, **properties):
        """Copy the passphrase, or select it and say what to press."""
        output = self.dom_nodes["passphrase_output"]
        message = self.dom_nodes["passphrase_copy_message"]
        try:
            window.navigator.clipboard.writeText(str(output.value))
            text = "Passphrase copied."
        except Exception:
            output.select()
            text = "Copy failed. The passphrase is selected, so press Ctrl+C or Cmd+C."
        message.textContent = text
        message.hidden = False

    def _show_profile_message(self, text):
        message = self.dom_nodes["profile_message"]
        message.textContent = text
        message.hidden = text == ""

    def _load_profile(self):
        try:
            self.dom_nodes["profile_input"].value = anvil.server.call("get_profile")
        except permissions.PermissionDenied:
            # Not a refresh: this runs inside the render effect, and a refresh
            # would change the signal it reads.
            self._show_profile_message("You are not signed in as staff.")
        except Exception:
            self._show_profile_message("Could not load the settings. Reload the page.")

    def _on_profile_save(self, event, **properties):
        text = str(self.dom_nodes["profile_input"].value or "")
        self._show_profile_message("")
        button = self.dom_nodes["profile_save"]
        button.disabled = True
        try:
            saved = anvil.server.call("update_profile", text)
            self.dom_nodes["profile_input"].value = saved
            self._show_profile_message("Saved. New joins use these settings.")
        except permissions.PermissionDenied:
            self._show_profile_message("You are not signed in as staff.")
            staff_session.refresh()
        except ValueError as error:
            self._show_profile_message(str(error))
        except Exception:
            self._show_profile_message("Could not save the settings. Try again.")
        finally:
            button.disabled = False
