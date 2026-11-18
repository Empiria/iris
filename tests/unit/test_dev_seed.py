"""The join room that tools/dev_seed.py puts on the local stack."""

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
E2E_JOIN = ROOT / "tests" / "e2e" / "test_join.py"


@pytest.fixture
def seed(load_tool, monkeypatch):
    # dev_seed imports its siblings create_staff and stack_url by bare name.
    monkeypatch.syspath_prepend(str(ROOT / "tools"))
    module = load_tool("dev_seed")
    yield module
    for name in ("create_staff", "stack_url"):
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
    assert room["created_by"] == seed.create_staff.DEV_STAFF_EMAIL
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
