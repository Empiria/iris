# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

from ._anvil_designer import TextFieldTemplate


class TextField(TextFieldTemplate):
    """A labelled single-line input.

    Properties: `label`, `input_type`, `autocomplete`, `maxlength` (0 for none),
    `readonly`, and `private`, which turns off autocapitalise and spellcheck for
    values like a passphrase or a slug.
    """

    def __init__(self, **properties):
        self.init_components(**properties)
        field = self.dom_nodes["input"]
        self.dom_nodes["label"].textContent = str(properties.get("label") or "")
        field.setAttribute("type", str(properties.get("input_type") or "text"))
        field.setAttribute("autocomplete", str(properties.get("autocomplete") or "off"))
        maxlength = properties.get("maxlength")
        if maxlength:
            field.setAttribute("maxlength", str(int(maxlength)))
        if properties.get("readonly"):
            field.setAttribute("readonly", "")
        if properties.get("private"):
            field.setAttribute("autocapitalize", "off")
            field.setAttribute("spellcheck", "false")

    @property
    def value(self):
        return str(self.dom_nodes["input"].value or "")

    @value.setter
    def value(self, text):
        self.dom_nodes["input"].value = "" if text is None else str(text)

    def focus(self):
        self.dom_nodes["input"].focus()

    def select(self):
        self.dom_nodes["input"].select()
