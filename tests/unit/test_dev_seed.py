# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""The join room that tools/dev_seed.py puts on the local stack."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
E2E_JOIN = ROOT / "tests" / "e2e" / "test_join.py"
E2E_PERMANENT = ROOT / "tests" / "e2e" / "test_permanent_room.py"


@pytest.fixture
def seed(load_tool, monkeypatch):
    # dev_seed imports its siblings create_admin and stack_url by bare name.
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    module = load_tool("dev_seed")
    yield module
    for name in ("create_admin", "stack_url"):
        sys.modules.pop(name, None)


def _setting(tables, key):
    row = tables.setting.get(key=key)
    return None if row is None else row["value"]


def test_the_first_run_creates_the_room_and_the_two_settings(seed, tables):
    result = seed.seed_join_room(tables)

    room = tables.room.get(slug=seed.DEV_ROOM_SLUG)
    assert result == "created"
    assert room["vdo_room"] == seed.DEV_ROOM_VDO
    assert room["title"] == seed.DEV_ROOM_TITLE
    assert room["kind"] == "one-off"
    assert room["active"] is True
    assert room["created_by"] == seed.create_admin.DEV_ADMIN_EMAIL
    assert room["created"] is not None
    assert _setting(tables, "vdo_origin") == seed.DEV_VDO_ORIGIN
    assert _setting(tables, "vdo_profile") == seed.DEV_VDO_PROFILE


def test_a_second_run_changes_nothing_and_adds_no_rows(seed, tables):
    seed.seed_join_room(tables)
    counts = (len(tables.room.rows), len(tables.setting.rows))

    result = seed.seed_join_room(tables)

    assert result == "updated"
    assert (len(tables.room.rows), len(tables.setting.rows)) == counts


def test_a_drifted_room_and_settings_are_put_back(seed, tables):
    seed.seed_join_room(tables)
    room = tables.room.get(slug=seed.DEV_ROOM_SLUG)
    room["vdo_room"] = "somethingelse"
    room["active"] = False
    tables.setting.get(key="vdo_origin")["value"] = "https://other.example"

    seed.seed_join_room(tables)

    assert room["vdo_room"] == seed.DEV_ROOM_VDO
    assert room["active"] is True
    assert _setting(tables, "vdo_origin") == seed.DEV_VDO_ORIGIN


def test_no_salt_setting_is_written(seed, tables):
    seed.seed_join_room(tables)

    assert tables.setting.get(key="vdo_salt") is None


def test_the_constants_make_a_valid_join_address(seed, load_client_module):
    vdo = load_client_module("services/vdo")

    assert vdo.normalise_origin(seed.DEV_VDO_ORIGIN) == seed.DEV_VDO_ORIGIN
    assert vdo.validate_profile(seed.DEV_VDO_PROFILE) == seed.DEV_VDO_PROFILE
    assert re.fullmatch(r"[a-z0-9]{20}", seed.DEV_ROOM_VDO)
    assert seed.DEV_ROOM_VDO != seed.DEV_ROOM_SLUG


@pytest.mark.parametrize(
    ("constant", "name"),
    [
        ("DEV_ROOM_SLUG", "SEEDED_SLUG"),
        ("DEV_ROOM_TITLE", "SEEDED_TITLE"),
        ("DEV_ROOM_VDO", "SEEDED_VDO_ROOM"),
        ("DEV_VDO_ORIGIN", "SEEDED_ORIGIN"),
    ],
)
def test_the_e2e_copy_of_each_constant_matches(seed, constant, name):
    text = E2E_JOIN.read_text(encoding="utf-8")
    found = re.search(rf'^{name} = "([^"]*)"$', text, re.MULTILINE)

    assert found is not None, f"{name} is not in tests/e2e/test_join.py"
    assert found.group(1) == getattr(seed, constant)


# The seeded permanent room (JOIN-02, JOIN-03, JOIN-05).


def test_the_first_run_creates_the_permanent_room(seed, tables):
    result = seed.seed_permanent_room(tables)

    room = tables.room.get(slug=seed.SEEDED_PERMANENT_SLUG)
    assert result == "created"
    assert room["kind"] == "permanent"
    assert room["active"] is True
    assert room["title"] == seed.SEEDED_PERMANENT_TITLE
    assert room["vdo_room"] == seed.SEEDED_PERMANENT_VDO_ROOM
    assert room["vdo_password"] == seed.SEEDED_PERMANENT_VDO_PASSWORD
    assert room["failed_unlocks"] == 0
    assert room["locked_until"] is None
    assert room["created_by"] == seed.create_admin.DEV_ADMIN_EMAIL


