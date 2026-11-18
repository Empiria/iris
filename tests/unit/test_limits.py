# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""The `maxlength` numbers in the form templates equal the constants in limits.py.

A template can't import Python, so each number is written out there. This
reads every template and fails when one drifts from its constant.
"""

import re
from pathlib import Path

import pytest

CLIENT = Path(__file__).resolve().parents[2] / "client_code"


@pytest.fixture
def meetings(load_client_module):
    import importlib

    load_client_module("services/limits")
    return importlib.import_module("iris.meetings")


@pytest.fixture
def limits(load_client_module):
    return load_client_module("services/limits")


# (template, the element's name, dom-node or prop label) -> the limit it must carry.
def _expected(limits):
    return {
        ("Join", "Passphrase"): limits.PASSPHRASE_INPUT_MAX,
        ("Join", "Your name"): limits.DISPLAY_NAME_MAX,
        ("RoomRow", "Meeting name"): limits.TITLE_MAX,
        ("CreateMeeting", "Room name, used in the link"): limits.SLUG_MAX,
        ("CreateMeeting", "Meeting name (optional)"): limits.TITLE_MAX,
        ("CallSettings", "profile_input"): limits.PROFILE_MAX,
    }


def _found():
    """Each `maxlength` in the templates, as {(form, label or dom-node): value}."""
    found = {}
    for path in sorted(CLIENT.glob("*/form_template.html")):
        text = path.read_text()
        for tag in re.findall(r"<(?:anvil-component|textarea|input)\b.*?>", text, re.S):
            number = re.search(r'(?:prop:)?maxlength="(\d+)"', tag)
            if not number:
                continue
            label = re.search(r'prop:label="([^"]*)"', tag) or re.search(
                r'anvil:dom-node="([^"]*)"', tag
            )
            found[(path.parent.name, label.group(1))] = int(number.group(1))
    return found


def test_templates_use_the_constants(limits):
    found = _found()
    assert {k: v for k, v in found.items() if k[0] != "TextField"} == _expected(limits)


def test_python_modules_use_the_constants(limits, load_client_module, meetings):
    passphrase = load_client_module("services/passphrase")
    join = load_client_module("services/join")
    slugs = load_client_module("services/slugs")
    setting = load_client_module("services/model/setting")
    assert passphrase.MAX_INPUT == limits.PASSPHRASE_INPUT_MAX
    assert join.NAME_MAX == limits.DISPLAY_NAME_MAX
    assert slugs.MAX_SLUG_LENGTH == limits.SLUG_MAX
    assert setting.Setting.MAX_PROFILE_LENGTH == limits.PROFILE_MAX
    assert meetings.MAX_TITLE_LENGTH == limits.TITLE_MAX
