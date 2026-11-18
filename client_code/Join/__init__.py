import anvil.server

from iris.services import (
    handoff,  # pyright: ignore[reportAttributeAccessIssue]
    join,  # pyright: ignore[reportAttributeAccessIssue]
)

from ._anvil_designer import JoinTemplate

NOT_SET_UP_MESSAGE = "This meeting is not set up correctly. Ask your host."


class Join(JoinTemplate):
    def __init__(self, routing_context=None, **properties):
        self.routing_context = routing_context
        self.found = None
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)

    def _route_data(self):
        """The route's loaded state, or a fresh lookup when there is none."""
        context = self.routing_context
        data = context.data if context else None
        if data is not None:
            return data
        slug = context.params["slug"] if context else None
        return join.load_meeting(slug, anvil.server.call)

    def _show_only(self, card):
        for name in ("loading_card", "join_card", "missing_card", "error_card"):
            self.dom_nodes[name].hidden = name != card

    def form_show(self, **event_args):
        data = self._route_data()
        state = data["state"]
        if state == "ready":
            self.found = data["found"]
            title = str(self.found["title"] or "").strip()
            self.dom_nodes["meeting_title"].textContent = title or "Your meeting"
            self._show_only("join_card")
        elif state == "missing":
            self._show_only("missing_card")
        else:
            self._show_only("error_card")

    def _show_message(self, text):
        message = self.dom_nodes["join_message"]
        message.textContent = text
        message.hidden = text == ""

    def _on_submit(self, event, **properties):
        event.preventDefault()
        self._show_message("")
        try:
            name = join.clean_display_name(
                str(self.dom_nodes["name_input"].value or "")
            )
        except ValueError as error:
            self._show_message(str(error))
            return
        button = self.dom_nodes["join_button"]
        button.disabled = True
        try:
            # Same call stack as the click, so the frame is made by a user gesture.
            how = handoff.start(join.join_url(self.found, name), self.meeting_frame)
        except ValueError:
            self._show_message(NOT_SET_UP_MESSAGE)
            button.disabled = False
            return
        if how == "iframe":
            self.dom_nodes["join_main"].hidden = True
            self.dom_nodes["frame_shell"].hidden = False
