# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

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
def admin(as_user, make_user):
    user = make_user(email="admin@example.test", is_admin=True)
    as_user(user)
    return user


def _add_room(tables, slug, vdo_room="r" * 20, active=True, title="T"):
    return tables.room.add_row(
        slug=slug,
        vdo_room=vdo_room,
        title=title,
        kind="one-off",
        active=active,
        created_by="admin@example.test",
        created=datetime.datetime(2026, 1, 1),
    )


# --- lookup ---------------------------------------------------------------


def test_lookup_empty_table_returns_none(Room, tables):
    assert Room.lookup("dk2wjd9d") is None


def test_lookup_returns_exactly_what_a_join_needs(Room, tables, admin):
    made = Room.create_one_off(title="Kickoff")
    row = tables.room.rows[0]

    found = Room.lookup(made["slug"])

    assert set(found) == {"vdo_room", "title", "origin", "profile", "salt", "kind"}
    assert found["kind"] == "one-off"
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


@pytest.mark.parametrize("slug", ["", "../x", "admin", None, "a b"])
def test_lookup_of_a_malformed_or_reserved_slug_reads_no_table(Room, tables, slug):
    assert Room.lookup(slug) is None
    assert tables.room.reads == 0


def test_lookup_normalises_case_and_whitespace(Room, tables):
    _add_room(tables, "dk2wjd9d", vdo_room="v" * 20)

    assert Room.lookup("  DK2WJD9D ")["vdo_room"] == "v" * 20


# --- create_one_off -------------------------------------------------------


