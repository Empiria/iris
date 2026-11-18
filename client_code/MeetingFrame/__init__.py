from ._anvil_designer import MeetingFrameTemplate


class MeetingFrame(MeetingFrameTemplate):
    """The one iframe that holds the room.

    It has no source until the Join page sets `src` after a person has pressed
    Join, so nothing asks for the camera or microphone before then. The source is
    applied when the form is shown, or at once if it is already shown.
    """

    def __init__(self, **properties):
        self._src = ""
        self._shown = False
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)

    @property
    def src(self):
        return self._src

    @src.setter
    def src(self, value):
        self._src = "" if value is None else str(value)
        if self._shown:
            self._apply()

    def form_show(self, **event_args):
        self._shown = True
        self._apply()

    def _apply(self):
        if self._src != "":
            self.dom_nodes["frame"].setAttribute("src", self._src)
