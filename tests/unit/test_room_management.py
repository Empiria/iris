# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import datetime

import anvil.server
import pytest
from room_helpers import permanent

SUMMARY_KEYS = {"slug", "title", "kind", "created"}
MANAGEMENT = ("list_for_admin", "update_title", "remove", "rotate")


def _call_management(Room, name):
    """Call each management method with arguments that would succeed for admin."""
    args = {
        "list_for_admin": (),
        "update_title": ("acme-board", "New title"),
        "remove": ("acme-board",),
        "rotate": ("acme-board",),
    }[name]
    return getattr(Room, name)(*args)


def test_list_for_admin_of_an_empty_table_is_an_empty_list(Room, tables, admin):
    assert Room.list_for_admin() == []


def test_list_for_admin_returns_exactly_slug_title_kind_and_created(
    Room, tables, admin, fast_kdf
):
    permanent(Room)
    Room.create_one_off(title="Kickoff")

    rooms = Room.list_for_admin()

    assert len(rooms) == 2
    for room in rooms:
        assert set(room) == SUMMARY_KEYS
        assert isinstance(room["created"], datetime.datetime)
    assert {r["kind"] for r in rooms} == {"one-off", "permanent"}
    by_slug = {r["slug"]: r for r in rooms}
    assert by_slug["acme-board"]["title"] == "Acme quarterly"


def test_list_for_admin_carries_no_secret_of_any_room(Room, tables, admin, fast_kdf):
    permanent(Room)
    Room.create_one_off(title="Kickoff")

    text = repr(Room.list_for_admin())

    for row in tables.room.rows:
        for column in ("vdo_room", "vdo_password", "verifier", "verifier_salt"):
            if row.get(column):
                assert str(row.get(column)) not in text, column
    for word in ("vdo_room", "vdo_password", "verifier", "failed_unlocks"):
        assert word not in text


def test_list_for_admin_is_newest_first(Room, tables, admin):
    for slug, day in (("older-room", 3), ("newest-room", 20), ("middle-room", 9)):
        tables.room.add_row(
            slug=slug,
            vdo_room="r" * 20,
            title=slug,
            kind="one-off",
            active=True,
            created_by="admin@example.test",
            created=datetime.datetime(2026, 11, day),
        )

    assert [r["slug"] for r in Room.list_for_admin()] == [
        "newest-room",
        "middle-room",
        "older-room",
    ]


def test_list_for_admin_puts_a_row_with_no_date_last_and_copes(Room, tables, admin):
    for slug, created in (
        ("undated-room", None),
        ("dated-room", datetime.datetime(2026, 11, 1)),
    ):
        tables.room.add_row(
            slug=slug,
            vdo_room="r" * 20,
            title="",
            kind="one-off",
            active=True,
            created_by="admin@example.test",
            created=created,
        )

    assert [r["slug"] for r in Room.list_for_admin()] == ["dated-room", "undated-room"]


def test_list_for_admin_copes_with_a_timezone_aware_and_a_naive_date(
    Room, tables, admin
):
    aware = datetime.datetime(
        2026, 11, 5, 12, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=2))
    )
    for slug, created in (
        ("aware-room", aware),
        ("naive-room", datetime.datetime(2026, 11, 6)),
    ):
        tables.room.add_row(
            slug=slug,
            vdo_room="r" * 20,
            title="",
            kind="one-off",
            active=True,
            created_by="admin@example.test",
            created=created,
        )

    assert [r["slug"] for r in Room.list_for_admin()] == ["naive-room", "aware-room"]


def test_update_title_sets_the_title_and_the_updated_time_and_saves(
    Room, tables, admin, fast_kdf, clock
):
    permanent(Room)
    row = tables.room.rows[0]
    before = {k: row[k] for k in ("slug", "vdo_room", "vdo_password", "verifier")}
    saves = row.saves
    clock.advance(hours=2)

    result = Room.update_title("acme-board", "Renamed meeting")

    assert set(result) == SUMMARY_KEYS
    assert result["slug"] == "acme-board"
    assert result["title"] == "Renamed meeting"
    assert row["title"] == "Renamed meeting"
    assert row["updated"] == clock.now
    assert row.saves > saves
    for column, value in before.items():
        assert row[column] == value, column


