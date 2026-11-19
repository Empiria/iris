# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Join logic: names, slugs, lookup states and the join address ."""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# Whether the join address carries room, label and salt after the "#". Pinned so a
# change is a deliberate edit.
PINNED_JOIN_IN_FRAGMENT = True
# Test data only: not a code default.
PROFILE = "ssq=-1&sharperscreen&rbr=50000&trb=50000&crb&codec=av1,vp9,vp8,h264&q=0"
VDO_ROOM = "kdvx2p8wmq5rt7hzn3cj"
ORIGIN = "http://127.0.0.1:3030"
HOSTILE_NAMES = [
    "Ann Lee",
    "A&meshcast=1",
    "x#room=other",
    "relay=1",
    "Ann%26relay%3D1",
    "名前",
]


@pytest.fixture
def join(load_client_module):
    return load_client_module("services/join")


def _found(**changes):
    found = {
        "vdo_room": VDO_ROOM,
        "title": "Kickoff",
        "origin": ORIGIN,
        "profile": PROFILE,
        "salt": None,
    }
    found.update(changes)
    return found


def _keys(url):
    pieces = re.split(r"[?#&]", url.split("://", 1)[1].split("/", 1)[1])
    return [piece.split("=", 1)[0].lower() for piece in pieces if piece]


# --- clean_display_name ---------------------------------------------------


def test_the_name_is_trimmed_and_collapsed(join):
    assert join.clean_display_name("  Ann   Lee ") == "Ann Lee"


@pytest.mark.parametrize("control", ["\x00", "\n", "\t"])
def test_a_control_character_becomes_a_space(join, control):
    assert join.clean_display_name("Ann" + control + "Lee") == "Ann Lee"


def test_a_long_name_is_cut_to_sixty(join):
    assert join.clean_display_name("a" * 100) == "a" * 60


@pytest.mark.parametrize("bad", ["", "   ", "\n\t", None, 5])
def test_a_missing_name_is_refused_with_the_message(join, bad):
    with pytest.raises(ValueError) as refused:
        join.clean_display_name(bad)

    assert str(refused.value) == "Enter your name to join."


# --- is_joinable_slug -----------------------------------------------------


@pytest.mark.parametrize("slug", ["dk2wjd9d", " DK2WJD9D ", "infinite-world"])
def test_a_slug_shape_is_joinable(join, slug):
    assert join.is_joinable_slug(slug) is True


@pytest.mark.parametrize("slug", ["admin", "ab", "", None, "../x", "a" * 65])
def test_a_bad_slug_is_not_joinable(join, slug):
    assert join.is_joinable_slug(slug) is False


# --- load_meeting ---------------------------------------------------------


def test_a_found_room_makes_one_call_and_is_ready(join):
    calls = []
    reply = _found()

    def call(name, *args):
        calls.append((name, args))
        return reply

    result = join.load_meeting(" DK2WJD9D ", call)

    assert result == {"state": "ready", "found": reply}
    assert calls == [("lookup_room", ("dk2wjd9d",))]


def test_a_none_reply_is_missing(join):
    assert join.load_meeting("dk2wjd9d", lambda *a: None) == {"state": "missing"}


def test_any_exception_is_the_error_state_with_no_text(join):
    def call(*args):
        raise ValueError("setting vdo_profile is invalid: secret detail")

    result = join.load_meeting("dk2wjd9d", call)

    assert result == {"state": "error"}


@pytest.mark.parametrize("slug", ["admin", "ab", "", None, "../x"])
def test_a_slug_that_is_not_joinable_never_calls(join, slug):
    calls = []

    result = join.load_meeting(slug, lambda *a: calls.append(a))

    assert result == {"state": "missing"}
    assert calls == []


# --- join_url -------------------------------------------------------------


def test_the_query_form(join):
    url = join.join_url(_found(), "Ann Lee", in_fragment=False)

    assert url == f"{ORIGIN}/?room={VDO_ROOM}&label=Ann%20Lee&{PROFILE}"


def test_the_fragment_form(join):
    url = join.join_url(_found(), "Ann Lee", in_fragment=True)

    assert url == f"{ORIGIN}/?{PROFILE}#room={VDO_ROOM}&label=Ann%20Lee"


def test_a_salt_is_appended(join):
    query = join.join_url(_found(salt="pepper"), "Ann", in_fragment=False)
    fragment = join.join_url(_found(salt="pepper"), "Ann", in_fragment=True)

    assert query.endswith("&salt=pepper")
    assert fragment.endswith("&salt=pepper")


