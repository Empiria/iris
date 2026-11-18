"""lookup_room: the public callable that opens a meeting link (JOIN-01, JOIN-04).

Also pins JOIN-06 at the lookup (a stored profile that forces relaying never
leaves the server) and DEPL-01 (the origin comes from the setting table).
"""

import importlib

import anvil.server
import pytest

SLUG = "dk2wjd9d"
VDO_ROOM = "kdvx2p8wmq5rt7hzn3c1"
# Test data only: not a code default.
PROFILE = "ssq=-1&sharperscreen&rbr=50000&trb=50000&crb&codec=av1,vp9,vp8,h264&q=0"


@pytest.fixture
def meetings(load_client_module):
    load_client_module("services/model/room")
    return importlib.import_module("iris.meetings")


def _room(tables, slug=SLUG, active=True, title="Kickoff"):
    return tables.room.add_row(
        slug=slug,
        vdo_room=VDO_ROOM,
        title=title,
        kind="one-off",
        active=active,
        created_by="staff@example.test",
    )


def _setting(tables, key, value):
    tables.setting.add_row(key=key, value=value)


# --- registration ---------------------------------------------------------


def test_lookup_room_is_a_plain_public_callable(meetings):
    found = [
        r
        for r in anvil.server.registrations
        if r.kind == "callable" and r.name == "lookup_room"
    ]

    assert len(found) == 1
    assert "require_user" not in found[0].kwargs


# --- the reply ------------------------------------------------------------


def test_reply_holds_exactly_what_a_join_needs(meetings, tables):
    _room(tables)

    found = meetings.lookup_room(SLUG)

    assert set(found) == {"vdo_room", "title", "origin", "profile", "salt"}
    assert found["vdo_room"] == VDO_ROOM
    assert found["title"] == "Kickoff"
    assert found["origin"] == "https://vdo.ninja"
    assert found["profile"] == ""
    assert found["salt"] is None
    for key in ("created_by", "kind", "active", "slug"):
        assert key not in found


@pytest.mark.parametrize("who", ["anonymous", "non-staff", "staff"])
def test_the_same_reply_for_every_caller(meetings, tables, as_user, make_user, who):
    _room(tables)
    if who == "non-staff":
        as_user(make_user(email="viewer@example.test", is_staff=False))
    elif who == "staff":
        as_user(make_user())
    else:
        as_user(None)

    found = meetings.lookup_room(SLUG)

    assert found["vdo_room"] == VDO_ROOM


def test_padding_and_capitals_resolve_to_the_same_room(meetings, tables):
    _room(tables)

    assert meetings.lookup_room(" DK2WJD9D ")["vdo_room"] == VDO_ROOM


# --- refusals -------------------------------------------------------------


def test_an_unknown_slug_returns_none(meetings, tables):
    _room(tables)

    assert meetings.lookup_room("zzzzzzzz") is None


def test_an_inactive_room_returns_none(meetings, tables):
    _room(tables, active=False)

    assert meetings.lookup_room(SLUG) is None


@pytest.mark.parametrize(
    "bad",
    ["ab", "../x", "Has Space", "staff", "a" * 65, "", None, 5],
    ids=["short", "path", "space", "reserved", "long", "empty", "none", "int"],
)
def test_a_bad_input_returns_none_and_reads_nothing(meetings, tables, bad):
    _room(tables)
    tables.room.reads = 0

    assert meetings.lookup_room(bad) is None
    assert tables.room.reads == 0


# --- DEPL-01 --------------------------------------------------------------


@pytest.mark.parametrize(
    "origin",
    ["https://meet.example.test", "http://127.0.0.1:3030"],
)
def test_the_stored_origin_is_the_one_returned(meetings, tables, origin):
    _room(tables)
    _setting(tables, "vdo_origin", origin)

    assert meetings.lookup_room(SLUG)["origin"] == origin


def test_the_stored_profile_and_salt_are_returned(meetings, tables):
    _room(tables)
    _setting(tables, "vdo_profile", PROFILE)
    _setting(tables, "vdo_salt", "pepper")

    found = meetings.lookup_room(SLUG)

    assert found["profile"] == PROFILE
    assert found["salt"] == "pepper"


# --- JOIN-06 at the lookup ------------------------------------------------


@pytest.mark.parametrize("bad", ["q=0&meshcast", "relay=1", "a=1&%52elay=1"])
def test_a_stored_profile_that_forces_relaying_is_refused(meetings, tables, bad):
    _room(tables)
    _setting(tables, "vdo_profile", bad)

    with pytest.raises(ValueError) as refused:
        meetings.lookup_room(SLUG)

    assert "vdo_profile" in str(refused.value)
    assert bad not in str(refused.value)


def test_a_stored_origin_over_plain_http_is_refused(meetings, tables):
    _room(tables)
    _setting(tables, "vdo_origin", "http://evil.example")

    with pytest.raises(ValueError) as refused:
        meetings.lookup_room(SLUG)

    assert "vdo_origin" in str(refused.value)
    assert "evil.example" not in str(refused.value)
