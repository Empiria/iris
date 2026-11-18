"""Join logic: names, slugs, lookup states and the join address (JOIN-01, 04, 06)."""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESULTS = (
    ROOT
    / ".planning"
    / "phases"
    / "02-one-off-meetings-staff-to-client"
    / "02-SPIKE-RESULTS.md"
)
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


@pytest.mark.parametrize("slug", ["staff", "ab", "", None, "../x", "a" * 65])
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


@pytest.mark.parametrize("slug", ["staff", "ab", "", None, "../x"])
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


# --- the recorded decision ------------------------------------------------


def test_join_in_fragment_matches_the_recorded_decision(join):
    if not RESULTS.is_file():
        pytest.skip("02-SPIKE-RESULTS.md is not on this machine")
    line = next(
        (
            row
            for row in RESULTS.read_text(encoding="utf-8").splitlines()
            if row.startswith("Join URL parameters:")
        ),
        None,
    )
    if line is None:
        pytest.skip("02-SPIKE-RESULTS.md has no 'Join URL parameters:' line")

    assert isinstance(join.JOIN_IN_FRAGMENT, bool)
    wants_fragment = line.split(":", 1)[1].strip() == "fragment"
    assert wants_fragment == join.JOIN_IN_FRAGMENT


# --- structure ------------------------------------------------------------


def test_the_default_origin_is_named_only_in_vdo_py():
    found = [
        path.relative_to(ROOT).as_posix()
        for directory in ("client_code", "server_code")
        for path in sorted((ROOT / directory).rglob("*.py"))
        if "https://vdo.ninja" in path.read_text(encoding="utf-8")
    ]

    assert found == ["client_code/services/vdo.py"]


def test_join_py_imports_only_slugs_and_vdo_and_touches_no_table():
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

    assert imported == {"iris.services", "slugs", "vdo"}
    assert "app_tables" not in names
