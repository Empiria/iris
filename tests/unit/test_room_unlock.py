# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import datetime

import anvil.server
import pytest
from room_helpers import START, permanent


def test_unlock_with_the_right_passphrase_releases_the_join_info(
    Room, tables, admin, as_user, fast_kdf
):
    made = permanent(Room)
    row = tables.room.rows[0]
    tables.setting.add_row(key="vdo_origin", value="https://meet.example.test")
    tables.setting.add_row(key="vdo_salt", value="pepper")
    as_user(None)

    result = Room.unlock("acme-board", made["passphrase"])

    assert result == {
        "ok": True,
        "found": {
            "vdo_room": row["vdo_room"],
            "password": row["vdo_password"],
            "title": "Acme quarterly",
            "origin": "https://meet.example.test",
            "profile": "",
            "salt": "pepper",
            "kind": "permanent",
        },
    }


@pytest.mark.parametrize(
    "retype",
    [
        lambda p: p.upper(),
        lambda p: p.replace("-", ""),
        lambda p: p.replace("-", " "),
        lambda p: "  " + p.upper().replace("-", " - ") + "  ",
    ],
    ids=["upper", "no-dashes", "spaces", "padded"],
)
def test_unlock_ignores_case_dashes_and_spaces(
    Room, tables, admin, as_user, fast_kdf, retype
):
    made = permanent(Room)
    as_user(None)

    assert Room.unlock("acme-board", retype(made["passphrase"]))["ok"] is True


def test_unlock_a_wrong_passphrase_is_incorrect_and_counts(
    Room, tables, admin, as_user, fast_kdf
):
    permanent(Room)
    as_user(None)

    result = Room.unlock("acme-board", "aaaa-bbbb-cccc")

    assert result == {"ok": False, "reason": "incorrect"}
    assert tables.room.rows[0]["failed_unlocks"] == 1
    assert tables.room.rows[0].saves >= 2


@pytest.mark.parametrize("slug", ["no-such-room", "kickoff1", "x", "../etc", None, 5])
def test_unlock_of_an_unknown_or_one_off_slug_is_missing(
    Room, tables, admin, as_user, fast_kdf, slug
):
    tables.room.add_row(slug="kickoff1", kind="one-off", active=True, vdo_room="v" * 20)
    as_user(None)

    assert Room.unlock(slug, "aaaa-bbbb-cccc") == {"ok": False, "reason": "missing"}


def test_unlock_of_an_inactive_room_is_missing(Room, tables, admin, as_user, fast_kdf):
    made = permanent(Room)
    tables.room.rows[0]["active"] = False
    as_user(None)

    assert Room.unlock("acme-board", made["passphrase"]) == {
        "ok": False,
        "reason": "missing",
    }


@pytest.mark.parametrize("text", ["", "   ", "- - -", None, 5, ["a"]])
def test_unlock_with_nothing_typed_is_empty_and_hashes_nothing(
    Room, tables, admin, as_user, fast_kdf, verifier, monkeypatch, text
):
    permanent(Room)
    as_user(None)

    def boom(*args, **kwargs):
        raise AssertionError("hashed an empty input")

    monkeypatch.setattr(verifier, "check_passphrase", boom)

    assert Room.unlock("acme-board", text) == {"ok": False, "reason": "empty"}
    assert tables.room.rows[0]["failed_unlocks"] == 0


def test_unlock_of_an_oversized_input_is_incorrect_and_hashes_nothing(
    Room, tables, admin, as_user, fast_kdf, verifier, monkeypatch
):
    permanent(Room)
    as_user(None)
    huge = "secret-" * 100

    def boom(*args, **kwargs):
        raise AssertionError("hashed an oversized input")

    monkeypatch.setattr(verifier, "check_passphrase", boom)

    assert Room.unlock("acme-board", huge) == {"ok": False, "reason": "incorrect"}


def test_nothing_the_unlock_raises_or_returns_carries_the_input(
    Room, tables, admin, as_user, fast_kdf
):
    permanent(Room)
    as_user(None)
    typed = "zzzz-yyyy-xxxx"

    result = Room.unlock("acme-board", typed)

    assert typed not in repr(result)
    assert "zzzzyyyyxxxx" not in repr(result)


def test_ten_wrong_in_a_row_lock_the_room_for_five_minutes(
    Room, tables, admin, as_user, fast_kdf, clock
):
    made = permanent(Room)
    as_user(None)

    for _ in range(9):
        assert Room.unlock("acme-board", "aaaa-bbbb-cccc")["reason"] == "incorrect"
    assert tables.room.rows[0]["locked_until"] is None
    assert Room.unlock("acme-board", "aaaa-bbbb-cccc")["reason"] == "incorrect"

    row = tables.room.rows[0]
    assert row["failed_unlocks"] == 10
    assert row["locked_until"] == START + datetime.timedelta(minutes=5)
    assert Room.unlock("acme-board", made["passphrase"]) == {
        "ok": False,
        "reason": "throttled",
    }


