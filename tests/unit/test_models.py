import datetime

import anvil.server
import pytest

SCREEN_SHARE = "ssq=-1&sharperscreen&rbr=50000&trb=50000&crb&codec=av1,vp9,vp8,h264&q=0"


@pytest.fixture
def Room(load_client_module):  # noqa: N802
    return load_client_module("services/model/room").Room


@pytest.fixture
def slugs(load_client_module):
    return load_client_module("services/slugs")


@pytest.fixture
def staff(as_user, make_user):
    user = make_user(email="staff@example.test", is_staff=True)
    as_user(user)
    return user


def _add_room(tables, slug, vdo_room="r" * 20, active=True, title="T"):
    return tables.room.add_row(
        slug=slug,
        vdo_room=vdo_room,
        title=title,
        kind="one-off",
        active=active,
        created_by="staff@example.test",
        created=datetime.datetime(2026, 1, 1),
    )


# --- lookup ---------------------------------------------------------------


def test_lookup_empty_table_returns_none(Room, tables):
    assert Room.lookup("dk2wjd9d") is None


def test_lookup_returns_exactly_what_a_join_needs(Room, tables, staff):
    made = Room.create_one_off(title="Kickoff")
    row = tables.room.rows[0]

    found = Room.lookup(made["slug"])

    assert set(found) == {"vdo_room", "title", "origin", "profile", "salt"}
    assert found["vdo_room"] == row["vdo_room"]
    assert found["vdo_room"] != made["slug"]
    assert found["title"] == "Kickoff"
    assert found["origin"] == "https://vdo.ninja"
    assert found["profile"] == ""
    assert found["salt"] is None


def test_lookup_carries_the_settings(Room, tables):
    _add_room(tables, "dk2wjd9d")
    tables.setting.add_row(key="vdo_origin", value="https://meet.example.test")
    tables.setting.add_row(key="vdo_profile", value=SCREEN_SHARE)
    tables.setting.add_row(key="vdo_salt", value="abc")

    found = Room.lookup("dk2wjd9d")

    assert found["origin"] == "https://meet.example.test"
    assert found["profile"] == SCREEN_SHARE
    assert found["salt"] == "abc"


def test_lookup_of_an_invented_slug_releases_nothing(Room, tables):
    _add_room(tables, "dk2wjd9d")

    assert Room.lookup("abcdefgh") is None


def test_lookup_of_an_inactive_row_returns_none(Room, tables):
    _add_room(tables, "dk2wjd9d", active=False)

    assert Room.lookup("dk2wjd9d") is None


@pytest.mark.parametrize("slug", ["", "../x", "staff", None, "a b"])
def test_lookup_of_a_malformed_or_reserved_slug_reads_no_table(Room, tables, slug):
    assert Room.lookup(slug) is None
    assert tables.room.reads == 0


def test_lookup_normalises_case_and_whitespace(Room, tables):
    _add_room(tables, "dk2wjd9d", vdo_room="v" * 20)

    assert Room.lookup("  DK2WJD9D ")["vdo_room"] == "v" * 20


# --- create_one_off -------------------------------------------------------


def test_create_one_off_stores_the_row_and_returns_slug_and_title(
    Room, tables, staff, slugs
):
    result = Room.create_one_off(title="Kickoff")

    assert set(result) == {"slug", "title"}
    assert result["title"] == "Kickoff"
    assert len(tables.room.rows) == 1
    row = tables.room.rows[0]
    assert row["slug"] == result["slug"]
    assert len(row["slug"]) == 8
    assert set(row["slug"]) <= set(slugs.ONE_OFF_ALPHABET)
    assert len(row["vdo_room"]) == 20
    assert row["vdo_room"] != row["slug"]
    assert row["title"] == "Kickoff"
    assert row["kind"] == "one-off"
    assert row["active"] is True
    assert row["created_by"] == "staff@example.test"
    assert isinstance(row["created"], datetime.datetime)


def test_create_one_off_title_defaults_to_empty(Room, tables, staff):
    assert Room.create_one_off()["title"] == ""


def test_create_one_off_refuses_signed_out(Room, tables, as_user):
    as_user(None)

    with pytest.raises(anvil.server.PermissionDenied):
        Room.create_one_off(title="x")

    assert tables.room.rows == []
    assert tables.room.reads == 0


def test_create_one_off_refuses_non_staff(Room, tables, as_user, make_user):
    as_user(make_user(is_staff=False))

    with pytest.raises(anvil.server.PermissionDenied):
        Room.create_one_off(title="x")

    assert tables.room.rows == []
    assert tables.room.reads == 0


def _draws(monkeypatch, slugs, values):
    queue = list(values)
    monkeypatch.setattr(slugs, "new_one_off_slug", lambda: queue.pop(0))


def test_create_one_off_redraws_a_taken_slug(Room, tables, staff, slugs, monkeypatch):
    _add_room(tables, "taken234")
    _draws(monkeypatch, slugs, ["taken234", "fresh345"])

    assert Room.create_one_off(title="x")["slug"] == "fresh345"
    assert len(tables.room.rows) == 2


def test_create_one_off_redraws_a_reserved_slug(
    Room, tables, staff, slugs, monkeypatch
):
    _draws(monkeypatch, slugs, ["staff", "fresh345"])

    assert Room.create_one_off(title="x")["slug"] == "fresh345"


def test_create_one_off_gives_up_after_ten_taken_slugs(
    Room, tables, staff, slugs, monkeypatch
):
    _add_room(tables, "taken234")
    monkeypatch.setattr(slugs, "new_one_off_slug", lambda: "taken234")

    with pytest.raises(RuntimeError):
        Room.create_one_off(title="x")

    assert len(tables.room.rows) == 1


# --- registration ---------------------------------------------------------


def test_room_methods_are_registered_server_methods(Room):
    registered = {
        r.name for r in anvil.server.registrations if r.kind == "server_method"
    }

    assert {"Room.lookup", "Room.create_one_off"} <= registered