def test_the_seeded_verifier_accepts_only_the_seeded_passphrase(
    seed, tables, load_server_module, load_client_module
):
    verifier = load_server_module("verifier")
    passphrase = load_client_module("services/passphrase")
    seed.seed_permanent_room(tables)
    room = tables.room.get(slug=seed.SEEDED_PERMANENT_SLUG)
    record = {
        "verifier": room["verifier"],
        "verifier_salt": room["verifier_salt"],
        "kdf_iterations": room["kdf_iterations"],
    }

    right = passphrase.normalise(seed.DEV_ROOM_PASSPHRASE)
    wrong = passphrase.normalise("test-room-wrong")

    assert verifier.check_passphrase(right, record) is True
    assert verifier.check_passphrase(wrong, record) is False
    # A client types it in any case and spacing, and still matches.
    assert passphrase.normalise(" TEST room-PASS ") == right


def test_the_seed_does_not_store_the_passphrase_or_its_normal_form(seed, tables):
    seed.seed_permanent_room(tables)
    room = tables.room.get(slug=seed.SEEDED_PERMANENT_SLUG)

    stored = " ".join(str(value) for value in room._values.values())

    assert seed.DEV_ROOM_PASSPHRASE not in stored
    assert "testroompass" not in stored


def test_a_second_run_adds_no_row_and_clears_a_throttle(seed, tables):
    seed.seed_permanent_room(tables)
    count = len(tables.room.rows)
    room = tables.room.get(slug=seed.SEEDED_PERMANENT_SLUG)
    room["failed_unlocks"] = 10
    room["locked_until"] = seed.datetime.datetime.now()
    room["vdo_room"] = "somethingelse"

    result = seed.seed_permanent_room(tables)

    assert result == "updated"
    assert len(tables.room.rows) == count
    assert room["failed_unlocks"] == 0
    assert room["locked_until"] is None
    assert room["vdo_room"] == seed.SEEDED_PERMANENT_VDO_ROOM


def test_the_permanent_constants_are_valid_and_obviously_made_up(
    seed, load_client_module
):
    slugs = load_client_module("services/slugs")
    vdo = load_client_module("services/vdo")

    assert slugs.clean_room_slug(seed.SEEDED_PERMANENT_SLUG) == (
        seed.SEEDED_PERMANENT_SLUG
    )
    assert re.fullmatch(r"[a-z0-9]{20}", seed.SEEDED_PERMANENT_VDO_ROOM)
    assert re.fullmatch(r"[0-9a-f]{24}", seed.SEEDED_PERMANENT_VDO_PASSWORD)
    assert seed.SEEDED_PERMANENT_VDO_ROOM != seed.DEV_ROOM_VDO
    # The seeded room builds a valid fragment address.
    url = vdo.build_join_url(
        seed.DEV_VDO_ORIGIN,
        seed.SEEDED_PERMANENT_VDO_ROOM,
        seed.DEV_VDO_PROFILE,
        "Ann",
        password=seed.SEEDED_PERMANENT_VDO_PASSWORD,
        in_fragment=True,
    )
    assert "password=" + seed.SEEDED_PERMANENT_VDO_PASSWORD in url.split("#")[1]


@pytest.mark.parametrize(
    ("constant", "name"),
    [
        ("SEEDED_PERMANENT_SLUG", "SEEDED_PERMANENT_SLUG"),
        ("SEEDED_PERMANENT_TITLE", "SEEDED_PERMANENT_TITLE"),
        ("SEEDED_PERMANENT_VDO_ROOM", "SEEDED_PERMANENT_VDO_ROOM"),
        ("SEEDED_PERMANENT_VDO_PASSWORD", "SEEDED_PERMANENT_VDO_PASSWORD"),
        ("DEV_ROOM_PASSPHRASE", "SEEDED_PASSPHRASE"),
    ],
)
def test_the_e2e_copy_of_each_permanent_constant_matches(seed, constant, name):
    text = E2E_PERMANENT.read_text(encoding="utf-8")
    found = re.search(rf'^{name} = "([^"]*)"$', text, re.MULTILINE)

    assert found is not None, f"{name} is not in tests/e2e/test_permanent_room.py"
    assert found.group(1) == getattr(seed, constant)
