import importlib

import anvil.server
import pytest


@pytest.fixture
def meetings(load_client_module):
    # Room and permissions load first, as they do on the server.
    load_client_module("services/model/room")
    return importlib.import_module("iris.meetings")


@pytest.fixture
def Room(load_client_module):  # noqa: N802
    return load_client_module("services/model/room").Room


@pytest.fixture
def slugs(load_client_module):
    return load_client_module("services/slugs")


@pytest.fixture
def links(load_client_module):
    return load_client_module("services/links")


@pytest.fixture
def staff(as_user, make_user):
    user = make_user(email="staff@example.test", is_staff=True)
    as_user(user)
    return user


# --- registration ---------------------------------------------------------


def test_create_one_off_link_requires_staff(meetings, load_client_module):
    permissions = load_client_module("services/permissions")
    found = [
        r
        for r in anvil.server.registrations
        if r.kind == "callable" and r.name == "create_one_off_link"
    ]

    assert len(found) == 1
    assert found[0].kwargs.get("require_user") is permissions.is_staff


# --- create_one_off_link --------------------------------------------------


def test_returns_slug_and_title_and_stores_one_row(meetings, tables, staff, slugs):
    result = meetings.create_one_off_link("Kickoff")

    assert set(result) == {"slug", "title"}
    assert result["title"] == "Kickoff"
    assert len(result["slug"]) == 8
    assert set(result["slug"]) <= set(slugs.ONE_OFF_ALPHABET)
    assert len(tables.room.rows) == 1
    row = tables.room.rows[0]
    assert row["slug"] == result["slug"]
    assert row["kind"] == "one-off"
    assert row["active"] is True
    assert row["created_by"] == "staff@example.test"
    assert len(row["vdo_room"]) == 20
    assert row["vdo_room"] != result["slug"]


def test_two_calls_give_two_links_and_two_rooms(meetings, tables, staff):
    first = meetings.create_one_off_link("")
    second = meetings.create_one_off_link("")

    assert first["slug"] != second["slug"]
    assert len(tables.room.rows) == 2
    assert tables.room.rows[0]["vdo_room"] != tables.room.rows[1]["vdo_room"]


def test_the_reply_and_the_link_never_contain_the_vdo_room(
    meetings, tables, staff, links
):
    result = meetings.create_one_off_link("Kickoff")
    vdo_room = tables.room.rows[0]["vdo_room"]

    assert vdo_room not in result
    assert vdo_room not in result.values()
    assert vdo_room not in repr(result)
    for owner in ("runtime", "own", "query"):
        link = links.link_for("https://meet.example", result["slug"], owner)
        assert vdo_room not in link


def test_signed_out_is_refused_and_writes_nothing(meetings, tables, as_user):
    as_user(None)

    with pytest.raises(anvil.server.PermissionDenied):
        meetings.create_one_off_link("x")

    assert tables.room.rows == []
    assert tables.room.reads == 0


@pytest.mark.parametrize("flag", [False, None])
def test_non_staff_is_refused_and_writes_nothing(
    meetings, tables, as_user, make_user, flag
):
    as_user(make_user(is_staff=flag))

    with pytest.raises(anvil.server.PermissionDenied):
        meetings.create_one_off_link("x")

    assert tables.room.rows == []
    assert tables.room.reads == 0


def test_the_title_is_cleaned_before_it_is_stored(meetings, tables, staff):
    result = meetings.create_one_off_link("  Kick\toff\n ")

    assert result["title"] == "Kick off"
    assert tables.room.rows[0]["title"] == "Kick off"


def test_a_blank_title_is_stored_as_empty(meetings, tables, staff):
    result = meetings.create_one_off_link("   ")

    assert result["title"] == ""
    assert tables.room.rows[0]["title"] == ""


def test_the_title_defaults_to_empty(meetings, tables, staff):
    assert meetings.create_one_off_link()["title"] == ""


# --- STAFF-07, pinned from the creation side ------------------------------


def test_lookup_finds_the_created_room_and_nothing_else(
    meetings, Room, tables, staff, slugs
):
    result = meetings.create_one_off_link("Kickoff")
    stored = tables.room.rows[0]["vdo_room"]

    found = Room.lookup(result["slug"])

    assert found is not None
    assert found["vdo_room"] == stored
    for _ in range(200):
        invented = slugs.new_one_off_slug()
        if invented == result["slug"]:
            continue
        assert Room.lookup(invented) is None


# --- clean_title ----------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, ""),
        ("", ""),
        ("  Kickoff  ", "Kickoff"),
        ("a\nb\tc", "a b c"),
        ("a\x00b", "a b"),
        ("a\x07b\x1fc", "a b c"),
        ("a\x7fb", "a b"),
    ],
)
def test_clean_title(meetings, raw, expected):
    assert meetings.clean_title(raw) == expected


def test_clean_title_caps_the_length_at_80(meetings):
    assert meetings.clean_title("x" * 200) == "x" * 80


@pytest.mark.parametrize("raw", [5, 1.5, ["a"], {"a": 1}, b"abc", True])
def test_clean_title_rejects_non_text(meetings, raw):
    with pytest.raises(ValueError, match="Title must be text"):
        meetings.clean_title(raw)