def test_the_default_mode_is_the_constant(join):
    assert join.join_url(_found(), "Ann") == join.join_url(
        _found(), "Ann", in_fragment=join.JOIN_IN_FRAGMENT
    )


def test_the_room_is_never_the_slug(join):
    url = join.join_url(_found(), "Ann")

    assert "dk2wjd9d" not in url
    assert "room=" + VDO_ROOM in url


@pytest.mark.parametrize("in_fragment", [False, True])
@pytest.mark.parametrize("name", HOSTILE_NAMES)
def test_no_meshcast_or_relay_key_and_one_room_and_label(join, in_fragment, name):
    url = join.join_url(_found(), name, in_fragment=in_fragment)
    keys = _keys(url)

    assert not [key for key in keys if key.startswith(("meshcast", "relay"))]
    assert keys.count("room") == 1
    assert keys.count("label") == 1


@pytest.mark.parametrize("in_fragment", [False, True])
@pytest.mark.parametrize("bad", ["relay=1", "q=0&meshcast", "q=0&%6Deshcast=1"])
def test_a_profile_that_forces_relaying_raises(join, in_fragment, bad):
    with pytest.raises(ValueError):
        join.join_url(_found(profile=bad), "Ann", in_fragment=in_fragment)


def test_an_empty_name_raises(join):
    with pytest.raises(ValueError):
        join.join_url(_found(), "  ")


# --- is_http_url ----------------------------------------------------------


@pytest.mark.parametrize(
    "url", ["https://a.example/x", "http://127.0.0.1:3030/?room=x"]
)
def test_an_http_address_is_accepted(join, url):
    assert join.is_http_url(url) is True


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "//a.example", "", None, "ftp://a"]
)
def test_any_other_address_is_refused(join, url):
    assert join.is_http_url(url) is False


# --- the pinned decision ------------------------------------------------


def test_join_in_fragment_matches_the_pinned_value(join):
    assert isinstance(join.JOIN_IN_FRAGMENT, bool)
    assert join.JOIN_IN_FRAGMENT == PINNED_JOIN_IN_FRAGMENT


# --- structure ------------------------------------------------------------


def test_the_default_origin_is_named_only_in_vdo_py():
    found = [
        path.relative_to(ROOT).as_posix()
        for directory in ("client_code", "server_code")
        for path in sorted((ROOT / directory).rglob("*.py"))
        if "https://vdo.ninja" in path.read_text(encoding="utf-8")
    ]

    assert found == ["client_code/services/vdo.py"]


def test_join_py_imports_only_sibling_services_and_touches_no_table():
    tree = ast.parse((ROOT / "client_code/services/join.py").read_text("utf-8"))
    imported = set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module)
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)

    assert imported == {"iris.services", "passphrase", "slugs", "vdo"}
    assert "app_tables" not in names


# --- permanent rooms: the locked state and the unlock step -----------------

SAMPLE_PASSPHRASE = "abcd-efgh-jkmn"
PASSWORD = "0123456789abcdef01234567"


def _unlocked(**changes):
    found = _found(salt=None, password=PASSWORD, kind="permanent")
    found.update(changes)
    return found


def test_a_locked_permanent_reply_is_the_locked_state(join):
    reply = {"kind": "permanent", "locked": True}

    result = join.load_meeting("acme-board", lambda *a: reply)

    assert result == {"state": "locked"}


def test_a_one_off_reply_with_a_kind_is_still_ready(join):
    reply = _found(kind="one-off")

    assert join.load_meeting("dk2wjd9d", lambda *a: reply) == {
        "state": "ready",
        "found": reply,
    }


def test_a_permanent_reply_that_is_not_locked_is_not_taken_as_ready(join):
    reply = {"kind": "permanent", "locked": False}

    assert join.load_meeting("acme-board", lambda *a: reply) == {"state": "missing"}


def test_unlock_calls_the_server_with_the_normalised_passphrase(join):
    calls = []
    reply = {"ok": True, "found": _unlocked()}

    def call(name, *args):
        calls.append((name, args))
        return reply

    result = join.unlock(" Acme-Board ", " ABCD EFGH-jkmn ", call)

    assert result == {"state": "ready", "found": reply["found"]}
    assert calls == [("unlock_room", ("acme-board", "abcdefghjkmn"))]


@pytest.mark.parametrize("reason", ["incorrect", "throttled", "missing", "empty"])
def test_unlock_maps_each_refusal_to_its_state(join, reason):
    reply = {"ok": False, "reason": reason}

    assert join.unlock("acme-board", SAMPLE_PASSPHRASE, lambda *a: reply) == {
        "state": reason
    }


