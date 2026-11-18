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


@pytest.fixture
def admin(as_user, make_user):
    user = make_user(email="admin@example.test", is_staff=True)
    as_user(user)
    return user


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
    as_user(make_user(email="viewer@example.test", is_staff=False))

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
