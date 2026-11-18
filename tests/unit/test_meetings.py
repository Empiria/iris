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
def admin(as_user, make_user):
    user = make_user(email="admin@example.test", is_admin=True)
    as_user(user)
    return user


# --- registration ---------------------------------------------------------


def test_create_one_off_link_requires_admin(meetings, load_client_module):
    permissions = load_client_module("services/permissions")
    found = [
        r
        for r in anvil.server.registrations
        if r.kind == "callable" and r.name == "create_one_off_link"
    ]

    assert len(found) == 1
    assert found[0].kwargs.get("require_user") is permissions.is_admin


# --- create_one_off_link --------------------------------------------------


def test_returns_slug_and_title_and_stores_one_row(meetings, tables, admin, slugs):
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
    assert row["created_by"] == "admin@example.test"
    assert len(row["vdo_room"]) == 20
    assert row["vdo_room"] != result["slug"]


def test_two_calls_give_two_links_and_two_rooms(meetings, tables, admin):
    first = meetings.create_one_off_link("")
    second = meetings.create_one_off_link("")

    assert first["slug"] != second["slug"]
    assert len(tables.room.rows) == 2
    assert tables.room.rows[0]["vdo_room"] != tables.room.rows[1]["vdo_room"]


def test_the_reply_and_the_link_never_contain_the_vdo_room(
    meetings, tables, admin, links
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
def test_non_admin_is_refused_and_writes_nothing(
    meetings, tables, as_user, make_user, flag
):
    as_user(make_user(is_admin=flag))

    with pytest.raises(anvil.server.PermissionDenied):
        meetings.create_one_off_link("x")

    assert tables.room.rows == []
    assert tables.room.reads == 0


def test_the_title_is_cleaned_before_it_is_stored(meetings, tables, admin):
    result = meetings.create_one_off_link("  Kick\toff\n ")

    assert result["title"] == "Kick off"
    assert tables.room.rows[0]["title"] == "Kick off"


def test_a_blank_title_is_stored_as_empty(meetings, tables, admin):
    result = meetings.create_one_off_link("   ")

    assert result["title"] == ""
    assert tables.room.rows[0]["title"] == ""


def test_the_title_defaults_to_empty(meetings, tables, admin):
    assert meetings.create_one_off_link()["title"] == ""


# --- ADMIN-07, pinned from the creation side ------------------------------


def test_lookup_finds_the_created_room_and_nothing_else(
    meetings, Room, tables, admin, slugs
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


# --- create_permanent_room ------------------------------------------------


@pytest.fixture
def fast_kdf(load_client_module, meetings, monkeypatch):
    import importlib

    monkeypatch.setattr(importlib.import_module("iris.verifier"), "ITERATIONS", 1000)


def _callable(name):
    found = [
        r for r in anvil.server.registrations if r.kind == "callable" and r.name == name
    ]
    assert len(found) == 1
    return found[0]


def test_create_permanent_room_requires_an_admin(meetings, load_client_module):
    permissions = load_client_module("services/permissions")

    registration = _callable("create_permanent_room")

    assert registration.kwargs.get("require_user") is permissions.is_admin


def test_create_permanent_room_returns_slug_title_and_passphrase(
    meetings, tables, admin, fast_kdf
):
    result = meetings.create_permanent_room("Acme Board", "Acme quarterly")

    assert set(result) == {"slug", "title", "passphrase"}
    assert result["slug"] == "acme-board"
    assert result["title"] == "Acme quarterly"
    assert len(result["passphrase"]) == 14
    row = tables.room.rows[0]
    assert row["kind"] == "permanent"
    assert row["created_by"] == "admin@example.test"


def test_create_permanent_room_cleans_the_title(meetings, tables, admin, fast_kdf):
    result = meetings.create_permanent_room("Acme Board", "  a\nb  ")

    assert result["title"] == "a b"
    assert tables.room.rows[0]["title"] == "a b"


def test_create_permanent_room_title_defaults_to_empty(
    meetings, tables, admin, fast_kdf
):
    assert meetings.create_permanent_room("Acme Board")["title"] == ""


def test_create_permanent_room_the_reply_holds_no_room_secrets(
    meetings, tables, admin, fast_kdf
):
    result = meetings.create_permanent_room("Acme Board", "x")
    row = tables.room.rows[0]

    assert row["vdo_room"] not in repr(result)
    assert row["vdo_password"] not in repr(result)
    assert row["verifier"] not in repr(result)


def test_create_permanent_room_passes_a_slug_message_on(
    meetings, tables, admin, fast_kdf
):
    with pytest.raises(ValueError, match="Use at least 3 characters"):
        meetings.create_permanent_room("ab")


def test_create_permanent_room_refuses_a_taken_name(meetings, tables, admin, fast_kdf):
    meetings.create_permanent_room("Acme Board")

    with pytest.raises(ValueError, match="That name is taken."):
        meetings.create_permanent_room("acme-board")

    assert len(tables.room.rows) == 1


def test_create_permanent_room_refuses_a_one_off_slug(
    meetings, tables, admin, fast_kdf
):
    made = meetings.create_one_off_link("")

    with pytest.raises(ValueError, match="That name is taken."):
        meetings.create_permanent_room(made["slug"])


def test_create_permanent_room_refuses_non_text(meetings, tables, admin, fast_kdf):
    with pytest.raises(ValueError):
        meetings.create_permanent_room(None)

    assert tables.room.rows == []


def test_create_permanent_room_the_model_refuses_a_non_admin_caller(
    meetings, tables, as_user, make_user, fast_kdf
):
    as_user(make_user(email="viewer@example.test", is_admin=False))

    with pytest.raises(anvil.server.PermissionDenied):
        meetings.create_permanent_room("Acme Board")

    assert tables.room.rows == []


# --- unlock_room (JOIN-02, JOIN-03, D-9) ----------------------------------


def test_unlock_room_is_a_plain_public_callable(meetings):
    assert "require_user" not in _callable("unlock_room").kwargs


def test_unlock_room_right_then_wrong_for_an_anonymous_caller(
    meetings, tables, admin, as_user, fast_kdf
):
    made = meetings.create_permanent_room("Acme Board", "Acme quarterly")
    row = tables.room.rows[0]
    as_user(None)

    good = meetings.unlock_room("acme-board", made["passphrase"].upper())
    bad = meetings.unlock_room("acme-board", "aaaa-bbbb-cccc")

    assert good["ok"] is True
    assert good["found"]["vdo_room"] == row["vdo_room"]
    assert good["found"]["password"] == row["vdo_password"]
    assert good["found"]["title"] == "Acme quarterly"
    assert bad == {"ok": False, "reason": "incorrect"}


def test_unlock_room_bad_input_types_are_plain_refusals(
    meetings, tables, admin, as_user, fast_kdf
):
    meetings.create_permanent_room("Acme Board")
    as_user(None)

    assert meetings.unlock_room(None, "x") == {"ok": False, "reason": "missing"}
    assert meetings.unlock_room(5, "x") == {"ok": False, "reason": "missing"}
    assert meetings.unlock_room("acme-board", None) == {"ok": False, "reason": "empty"}
    assert meetings.unlock_room("acme-board", 12) == {"ok": False, "reason": "empty"}


def test_lookup_room_of_a_permanent_slug_is_locked_for_everyone(
    meetings, tables, admin, as_user, fast_kdf
):
    meetings.create_permanent_room("Acme Board", "Secret client")

    assert meetings.lookup_room("acme-board") == {"kind": "permanent", "locked": True}
    as_user(None)
    assert meetings.lookup_room("ACME-BOARD") == {"kind": "permanent", "locked": True}


# --- room management callables (ADMIN-04, D-7, D-8) -----------------------

MANAGEMENT_CALLABLES = ("list_rooms", "update_room", "delete_room", "rotate_passphrase")


def _manage(meetings, name):
    args = {
        "list_rooms": (),
        "update_room": ("acme-board", "New title"),
        "delete_room": ("acme-board",),
        "rotate_passphrase": ("acme-board",),
    }[name]
    return getattr(meetings, name)(*args)


@pytest.mark.parametrize("name", MANAGEMENT_CALLABLES)
def test_management_callables_require_an_admin(meetings, load_client_module, name):
    permissions = load_client_module("services/permissions")

    assert _callable(name).kwargs.get("require_user") is permissions.is_admin


def test_list_rooms_returns_plain_summaries_without_secrets(
    meetings, tables, admin, fast_kdf
):
    meetings.create_permanent_room("Acme Board", "Acme quarterly")
    meetings.create_one_off_link("Kickoff")

    rooms = meetings.list_rooms()

    assert len(rooms) == 2
    assert all(set(r) == {"slug", "title", "kind", "created"} for r in rooms)
    text = repr(rooms)
    for row in tables.room.rows:
        for column in ("vdo_room", "vdo_password", "verifier", "verifier_salt"):
            if row.get(column):
                assert str(row.get(column)) not in text


def test_update_room_cleans_the_title(meetings, tables, admin, fast_kdf):
    meetings.create_permanent_room("Acme Board", "Acme quarterly")

    result = meetings.update_room("Acme-Board", "  a\nb  ")

    assert result["title"] == "a b"
    assert tables.room.rows[0]["title"] == "a b"
    assert tables.room.rows[0]["slug"] == "acme-board"


def test_update_room_may_blank_the_title(meetings, tables, admin, fast_kdf):
    meetings.create_permanent_room("Acme Board", "Acme quarterly")

    assert meetings.update_room("acme-board", "   ")["title"] == ""


def test_update_room_refuses_a_title_that_is_not_text(
    meetings, tables, admin, fast_kdf
):
    meetings.create_permanent_room("Acme Board", "Acme quarterly")

    with pytest.raises(ValueError, match="Title must be text"):
        meetings.update_room("acme-board", 5)

    assert tables.room.rows[0]["title"] == "Acme quarterly"


@pytest.mark.parametrize("slug", [None, 5, ["a"], {}])
@pytest.mark.parametrize("name", ["update_room", "delete_room", "rotate_passphrase"])
def test_a_slug_that_is_not_text_is_no_such_room(
    meetings, tables, admin, fast_kdf, name, slug
):
    meetings.create_permanent_room("Acme Board")
    args = (slug, "x") if name == "update_room" else (slug,)

    with pytest.raises(ValueError, match="No such room."):
        getattr(meetings, name)(*args)

    assert len(tables.room.rows) == 1


@pytest.mark.parametrize("name", ["update_room", "delete_room", "rotate_passphrase"])
def test_an_unknown_slug_is_no_such_room(meetings, tables, admin, fast_kdf, name):
    args = ("nothing-here", "x") if name == "update_room" else ("nothing-here",)

    with pytest.raises(ValueError, match="No such room."):
        getattr(meetings, name)(*args)


def test_delete_room_removes_it_and_lookup_is_none(meetings, tables, admin, fast_kdf):
    meetings.create_permanent_room("Acme Board")
    made = meetings.create_one_off_link("Kickoff")

    assert meetings.delete_room("acme-board") == {"slug": "acme-board"}

    assert meetings.lookup_room("acme-board") is None
    assert [r["slug"] for r in tables.room.rows] == [made["slug"]]


def test_delete_room_works_on_a_one_off_and_frees_nothing_else(meetings, tables, admin):
    made = meetings.create_one_off_link("Kickoff")

    meetings.delete_room(made["slug"])

    assert meetings.lookup_room(made["slug"]) is None
    assert tables.room.rows == []


def test_a_deleted_name_can_be_made_again(meetings, tables, admin, fast_kdf):
    meetings.create_permanent_room("Acme Board")
    meetings.delete_room("acme-board")

    assert meetings.create_permanent_room("Acme Board")["slug"] == "acme-board"


def test_rotate_passphrase_replaces_the_passphrase(
    meetings, tables, admin, as_user, fast_kdf
):
    old = meetings.create_permanent_room("Acme Board")["passphrase"]

    result = meetings.rotate_passphrase("acme-board")

    assert set(result) == {"slug", "passphrase"}
    assert result["passphrase"] != old
    as_user(None)
    assert meetings.unlock_room("acme-board", old) == {
        "ok": False,
        "reason": "incorrect",
    }
    assert meetings.unlock_room("acme-board", result["passphrase"])["ok"] is True


def test_rotate_passphrase_holds_no_room_secrets(meetings, tables, admin, fast_kdf):
    meetings.create_permanent_room("Acme Board")

    result = meetings.rotate_passphrase("acme-board")
    row = tables.room.rows[0]

    for column in ("vdo_room", "vdo_password", "verifier"):
        assert row[column] not in repr(result)


def test_rotate_passphrase_of_a_one_off_is_refused(meetings, tables, admin):
    made = meetings.create_one_off_link("Kickoff")

    with pytest.raises(ValueError, match="Only permanent rooms have a passphrase."):
        meetings.rotate_passphrase(made["slug"])


@pytest.mark.parametrize("name", MANAGEMENT_CALLABLES)
def test_management_callables_refuse_signed_out_and_touch_nothing(
    meetings, tables, admin, fast_kdf, as_user, name
):
    meetings.create_permanent_room("Acme Board", "Acme quarterly")
    before = [dict(r._values) for r in tables.room.rows]
    reads = tables.room.reads
    as_user(None)

    with pytest.raises(anvil.server.PermissionDenied):
        _manage(meetings, name)

    assert [dict(r._values) for r in tables.room.rows] == before
    assert tables.room.reads == reads


@pytest.mark.parametrize("name", MANAGEMENT_CALLABLES)
def test_management_callables_refuse_non_admin_and_touch_nothing(
    meetings, tables, admin, fast_kdf, as_user, make_user, name
):
    meetings.create_permanent_room("Acme Board", "Acme quarterly")
    before = [dict(r._values) for r in tables.room.rows]
    reads = tables.room.reads
    as_user(make_user(email="viewer@example.test", is_admin=False))

    with pytest.raises(anvil.server.PermissionDenied):
        _manage(meetings, name)

    assert [dict(r._values) for r in tables.room.rows] == before
    assert tables.room.reads == reads
