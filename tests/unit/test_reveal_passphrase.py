# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Revealing a permanent room's passphrase to an admin (D-19)."""

import importlib

import anvil.server
import pytest
from room_helpers import permanent  # pyright: ignore[reportMissingImports]

vault_name = "iris.vault"


@pytest.fixture
def vault(Room):  # noqa: N803 (loads the room model first, as the server does)
    return importlib.import_module(vault_name)


@pytest.fixture
def meetings(Room):  # noqa: N803
    return importlib.import_module("iris.meetings")


# --- authorisation --------------------------------------------------------


def test_anonymous_is_refused(Room, tables, admin, fast_kdf, as_user):  # noqa: N803
    permanent(Room)
    as_user(None)

    with pytest.raises(anvil.server.PermissionDenied):
        Room.reveal_passphrase("acme-board")


def test_non_admin_is_refused(Room, tables, admin, fast_kdf, as_user, make_user):  # noqa: N803
    permanent(Room)
    as_user(make_user(email="guest@example.test", is_admin=False))

    with pytest.raises(anvil.server.PermissionDenied):
        Room.reveal_passphrase("acme-board")


def test_refusal_comes_before_the_room_is_looked_up(Room, tables, as_user):  # noqa: N803
    # An anonymous caller learns nothing, not even that a room does not exist.
    as_user(None)

    with pytest.raises(anvil.server.PermissionDenied):
        Room.reveal_passphrase("no-such-room")


def test_callable_requires_admin(meetings, load_client_module):
    permissions = load_client_module("services/permissions")
    found = [
        r
        for r in anvil.server.registrations  # pyright: ignore[reportAttributeAccessIssue]
        if r.kind == "callable" and r.name == "reveal_room_passphrase"
    ]

    assert len(found) == 1
    assert found[0].kwargs.get("require_user") is permissions.is_admin


def test_callable_refuses_a_non_admin(
    meetings,
    Room,
    tables,
    admin,
    fast_kdf,
    as_user,
    make_user,  # noqa: N803
):
    permanent(Room)
    as_user(make_user(email="guest@example.test", is_admin=False))

    with pytest.raises(anvil.server.PermissionDenied):
        meetings.reveal_room_passphrase("acme-board")


def test_the_passphrase_is_in_no_public_reply(Room, tables, admin, fast_kdf, as_user):  # noqa: N803
    created = permanent(Room)
    as_user(None)

    assert created["passphrase"] not in str(Room.lookup("acme-board"))
    unlocked = Room.unlock("acme-board", created["passphrase"])
    assert "passphrase" not in unlocked["found"]
    assert created["passphrase"] not in str(unlocked)


# --- round trip -----------------------------------------------------------


def test_reveal_returns_the_passphrase_shown_at_creation(Room, tables, admin, fast_kdf):  # noqa: N803
    created = permanent(Room)

    assert Room.reveal_passphrase("acme-board") == {
        "status": "ok",
        "passphrase": created["passphrase"],
    }


def test_the_row_holds_ciphertext_never_the_passphrase(Room, tables, admin, fast_kdf):  # noqa: N803
    created = permanent(Room)

    stored = tables.room.rows[0]["passphrase_sealed"]
    assert stored
    assert created["passphrase"] not in stored
    assert created["passphrase"] not in str(tables.room.rows[0]._values)


def test_rotate_stores_the_new_passphrase(Room, tables, admin, fast_kdf):  # noqa: N803
    old = permanent(Room)["passphrase"]

    new = Room.rotate("acme-board")["passphrase"]

    assert new != old
    assert Room.reveal_passphrase("acme-board")["passphrase"] == new


def test_the_revealed_passphrase_unlocks_the_room(  # noqa: N803
    Room, tables, admin, fast_kdf, as_user
):
    permanent(Room)
    shown = Room.reveal_passphrase("acme-board")["passphrase"]
    as_user(None)

    assert Room.unlock("acme-board", shown)["ok"] is True


def test_seal_and_unseal_round_trip(vault):
    sealed = vault.seal("river-lamp-tiger")

    assert sealed != "river-lamp-tiger"
    assert vault.unseal(sealed) == "river-lamp-tiger"


# --- rooms with nothing stored --------------------------------------------


def test_a_room_made_before_has_nothing_to_reveal(Room, tables, admin, fast_kdf):  # noqa: N803
    permanent(Room)
    tables.room.rows[0]["passphrase_sealed"] = None

    assert Room.reveal_passphrase("acme-board") == {"status": "none"}


def test_an_empty_stored_value_has_nothing_to_reveal(  # noqa: N803
    Room, tables, admin, fast_kdf
):
    permanent(Room)
    tables.room.rows[0]["passphrase_sealed"] = ""

    assert Room.reveal_passphrase("acme-board") == {"status": "none"}


def test_rotating_an_old_room_makes_it_revealable(Room, tables, admin, fast_kdf):  # noqa: N803
    permanent(Room)
    tables.room.rows[0]["passphrase_sealed"] = None

    new = Room.rotate("acme-board")["passphrase"]

    assert Room.reveal_passphrase("acme-board")["passphrase"] == new


def test_a_one_off_room_has_no_passphrase(Room, tables, admin):  # noqa: N803
    slug = Room.create_one_off("Kickoff")["slug"]

    with pytest.raises(ValueError, match="Only permanent rooms"):
        Room.reveal_passphrase(slug)


def test_an_unknown_room_is_refused(Room, tables, admin):  # noqa: N803
    with pytest.raises(ValueError, match="No such room"):
        Room.reveal_passphrase("no-such-room")


# --- failures -------------------------------------------------------------


def test_a_missing_key_at_reveal_gives_a_clear_message(
    Room,
    tables,
    admin,
    fast_kdf,
    secret_keys,
    vault,  # noqa: N803
):
    created = permanent(Room)
    secret_keys.clear()

    with pytest.raises(vault.VaultError) as raised:
        Room.reveal_passphrase("acme-board")

    assert "iris_passphrase_key" in str(raised.value)
    assert created["passphrase"] not in str(raised.value)


def test_a_different_key_cannot_read_the_stored_value(
    Room,
    tables,
    admin,
    fast_kdf,
    secret_keys,
    vault,  # noqa: N803
):
    permanent(Room)
    tables.room.rows[0]["passphrase_sealed"] = "not-from-this-key"

    with pytest.raises(vault.VaultError, match="not the key that stored it"):
        Room.reveal_passphrase("acme-board")


def test_vault_error_is_a_value_error_so_the_client_shows_it(vault):
    assert issubclass(vault.VaultError, ValueError)


def test_a_missing_key_refuses_creation_and_makes_no_room(
    Room,
    tables,
    admin,
    fast_kdf,
    secret_keys,
    vault,  # noqa: N803
):
    secret_keys.clear()

    with pytest.raises(vault.VaultError, match="could not be stored"):
        permanent(Room)

    assert len(tables.room.rows) == 0


def test_a_missing_key_leaves_a_rotation_unchanged(
    Room,
    tables,
    admin,
    fast_kdf,
    secret_keys,
    vault,  # noqa: N803
):
    created = permanent(Room)
    before = dict(tables.room.rows[0]._values)
    secret_keys.clear()

    with pytest.raises(vault.VaultError):
        Room.rotate("acme-board")

    assert dict(tables.room.rows[0]._values) == before
    secret_keys.add("iris_passphrase_key")
    assert Room.reveal_passphrase("acme-board")["passphrase"] == created["passphrase"]
