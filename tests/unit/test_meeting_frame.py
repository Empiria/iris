"""The MeetingFrame template and its use on the Join page (JOIN-07).

Client forms can't run under pytest, so these pin the template facts that matter
in a browser: the room's permissions, the referrer policy, no source before Join.
"""

import re
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[2] / "client_code"
FRAME = (CLIENT / "MeetingFrame" / "form_template.html").read_text()
FRAME_PY = (CLIENT / "MeetingFrame" / "__init__.py").read_text()
JOIN_HTML = (CLIENT / "Join" / "form_template.html").read_text()
JOIN_PY = (CLIENT / "Join" / "__init__.py").read_text()


def _iframe():
    match = re.search(r"<iframe\b[^>]*>", FRAME)
    assert match, "MeetingFrame has no iframe"
    return match.group(0)


def test_frame_is_a_custom_component_with_a_src_property():
    assert "custom_component: true" in FRAME
    assert "name: src" in FRAME


def test_iframe_has_the_room_permissions_and_referrer_policy():
    tag = _iframe()
    assert 'allow="camera; microphone; autoplay; display-capture"' in tag
    assert 'referrerpolicy="strict-origin-when-cross-origin"' in tag
    assert 'anvil:dom-node="frame"' in tag


def test_iframe_has_no_source_until_join():
    assert not re.search(r"\ssrc\s*=", _iframe())


def test_frame_applies_src_on_show_or_at_once_when_shown():
    assert 'add_event_handler("show"' in FRAME_PY
    assert "_shown" in FRAME_PY
    assert 'setAttribute("src"' in FRAME_PY


def test_join_hosts_the_frame_hidden_and_swaps_it_in():
    assert 'type="form:MeetingFrame"' in JOIN_HTML
    assert 'name="meeting_frame"' in JOIN_HTML
    assert re.search(r'anvil:dom-node="frame_shell"[^>]*\bhidden\b', JOIN_HTML)
    assert "handoff.start(" in JOIN_PY
    assert "self.meeting_frame" in JOIN_PY
    assert 'dom_nodes["frame_shell"].hidden = False' in JOIN_PY