def test_a_locked_room_refuses_before_hashing(
    Room, tables, admin, as_user, fast_kdf, clock, verifier, monkeypatch
):
    permanent(Room)
    as_user(None)
    row = tables.room.rows[0]
    row["failed_unlocks"] = 10
    row["locked_until"] = START + datetime.timedelta(minutes=3)

    def boom(*args, **kwargs):
        raise AssertionError("hashed while locked")

    monkeypatch.setattr(verifier, "check_passphrase", boom)

    assert Room.unlock("acme-board", "aaaa-bbbb-cccc")["reason"] == "throttled"
    assert row["failed_unlocks"] == 10


def test_after_the_window_the_right_passphrase_works_and_resets_the_count(
    Room, tables, admin, as_user, fast_kdf, clock
):
    made = permanent(Room)
    as_user(None)
    for _ in range(10):
        Room.unlock("acme-board", "aaaa-bbbb-cccc")
    clock.advance(minutes=5, seconds=1)

    assert Room.unlock("acme-board", made["passphrase"])["ok"] is True

    row = tables.room.rows[0]
    assert row["failed_unlocks"] == 0
    assert row["locked_until"] is None


def test_after_the_window_a_wrong_guess_starts_a_fresh_count(
    Room, tables, admin, as_user, fast_kdf, clock
):
    permanent(Room)
    as_user(None)
    for _ in range(10):
        Room.unlock("acme-board", "aaaa-bbbb-cccc")
    clock.advance(minutes=6)

    assert Room.unlock("acme-board", "aaaa-bbbb-cccc")["reason"] == "incorrect"

    row = tables.room.rows[0]
    assert row["failed_unlocks"] == 1
    assert row["locked_until"] is None


def test_a_correct_unlock_resets_a_partial_count(
    Room, tables, admin, as_user, fast_kdf, clock
):
    made = permanent(Room)
    as_user(None)
    for _ in range(9):
        Room.unlock("acme-board", "aaaa-bbbb-cccc")

    assert Room.unlock("acme-board", made["passphrase"])["ok"] is True
    assert tables.room.rows[0]["failed_unlocks"] == 0
    # Nine more wrong ones do not lock, because the count restarted.
    for _ in range(9):
        Room.unlock("acme-board", "aaaa-bbbb-cccc")
    assert tables.room.rows[0]["locked_until"] is None


def test_the_lock_is_per_room(Room, tables, admin, as_user, fast_kdf, clock):
    first = permanent(Room, "Room one")
    permanent(Room, "Room two")
    as_user(None)
    for _ in range(10):
        Room.unlock("room-two", "aaaa-bbbb-cccc")

    assert Room.unlock("room-one", first["passphrase"])["ok"] is True


def test_a_timezone_aware_lock_time_is_compared_correctly(
    Room, tables, admin, as_user, fast_kdf, clock
):
    made = permanent(Room)
    as_user(None)
    row = tables.room.rows[0]
    row["failed_unlocks"] = 10
    aware = datetime.timezone(datetime.timedelta(hours=2))
    # 12:03 UTC, written with a +02:00 offset.
    row["locked_until"] = datetime.datetime(2026, 11, 18, 14, 3, tzinfo=aware)

    assert Room.unlock("acme-board", made["passphrase"])["reason"] == "throttled"
    clock.advance(minutes=4)
    assert Room.unlock("acme-board", made["passphrase"])["ok"] is True


def test_the_tenth_miss_locks_and_the_eleventh_is_refused_unhashed(
    Room, tables, admin, as_user, fast_kdf, clock, verifier, monkeypatch
):
    permanent(Room)
    as_user(None)
    hashed = []
    real = verifier.check_passphrase

    def counting(text, record):
        hashed.append(text)
        return real(text, record)

    monkeypatch.setattr(verifier, "check_passphrase", counting)

    reasons = [Room.unlock("acme-board", "aaaa-bbbb-cccc")["reason"] for _ in range(11)]

    assert reasons == ["incorrect"] * 10 + ["throttled"]
    assert len(hashed) == 10
    assert tables.room.rows[0]["failed_unlocks"] == 10


def test_the_lock_ends_exactly_five_minutes_after_the_tenth_miss(
    Room, tables, admin, as_user, fast_kdf, clock
):
    made = permanent(Room)
    as_user(None)
    for _ in range(10):
        Room.unlock("acme-board", "aaaa-bbbb-cccc")

    clock.advance(minutes=4, seconds=59)
    assert Room.unlock("acme-board", made["passphrase"])["reason"] == "throttled"
    clock.advance(seconds=1)
    assert Room.unlock("acme-board", made["passphrase"])["ok"] is True