@pytest.mark.parametrize(
    "reply",
    [None, {}, {"ok": False}, {"ok": False, "reason": "surprise"}, {"ok": True}, 5],
)
def test_unlock_treats_an_unexpected_reply_as_an_error(join, reply):
    assert join.unlock("acme-board", SAMPLE_PASSPHRASE, lambda *a: reply) == {
        "state": "error"
    }


def test_unlock_exception_is_the_error_state_with_no_text(join):
    def call(*args):
        raise RuntimeError("detail " + SAMPLE_PASSPHRASE)

    assert join.unlock("acme-board", SAMPLE_PASSPHRASE, call) == {"state": "error"}


@pytest.mark.parametrize("text", ["", "   ", "- -", None, 5])
def test_unlock_with_nothing_typed_makes_no_server_call(join, text):
    calls = []

    result = join.unlock("acme-board", text, lambda *a: calls.append(a))

    assert result == {"state": "empty"}
    assert calls == []


def test_unlock_with_an_oversized_input_makes_no_server_call(join):
    calls = []

    result = join.unlock("acme-board", "x" * 500, lambda *a: calls.append(a))

    assert result == {"state": "incorrect"}
    assert calls == []


@pytest.mark.parametrize("slug", ["admin", "ab", "", None, "../x"])
def test_unlock_of_a_slug_that_is_not_joinable_never_calls(join, slug):
    calls = []

    result = join.unlock(slug, SAMPLE_PASSPHRASE, lambda *a: calls.append(a))

    assert result == {"state": "missing"}
    assert calls == []


def test_the_unlock_messages_are_fixed(join):
    assert join.UNLOCK_MESSAGES == {
        "incorrect": "Incorrect passphrase. Check it and try again.",
        "throttled": "Too many attempts. Try again in a few minutes.",
        "empty": "Enter the passphrase.",
        "missing": "This meeting no longer exists.",
    }


def test_join_url_passes_the_password_in_the_fragment(join):
    url = join.join_url(_unlocked(), "Ann Lee", in_fragment=True)

    assert url == (
        f"{ORIGIN}/?{PROFILE}#room={VDO_ROOM}&label=Ann%20Lee&password={PASSWORD}"
    )


def test_join_url_refuses_a_password_in_the_query(join):
    with pytest.raises(ValueError):
        join.join_url(_unlocked(), "Ann", in_fragment=False)


def test_join_url_without_a_password_is_unchanged(join):
    assert "password" not in join.join_url(_found(), "Ann")
    assert join.join_url(_found(kind="one-off"), "Ann") == join.join_url(
        _found(), "Ann"
    )


@pytest.fixture
def passphrase_module(load_client_module):
    return load_client_module("services/passphrase")


@pytest.mark.parametrize("in_fragment", [True])
def test_the_hand_off_url_never_contains_the_passphrase(
    join, passphrase_module, in_fragment
):
    normalised = passphrase_module.normalise(SAMPLE_PASSPHRASE)

    url = join.join_url(_unlocked(), "Ann Lee", in_fragment=in_fragment)

    assert SAMPLE_PASSPHRASE not in url
    assert normalised not in url
    assert PASSWORD in url.split("#", 1)[1]
    assert PASSWORD not in url.split("#", 1)[0]


# --- overrides and the displayed address ----------------------------------


def test_join_url_applies_overrides_over_the_profile(join):
    url = join.join_url(_found(), "Ann", in_fragment=True, overrides="q=2&fps=15")

    assert url.count("&q=") == 1 and "q=0" not in url
    assert "q=2" in url and "fps=15" in url
    # Settings stay in the query, so no key is in both the query and the fragment.
    query, fragment = url.split("#")
    assert fragment == f"room={VDO_ROOM}&label=Ann"
    assert "room=" not in query


def test_join_url_refuses_a_hostile_override(join):
    with pytest.raises(ValueError):
        join.join_url(_found(), "Ann", overrides="room=other")


def test_display_url_leaves_out_password_and_salt(join):
    found = _found(salt="pepper", password="Abc123xyz")

    shown = join.display_url(found, "Ann", overrides="q=2")
    opened = join.join_url(found, "Ann", overrides="q=2")

    assert "Abc123xyz" not in shown and "pepper" not in shown
    assert "password=" not in shown and "salt=" not in shown
    assert "Abc123xyz" in opened and "salt=pepper" in opened
    assert shown.startswith(ORIGIN) and f"room={VDO_ROOM}" in shown and "q=2" in shown