def test_update_title_may_empty_the_title(Room, tables, admin, fast_kdf):
    permanent(Room)

    assert Room.update_title("acme-board", "")["title"] == ""


def test_update_title_finds_the_room_whatever_the_case(Room, tables, admin, fast_kdf):
    permanent(Room)

    assert Room.update_title("  ACME-Board ", "x")["slug"] == "acme-board"


def test_update_title_works_on_a_one_off_room(Room, tables, admin):
    made = Room.create_one_off(title="Kickoff")

    result = Room.update_title(made["slug"], "Moved")

    assert result["title"] == "Moved"
    assert result["kind"] == "one-off"


@pytest.mark.parametrize("slug", ["no-such-room", "", "../x", "x", None, 5, ["a"]])
@pytest.mark.parametrize("name", ["update_title", "remove", "rotate"])
def test_an_unknown_or_malformed_slug_is_no_such_room(
    Room, tables, admin, fast_kdf, name, slug
):
    permanent(Room)
    args = (slug, "x") if name == "update_title" else (slug,)

    with pytest.raises(ValueError) as refused:
        getattr(Room, name)(*args)

    assert str(refused.value) == "No such room."
    assert len(tables.room.rows) == 1


@pytest.mark.parametrize("title", [5, ["a"], b"x"])
def test_update_title_refuses_a_title_that_is_not_text(
    Room, tables, admin, fast_kdf, title
):
    permanent(Room)

    with pytest.raises(ValueError, match="Title must be text"):
        Room.update_title("acme-board", title)

    assert tables.room.rows[0]["title"] == "Acme quarterly"


def test_remove_deletes_the_row_and_the_link_is_dead(Room, tables, admin, fast_kdf):
    made = Room.create_one_off(title="Kickoff")
    permanent(Room)

    assert Room.remove("acme-board") == {"slug": "acme-board"}

    assert [r["slug"] for r in tables.room.rows] == [made["slug"]]
    assert Room.lookup("acme-board") is None
    assert Room.unlock("acme-board", "aaaa-bbbb-cccc") == {
        "ok": False,
        "reason": "missing",
    }


def test_remove_of_a_one_off_room_kills_its_link(Room, tables, admin):
    made = Room.create_one_off(title="Kickoff")

    Room.remove(made["slug"])

    assert Room.lookup(made["slug"]) is None
    assert tables.room.rows == []


def test_remove_frees_the_slug_for_a_new_permanent_room(Room, tables, admin, fast_kdf):
    first = permanent(Room)
    Room.remove("acme-board")

    second = permanent(Room)

    assert second["slug"] == "acme-board"
    assert second["passphrase"] != first["passphrase"]
    assert len(tables.room.rows) == 1


def test_remove_twice_is_no_such_room(Room, tables, admin, fast_kdf):
    permanent(Room)
    Room.remove("acme-board")

    with pytest.raises(ValueError, match="No such room."):
        Room.remove("acme-board")


def test_remove_leaves_other_rooms_alone(Room, tables, admin, fast_kdf):
    permanent(Room, "Room one")
    permanent(Room, "Room two")

    Room.remove("room-one")

    assert [r["slug"] for r in tables.room.rows] == ["room-two"]


def test_rotate_returns_the_slug_and_one_new_passphrase_only(
    Room, tables, admin, fast_kdf
):
    made = permanent(Room)

    result = Room.rotate("acme-board")

    assert set(result) == {"slug", "passphrase"}
    assert result["slug"] == "acme-board"
    assert [len(g) for g in result["passphrase"].split("-")] == [4, 4, 4]
    assert result["passphrase"] != made["passphrase"]


def test_rotate_old_passphrase_fails_and_the_new_one_unlocks(
    Room, tables, admin, as_user, fast_kdf
):
    made = permanent(Room)
    result = Room.rotate("acme-board")
    as_user(None)

    assert Room.unlock("acme-board", made["passphrase"]) == {
        "ok": False,
        "reason": "incorrect",
    }
    unlocked = Room.unlock("acme-board", result["passphrase"])

    assert unlocked["ok"] is True
    assert unlocked["found"]["title"] == "Acme quarterly"


