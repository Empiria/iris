# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import random

from ._anvil_designer import MatrixTemplate

ALPHABET = "abcdefghijklmnopqrstuvwxyz"


class Matrix(MatrixTemplate):
    def __init__(self, **properties):
        self.init_components(**properties)
        self.add_event_handler("show", self.form_show)

    def form_show(self, **event_args):
        room = "".join(random.choice(ALPHABET) for _ in range(12))
        self.dom_nodes["room_input"].value = room

    def _join_click(self, event):
        # event.target, not event.currentTarget: that is null by now.
        room = self.dom_nodes["room_input"].value.strip()
        if not room:
            self.dom_nodes["matrix_status"].textContent = "Enter a room name"
            return
        frame = self.dom_nodes["matrix_frame"]
        # Setting src here, in the click handler, keeps the user gesture.
        frame.src = "https://vdo.ninja/?room=" + room + "&label=Matrix"
        frame.hidden = False
        self.dom_nodes["matrix_status"].textContent = "Joined " + room
