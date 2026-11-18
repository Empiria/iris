# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import anvil.server
import pytest
from room_helpers import permanent


def test_create_permanent_returns_slug_title_and_one_passphrase(
    Room, tables, admin, fast_kdf
):
    result = permanent(Room)

    assert set(result) == {"slug", "title", "passphrase"}
    assert result["slug"] == "acme-board"
    assert result["title"] == "Acme quarterly"
    groups = result["passphrase"].split("-")
    assert [len(g) for g in groups] == [4, 4, 4]


def test_create_permanent_stores_the_row_and_saves_it(Room, tables, admin, verifier):
    result = permanent(Room)

    assert len(tables.room.rows) == 1
    row = tables.room.rows[0]
    assert row["slug"] == "acme-board"
    assert row["kind"] == "permanent"
    assert row["active"] is True
    assert row["title"] == "Acme quarterly"
    assert row["created_by"] == "admin@example.test"
    assert len(row["vdo_room"]) == 20
    assert row["vdo_room"] != row["slug"]
    assert len(row["vdo_password"]) == 24
    assert set(row["vdo_password"]) <= set("0123456789abcdef")
    assert row["kdf_iterations"] == verifier.ITERATIONS == 600000
    assert row["failed_unlocks"] == 0
    assert row["locked_until"] is None
    assert row.saves >= 1
    assert result["passphrase"]


def test_create_permanent_stores_no_trace_of_the_passphrase(
    Room, tables, admin, fast_kdf
):
    result = permanent(Room)
    row = tables.room.rows[0]
    normalised = result["passphrase"].replace("-", "")

    for column, value in row._values.items():
        text = str(value)
        assert result["passphrase"] not in text, column
        assert normalised not in text, column


def test_create_permanent_draws_a_new_room_password_and_passphrase_each_time(
    Room, tables, admin, fast_kdf
):
    first = permanent(Room, "Room one")
    second = permanent(Room, "Room two")

    assert first["passphrase"] != second["passphrase"]
    one, two = tables.room.rows
    assert one["vdo_room"] != two["vdo_room"]
    assert one["vdo_password"] != two["vdo_password"]
    assert one["verifier_salt"] != two["verifier_salt"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("ab", "Use at least 3 characters for the name."),
        ("a" * 65, "Use at most 64 characters for the name."),
        ("bad!name", "Use only letters, numbers and dashes in the name."),
        ("-lead", "The name can't start or end with a dash."),
        ("admin", "That name is reserved."),
    ],
)
def test_create_permanent_passes_slug_errors_on(
    Room, tables, admin, fast_kdf, text, message
):
    with pytest.raises(ValueError) as refused:
        Room.create_permanent(text, title="x")

    assert str(refused.value) == message
    assert tables.room.rows == []


@pytest.mark.parametrize("kind", ["one-off", "permanent"])
@pytest.mark.parametrize("active", [True, False])
def test_create_permanent_refuses_a_taken_slug_of_either_kind(
    Room, tables, admin, fast_kdf, kind, active
):
    tables.room.add_row(slug="acme-board", kind=kind, active=active, vdo_room="v" * 20)

    with pytest.raises(ValueError) as refused:
        Room.create_permanent("Acme Board", title="x")

    assert str(refused.value) == "That name is taken."
    assert len(tables.room.rows) == 1


def test_create_permanent_refuses_signed_out(Room, tables, as_user, fast_kdf):
    as_user(None)

    with pytest.raises(anvil.server.PermissionDenied):
        Room.create_permanent("Acme Board", title="x")

    assert tables.room.rows == []
    assert tables.room.reads == 0


def test_create_permanent_refuses_non_admin(Room, tables, as_user, make_user, fast_kdf):
    as_user(make_user(email="viewer@example.test", is_admin=False))

    with pytest.raises(anvil.server.PermissionDenied):
        Room.create_permanent("Acme Board", title="x")

    assert tables.room.rows == []
    assert tables.room.reads == 0


def test_lookup_of_a_permanent_room_is_locked_and_nothing_else(
    Room, tables, admin, fast_kdf
):
    permanent(Room)

    assert Room.lookup("acme-board") == {"kind": "permanent", "locked": True}


def test_lookup_of_an_inactive_permanent_room_is_none(Room, tables, admin, fast_kdf):
    permanent(Room)
    tables.room.rows[0]["active"] = False

    assert Room.lookup("acme-board") is None


def test_lookup_of_a_permanent_room_reads_no_setting(Room, tables, admin, fast_kdf):
    permanent(Room)
    tables.setting.reads = 0

    Room.lookup("acme-board")

    assert tables.setting.reads == 0