def test_overlapping_guesses_cannot_exceed_the_limit(
    Room, tables, admin, as_user, fast_kdf, clock, verifier, monkeypatch
):
    """Guesses that overlap while one is still hashing are counted before hashing.

    This is not a real race: the fake tables have no threads. The hash step is
    made to start the next guess before it returns, so eleven guesses are all
    in flight at once. A version that read the count, hashed, then wrote it
    would let all eleven hash. It proves the count is taken before the slow
    step; it does not prove Anvil's transaction isolation, which only a
    running server can.
    """
    permanent(Room)
    as_user(None)
    real = verifier.check_passphrase
    hashed = []
    outcomes = []

    def overlapping(text, record):
        hashed.append(text)
        if len(hashed) < 11:
            outcomes.append(Room.unlock("acme-board", "aaaa-bbbb-cccc")["reason"])
        return real(text, record)

    monkeypatch.setattr(verifier, "check_passphrase", overlapping)

    first = Room.unlock("acme-board", "aaaa-bbbb-cccc")["reason"]

    assert len(hashed) == 10
    assert first == "incorrect"
    assert outcomes.count("incorrect") == 9
    assert outcomes.count("throttled") == 1
    assert tables.room.rows[0]["failed_unlocks"] == 10


def test_attempt_counts_are_written_through_not_saved(load_client_module):
    """Inside a transaction `save()` is itself a transaction, which Anvil refuses
    to nest, so the counts must be written by a write-through `update()`."""
    from fakes import FakeRow

    module = load_client_module("services/model/room")
    row = FakeRow({"failed_unlocks": 0, "locked_until": None})

    module._store_attempts(row, 3, None)

    assert row["failed_unlocks"] == 3
    assert row.saves == 1
    assert row.__dict__.get("write_through") is True


def test_a_write_conflict_is_retried_and_counts_the_guess_once(
    Room, tables, admin, as_user, fast_kdf, clock, load_client_module, monkeypatch
):
    from anvil.tables import TransactionConflict

    module = load_client_module("services/model/room")
    permanent(Room)
    as_user(None)
    real = module._store_attempts
    conflicts = []

    def conflicting_once(row, failed, locked_until):
        real(row, failed, locked_until)
        if not conflicts:
            conflicts.append(1)
            raise TransactionConflict()

    monkeypatch.setattr(module, "_store_attempts", conflicting_once)

    assert Room.unlock("acme-board", "aaaa-bbbb-cccc")["reason"] == "incorrect"
    assert conflicts == [1]
    assert tables.room.rows[0]["failed_unlocks"] == 1


def test_unending_conflicts_refuse_the_guess_without_hashing(
    Room,
    tables,
    admin,
    as_user,
    fast_kdf,
    clock,
    load_client_module,
    verifier,
    monkeypatch,
):
    from anvil.tables import TransactionConflict

    module = load_client_module("services/model/room")
    made = permanent(Room)
    as_user(None)

    def always(row, failed, locked_until):
        raise TransactionConflict()

    def boom(*args, **kwargs):
        raise AssertionError("hashed without a counted attempt")

    monkeypatch.setattr(module, "_store_attempts", always)
    monkeypatch.setattr(verifier, "check_passphrase", boom)

    assert Room.unlock("acme-board", made["passphrase"]) == {
        "ok": False,
        "reason": "throttled",
    }


def test_a_rotation_during_the_hash_does_not_release_the_old_details(
    Room, tables, admin, as_user, fast_kdf, clock, verifier, monkeypatch
):
    made = permanent(Room)
    old_room = tables.room.rows[0]["vdo_room"]
    as_user(None)
    real = verifier.check_passphrase

    def rotating(text, record):
        result = real(text, record)
        as_user(admin_user)
        Room.rotate("acme-board")
        as_user(None)
        return result

    admin_user = admin
    monkeypatch.setattr(verifier, "check_passphrase", rotating)

    result = Room.unlock("acme-board", made["passphrase"])

    assert result == {"ok": False, "reason": "incorrect"}
    assert tables.room.rows[0]["vdo_room"] != old_room


def test_a_damaged_verifier_refuses_every_attempt(
    Room, tables, admin, as_user, fast_kdf
):
    made = permanent(Room)
    as_user(None)
    tables.room.rows[0]["verifier"] = None

    assert Room.unlock("acme-board", made["passphrase"])["reason"] == "incorrect"


def test_permanent_methods_are_registered(Room):
    registered = {
        r.name for r in anvil.server.registrations if r.kind == "server_method"
    }

    assert {"Room.create_permanent", "Room.unlock"} <= registered


# --- room management ---------------------------------