def test_rotate_renews_the_vdo_room_and_the_vdo_password(
    Room, tables, admin, as_user, fast_kdf
):
    made = permanent(Room)
    row = tables.room.rows[0]
    old_room, old_password = row["vdo_room"], row["vdo_password"]
    saves = row.saves

    result = Room.rotate("acme-board")

    assert row["vdo_room"] != old_room
    assert len(row["vdo_room"]) == 20
    assert row["vdo_password"] != old_password
    assert len(row["vdo_password"]) == 24
    assert set(row["vdo_password"]) <= set("0123456789abcdef")
    assert row.saves > saves
    as_user(None)
    found = Room.unlock("acme-board", result["passphrase"])["found"]
    assert found["vdo_room"] == row["vdo_room"]
    assert found["password"] == row["vdo_password"]
    assert made["passphrase"] != result["passphrase"]


def test_rotate_clears_a_lock_and_the_failed_count(
    Room, tables, admin, as_user, fast_kdf, clock
):
    permanent(Room)
    row = tables.room.rows[0]
    row["failed_unlocks"] = 10
    row["locked_until"] = clock.now + datetime.timedelta(minutes=5)

    result = Room.rotate("acme-board")

    assert row["failed_unlocks"] == 0
    assert row["locked_until"] is None
    assert row["updated"] == clock.now
    as_user(None)
    assert Room.unlock("acme-board", result["passphrase"])["ok"] is True


def test_rotate_stores_no_trace_of_the_passphrase(Room, tables, admin, fast_kdf):
    permanent(Room)

    result = Room.rotate("acme-board")
    row = tables.room.rows[0]

    for column, value in row._values.items():
        assert result["passphrase"] not in str(value), column
        assert result["passphrase"].replace("-", "") not in str(value), column


def test_rotate_keeps_the_slug_title_and_kind(Room, tables, admin, fast_kdf):
    permanent(Room)

    Room.rotate("acme-board")

    row = tables.room.rows[0]
    assert (row["slug"], row["title"], row["kind"], row["active"]) == (
        "acme-board",
        "Acme quarterly",
        "permanent",
        True,
    )


def test_rotate_of_a_one_off_room_is_refused_and_changes_nothing(Room, tables, admin):
    made = Room.create_one_off(title="Kickoff")
    row = tables.room.rows[0]
    before = dict(row._values)

    with pytest.raises(ValueError) as refused:
        Room.rotate(made["slug"])

    assert str(refused.value) == "Only permanent rooms have a passphrase."
    assert row._values == before


@pytest.mark.parametrize("name", MANAGEMENT)
def test_management_methods_refuse_signed_out_and_touch_nothing(
    Room, tables, admin, fast_kdf, as_user, name
):
    permanent(Room)
    before = [dict(r._values) for r in tables.room.rows]
    reads = tables.room.reads
    as_user(None)

    with pytest.raises(anvil.server.PermissionDenied):
        _call_management(Room, name)

    assert [dict(r._values) for r in tables.room.rows] == before
    assert tables.room.reads == reads


@pytest.mark.parametrize("name", MANAGEMENT)
def test_management_methods_refuse_non_admin_and_touch_nothing(
    Room, tables, admin, fast_kdf, as_user, make_user, name
):
    permanent(Room)
    before = [dict(r._values) for r in tables.room.rows]
    reads = tables.room.reads
    as_user(make_user(email="viewer@example.test", is_admin=False))

    with pytest.raises(anvil.server.PermissionDenied):
        _call_management(Room, name)

    assert [dict(r._values) for r in tables.room.rows] == before
    assert tables.room.reads == reads


def test_management_methods_are_registered_server_methods(Room):
    registered = {
        r.name for r in anvil.server.registrations if r.kind == "server_method"
    }

    assert {f"Room.{name}" for name in MANAGEMENT} <= registered
