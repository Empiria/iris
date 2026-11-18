# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""The UI primitives are HTML-template custom components, and forms use them right.

pytest can't run client code, so these read the templates.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "client_code"
PRIMITIVES = ["Message", "TextField", "CopyField", "StatusCard", "ConfirmBar"]
FORMS = sorted(p.parent for p in CLIENT.rglob("form_template.html"))

USE = re.compile(r"""<anvil-component\b[^>]*?\btype="form:([A-Za-z]+)"[^>]*>""", re.S)
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _template(name):
    return (CLIENT / name / "form_template.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", PRIMITIVES)
def test_primitive_is_a_custom_component(name):
    text = _template(name)

    assert re.match(r"---\n(?:.*\n)*?custom_component: true\n(?:.*\n)*?---\n", text)
    assert (CLIENT / name / "__init__.py").is_file()


@pytest.mark.parametrize("name", PRIMITIVES)
def test_primitive_has_no_m3_or_colours(name):
    text = _template(name)

    assert "m3" not in text.lower()
    assert "style=" not in text
    assert not HEX.search(text)


def test_message_is_a_live_region_that_is_never_hidden():
    text = _template("Message")

    assert 'role="status"' in text
    assert "hidden" not in text


@pytest.mark.parametrize("form", FORMS, ids=lambda p: p.name)
def test_embedded_components_name_a_real_form(form):
    used = set(USE.findall((form / "form_template.html").read_text(encoding="utf-8")))

    missing = {name for name in used if not (CLIENT / name / "__init__.py").is_file()}

    assert not missing, f"{form.name} embeds forms that do not exist: {sorted(missing)}"


def test_the_pages_use_the_primitives():
    joined = "".join(
        _template(page)
        for page in [
            "Admin",
            "SignInCard",
            "CreateMeeting",
            "RoomsList",
            "CallSettings",
            "Join",
            "RoomRow",
        ]
    )

    for name in PRIMITIVES:
        assert f"form:{name}" in joined, name


def test_pages_do_not_rebuild_a_message_by_hand():
    for page in [
        "Admin",
        "SignInCard",
        "CreateMeeting",
        "RoomsList",
        "CallSettings",
        "Join",
        "RoomRow",
        "ForgotPassword",
    ]:
        assert 'class="iris-message"' not in _template(page), page