def test_create_one_off_stores_the_row_and_returns_slug_and_title(
    Room, tables, admin, slugs
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
    assert row["created_by"] == "admin@example.test"
    assert isinstance(row["created"], datetime.datetime)


def test_create_one_off_title_defaults_to_empty(Room, tables, admin):
    assert Room.create_one_off()["title"] == ""


def test_create_one_off_refuses_signed_out(Room, tables, as_user):
    as_user(None)

    with pytest.raises(anvil.server.PermissionDenied):
        Room.create_one_off(title="x")

    assert tables.room.rows == []
    assert tables.room.reads == 0


def test_create_one_off_refuses_non_admin(Room, tables, as_user, make_user):
    as_user(make_user(is_admin=False))

    with pytest.raises(anvil.server.PermissionDenied):
        Room.create_one_off(title="x")

    assert tables.room.rows == []
    assert tables.room.reads == 0


def _draws(monkeypatch, slugs, values):
    queue = list(values)
    monkeypatch.setattr(slugs, "new_one_off_slug", lambda: queue.pop(0))


def test_create_one_off_redraws_a_taken_slug(Room, tables, admin, slugs, monkeypatch):
    _add_room(tables, "taken234")
    _draws(monkeypatch, slugs, ["taken234", "fresh345"])

    assert Room.create_one_off(title="x")["slug"] == "fresh345"
    assert len(tables.room.rows) == 2


def test_create_one_off_redraws_a_reserved_slug(
    Room, tables, admin, slugs, monkeypatch
):
    _draws(monkeypatch, slugs, ["admin", "fresh345"])

    assert Room.create_one_off(title="x")["slug"] == "fresh345"


def test_create_one_off_gives_up_after_ten_taken_slugs(
    Room, tables, admin, slugs, monkeypatch
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


# --- permanent rooms (JOIN-02, JOIN-03, D-9) ------------------------------

START = datetime.datetime(2026, 11, 18, 12, 0, 0)
PERMANENT_COLUMNS = (
    "slug",
    "vdo_room",
    "title",
    "kind",
    "active",
    "created_by",
    "created",
    "verifier",
    "verifier_salt",
    "kdf_iterations",
    "vdo_password",
    "failed_unlocks",
    "locked_until",
    "updated",
)


@pytest.fixture
def verifier():
    import importlib

    return importlib.import_module("iris.verifier")


@pytest.fixture
def fast_kdf(verifier, monkeypatch):
    """Cheap iterations, so a test of the logic does not pay for 600000."""
    monkeypatch.setattr(verifier, "ITERATIONS", 1000)


@pytest.fixture
def clock(Room, load_client_module, monkeypatch):
    """A frozen clock: the model reads `clock.now`, and `advance()` moves it."""
    module = load_client_module("services/model/room")

    class Clock:
        now = START

        def advance(self, **delta):
            self.now = self.now + datetime.timedelta(**delta)

    frozen = Clock()
    monkeypatch.setattr(module, "_now", lambda: frozen.now)
    return frozen


def _permanent(Room, slug="Acme Board", title="Acme quarterly"):
    return Room.create_permanent(slug, title=title)


def test_create_permanent_returns_slug_title_and_one_passphrase(
    Room, tables, admin, fast_kdf
):
    result = _permanent(Room)

    assert set(result) == {"slug", "title", "passphrase"}
    assert result["slug"] == "acme-board"
    assert result["title"] == "Acme quarterly"
    groups = result["passphrase"].split("-")
    assert [len(g) for g in groups] == [4, 4, 4]


def test_create_permanent_stores_the_row_and_saves_it(Room, tables, admin, verifier):
    result = _permanent(Room)

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
    result = _permanent(Room)
    row = tables.room.rows[0]
    normalised = result["passphrase"].replace("-", "")

    for column, value in row._values.items():
        text = str(value)
        assert result["passphrase"] not in text, column
        assert normalised not in text, column


def test_create_permanent_draws_a_new_room_password_and_passphrase_each_time(
    Room, tables, admin, fast_kdf
):
    first = _permanent(Room, "Room one")
    second = _permanent(Room, "Room two")

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
    _permanent(Room)

    assert Room.lookup("acme-board") == {"kind": "permanent", "locked": True}


def test_lookup_of_an_inactive_permanent_room_is_none(Room, tables, admin, fast_kdf):
    _permanent(Room)
    tables.room.rows[0]["active"] = False

    assert Room.lookup("acme-board") is None


def test_lookup_of_a_permanent_room_reads_no_setting(Room, tables, admin, fast_kdf):
    _permanent(Room)
    tables.setting.reads = 0

    Room.lookup("acme-board")

    assert tables.setting.reads == 0


def _signed_out(as_user):
    as_user(None)


def test_unlock_with_the_right_passphrase_releases_the_join_info(
    Room, tables, admin, as_user, fast_kdf
):
    made = _permanent(Room)
    row = tables.room.rows[0]
    tables.setting.add_row(key="vdo_origin", value="https://meet.example.test")
    tables.setting.add_row(key="vdo_salt", value="pepper")
    _signed_out(as_user)

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
    made = _permanent(Room)
    _signed_out(as_user)

    assert Room.unlock("acme-board", retype(made["passphrase"]))["ok"] is True


def test_unlock_a_wrong_passphrase_is_incorrect_and_counts(
    Room, tables, admin, as_user, fast_kdf
):
    _permanent(Room)
    _signed_out(as_user)

    result = Room.unlock("acme-board", "aaaa-bbbb-cccc")

    assert result == {"ok": False, "reason": "incorrect"}
    assert tables.room.rows[0]["failed_unlocks"] == 1
    assert tables.room.rows[0].saves >= 2


@pytest.mark.parametrize("slug", ["no-such-room", "kickoff1", "x", "../etc", None, 5])
def test_unlock_of_an_unknown_or_one_off_slug_is_missing(
    Room, tables, admin, as_user, fast_kdf, slug
):
    tables.room.add_row(slug="kickoff1", kind="one-off", active=True, vdo_room="v" * 20)
    _signed_out(as_user)

    assert Room.unlock(slug, "aaaa-bbbb-cccc") == {"ok": False, "reason": "missing"}


def test_unlock_of_an_inactive_room_is_missing(Room, tables, admin, as_user, fast_kdf):
    made = _permanent(Room)
    tables.room.rows[0]["active"] = False
    _signed_out(as_user)

    assert Room.unlock("acme-board", made["passphrase"]) == {
        "ok": False,
        "reason": "missing",
    }


@pytest.mark.parametrize("text", ["", "   ", "- - -", None, 5, ["a"]])
def test_unlock_with_nothing_typed_is_empty_and_hashes_nothing(
    Room, tables, admin, as_user, fast_kdf, verifier, monkeypatch, text
):
    _permanent(Room)
    _signed_out(as_user)

    def boom(*args, **kwargs):
        raise AssertionError("hashed an empty input")

    monkeypatch.setattr(verifier, "check_passphrase", boom)

    assert Room.unlock("acme-board", text) == {"ok": False, "reason": "empty"}
    assert tables.room.rows[0]["failed_unlocks"] == 0


def test_unlock_of_an_oversized_input_is_incorrect_and_hashes_nothing(
    Room, tables, admin, as_user, fast_kdf, verifier, monkeypatch
):
    _permanent(Room)
    _signed_out(as_user)
    huge = "secret-" * 100

    def boom(*args, **kwargs):
        raise AssertionError("hashed an oversized input")

    monkeypatch.setattr(verifier, "check_passphrase", boom)

    assert Room.unlock("acme-board", huge) == {"ok": False, "reason": "incorrect"}


def test_nothing_the_unlock_raises_or_returns_carries_the_input(
    Room, tables, admin, as_user, fast_kdf
):
    _permanent(Room)
    _signed_out(as_user)
    typed = "zzzz-yyyy-xxxx"

    result = Room.unlock("acme-board", typed)

    assert typed not in repr(result)
    assert "zzzzyyyyxxxx" not in repr(result)


def test_ten_wrong_in_a_row_lock_the_room_for_five_minutes(
    Room, tables, admin, as_user, fast_kdf, clock
):
    made = _permanent(Room)
    _signed_out(as_user)

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
    _permanent(Room)
    _signed_out(as_user)
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
    made = _permanent(Room)
    _signed_out(as_user)
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
    _permanent(Room)
    _signed_out(as_user)
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
    made = _permanent(Room)
    _signed_out(as_user)
    for _ in range(9):
        Room.unlock("acme-board", "aaaa-bbbb-cccc")

    assert Room.unlock("acme-board", made["passphrase"])["ok"] is True
    assert tables.room.rows[0]["failed_unlocks"] == 0
    # Nine more wrong ones do not lock, because the count restarted.
    for _ in range(9):
        Room.unlock("acme-board", "aaaa-bbbb-cccc")
    assert tables.room.rows[0]["locked_until"] is None


def test_the_lock_is_per_room(Room, tables, admin, as_user, fast_kdf, clock):
    first = _permanent(Room, "Room one")
    _permanent(Room, "Room two")
    _signed_out(as_user)
    for _ in range(10):
        Room.unlock("room-two", "aaaa-bbbb-cccc")

    assert Room.unlock("room-one", first["passphrase"])["ok"] is True


def test_a_timezone_aware_lock_time_is_compared_correctly(
    Room, tables, admin, as_user, fast_kdf, clock
):
    made = _permanent(Room)
    _signed_out(as_user)
    row = tables.room.rows[0]
    row["failed_unlocks"] = 10
    aware = datetime.timezone(datetime.timedelta(hours=2))
    # 12:03 UTC, written with a +02:00 offset.
    row["locked_until"] = datetime.datetime(2026, 11, 18, 14, 3, tzinfo=aware)

    assert Room.unlock("acme-board", made["passphrase"])["reason"] == "throttled"
    clock.advance(minutes=4)
    assert Room.unlock("acme-board", made["passphrase"])["ok"] is True


def test_a_damaged_verifier_refuses_every_attempt(
    Room, tables, admin, as_user, fast_kdf
):
    made = _permanent(Room)
    _signed_out(as_user)
    tables.room.rows[0]["verifier"] = None

    assert Room.unlock("acme-board", made["passphrase"])["reason"] == "incorrect"


def test_permanent_methods_are_registered(Room):
    registered = {
        r.name for r in anvil.server.registrations if r.kind == "server_method"
    }

    assert {"Room.create_permanent", "Room.unlock"} <= registered


# --- room management (ADMIN-04, D-7, D-8) ---------------------------------

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
    _permanent(Room)
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
    _permanent(Room)
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
    _permanent(Room)
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
    _permanent(Room)

    assert Room.update_title("acme-board", "")["title"] == ""


def test_update_title_finds_the_room_whatever_the_case(Room, tables, admin, fast_kdf):
    _permanent(Room)

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
    _permanent(Room)
    args = (slug, "x") if name == "update_title" else (slug,)

    with pytest.raises(ValueError) as refused:
        getattr(Room, name)(*args)

    assert str(refused.value) == "No such room."
    assert len(tables.room.rows) == 1


@pytest.mark.parametrize("title", [5, ["a"], b"x"])
def test_update_title_refuses_a_title_that_is_not_text(
    Room, tables, admin, fast_kdf, title
):
    _permanent(Room)

    with pytest.raises(ValueError, match="Title must be text"):
        Room.update_title("acme-board", title)

    assert tables.room.rows[0]["title"] == "Acme quarterly"


def test_remove_deletes_the_row_and_the_link_is_dead(Room, tables, admin, fast_kdf):
    made = Room.create_one_off(title="Kickoff")
    _permanent(Room)

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
    first = _permanent(Room)
    Room.remove("acme-board")

    second = _permanent(Room)

    assert second["slug"] == "acme-board"
    assert second["passphrase"] != first["passphrase"]
    assert len(tables.room.rows) == 1


def test_remove_twice_is_no_such_room(Room, tables, admin, fast_kdf):
    _permanent(Room)
    Room.remove("acme-board")

    with pytest.raises(ValueError, match="No such room."):
        Room.remove("acme-board")


def test_remove_leaves_other_rooms_alone(Room, tables, admin, fast_kdf):
    _permanent(Room, "Room one")
    _permanent(Room, "Room two")

    Room.remove("room-one")

    assert [r["slug"] for r in tables.room.rows] == ["room-two"]


def test_rotate_returns_the_slug_and_one_new_passphrase_only(
    Room, tables, admin, fast_kdf
):
    made = _permanent(Room)

    result = Room.rotate("acme-board")

    assert set(result) == {"slug", "passphrase"}
    assert result["slug"] == "acme-board"
    assert [len(g) for g in result["passphrase"].split("-")] == [4, 4, 4]
    assert result["passphrase"] != made["passphrase"]


def test_rotate_old_passphrase_fails_and_the_new_one_unlocks(
    Room, tables, admin, as_user, fast_kdf
):
    made = _permanent(Room)
    result = Room.rotate("acme-board")
    _signed_out(as_user)

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
    made = _permanent(Room)
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
    _signed_out(as_user)
    found = Room.unlock("acme-board", result["passphrase"])["found"]
    assert found["vdo_room"] == row["vdo_room"]
    assert found["password"] == row["vdo_password"]
    assert made["passphrase"] != result["passphrase"]


def test_rotate_clears_a_lock_and_the_failed_count(
    Room, tables, admin, as_user, fast_kdf, clock
):
    _permanent(Room)
    row = tables.room.rows[0]
    row["failed_unlocks"] = 10
    row["locked_until"] = clock.now + datetime.timedelta(minutes=5)

    result = Room.rotate("acme-board")

    assert row["failed_unlocks"] == 0
    assert row["locked_until"] is None
    assert row["updated"] == clock.now
    _signed_out(as_user)
    assert Room.unlock("acme-board", result["passphrase"])["ok"] is True


def test_rotate_stores_no_trace_of_the_passphrase(Room, tables, admin, fast_kdf):
    _permanent(Room)

    result = Room.rotate("acme-board")
    row = tables.room.rows[0]

    for column, value in row._values.items():
        assert result["passphrase"] not in str(value), column
        assert result["passphrase"].replace("-", "") not in str(value), column


def test_rotate_keeps_the_slug_title_and_kind(Room, tables, admin, fast_kdf):
    _permanent(Room)

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
    _permanent(Room)
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
    _permanent(Room)
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
