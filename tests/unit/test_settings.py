# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import anvil.server
import pytest

SCREEN_SHARE = "ssq=-1&sharperscreen&rbr=50000&trb=50000&crb&codec=av1,vp9,vp8,h264&q=0"


@pytest.fixture
def Setting(load_client_module):  # noqa: N802
    return load_client_module("services/model/setting").Setting


def _put(tables, key, value):
    tables.setting.add_row(key=key, value=value)


def test_vdo_config_defaults_with_no_rows(Setting, tables):
    assert Setting.vdo_config() == {
        "origin": "https://vdo.ninja",
        "profile": "",
        "salt": None,
    }


def test_vdo_config_reads_the_three_values(Setting, tables):
    _put(tables, "vdo_origin", "https://meet.example.test")
    _put(tables, "vdo_profile", SCREEN_SHARE)
    _put(tables, "vdo_salt", "abc")

    assert Setting.vdo_config() == {
        "origin": "https://meet.example.test",
        "profile": SCREEN_SHARE,
        "salt": "abc",
    }


def test_vdo_config_empty_values_fall_back(Setting, tables):
    _put(tables, "vdo_origin", "")
    _put(tables, "vdo_profile", "")
    _put(tables, "vdo_salt", "")

    assert Setting.vdo_config() == {
        "origin": "https://vdo.ninja",
        "profile": "",
        "salt": None,
    }


def test_vdo_config_normalises_the_stored_origin(Setting, tables):
    _put(tables, "vdo_origin", "https://Meet.Example.Test/")

    assert Setting.vdo_config()["origin"] == "https://meet.example.test"


@pytest.mark.parametrize(
    "stored", ["http://evil.example", "https://a.example/x", "javascript:alert(1)"]
)
def test_vdo_config_refuses_a_bad_stored_origin(Setting, tables, stored):
    _put(tables, "vdo_origin", stored)

    with pytest.raises(ValueError) as caught:
        Setting.vdo_config()

    assert "vdo_origin" in str(caught.value)
    assert stored not in str(caught.value)


def test_vdo_config_refuses_a_stored_profile_with_meshcast(Setting, tables):
    _put(tables, "vdo_profile", "ssq=-1&meshcast=SECRETVALUE")

    with pytest.raises(ValueError) as caught:
        Setting.vdo_config()

    assert "vdo_profile" in str(caught.value)
    assert "SECRETVALUE" not in str(caught.value)


def test_get_value_returns_the_stored_string_or_none(Setting, tables):
    _put(tables, "vdo_origin", "https://meet.example.test")

    assert Setting.get_value("vdo_origin") == "https://meet.example.test"
    assert Setting.get_value("vdo_salt") is None


def test_get_value_refuses_other_keys_without_reading(Setting, tables):
    _put(tables, "secret_thing", "x")

    with pytest.raises(KeyError):
        Setting.get_value("secret_thing")

    assert tables.setting.reads == 0


def test_setting_methods_are_registered_server_methods(Setting):
    registered = {
        r.name for r in anvil.server.registrations if r.kind == "server_method"
    }

    assert {"Setting.vdo_config", "Setting.get_value"} <= registered


# --- set_profile and get_profile (admin only) -----------------------------


@pytest.fixture
def permissions(load_client_module):
    return load_client_module("services/permissions")


@pytest.fixture
def admin(as_user, make_user):
    user = make_user(email="admin@example.test", is_admin=True)
    as_user(user)
    return user


def _profile_rows(tables):
    return [r for r in tables.setting.rows if r["key"] == "vdo_profile"]


def test_set_profile_stores_the_normalised_profile_and_returns_it(
    Setting, tables, admin
):
    result = Setting.set_profile("&quality=1&screensharequality=2")

    assert result == "quality=1&screensharequality=2"
    rows = _profile_rows(tables)
    assert len(rows) == 1
    assert rows[0]["value"] == "quality=1&screensharequality=2"


def test_set_profile_updates_the_existing_row_and_saves_it(Setting, tables, admin):
    _put(tables, "vdo_profile", "quality=1")
    existing = _profile_rows(tables)[0]

    Setting.set_profile("quality=2")

    assert _profile_rows(tables) == [existing]
    assert existing["value"] == "quality=2"
    assert existing.saves >= 1


def test_the_next_vdo_config_uses_the_saved_profile(Setting, tables, admin):
    Setting.set_profile("quality=1")

    assert Setting.vdo_config()["profile"] == "quality=1"
    Setting.set_profile("quality=2")
    assert Setting.vdo_config()["profile"] == "quality=2"


def test_set_profile_accepts_the_empty_profile(Setting, tables, admin):
    _put(tables, "vdo_profile", "quality=1")

    assert Setting.set_profile("") == ""

    assert _profile_rows(tables)[0]["value"] == ""
    assert Setting.vdo_config()["profile"] == ""


@pytest.mark.parametrize(
    "bad", ["&meshcast", "&relay", "&password=x", "&room=x", "&salt=x", "&hash=x"]
)
def test_set_profile_refuses_a_bad_profile_and_keeps_the_old_one(
    Setting, tables, admin, bad
):
    _put(tables, "vdo_profile", "quality=1")

    with pytest.raises(ValueError) as caught:
        Setting.set_profile(bad)

    assert "profile parameter" in str(caught.value)
    assert _profile_rows(tables)[0]["value"] == "quality=1"


def test_set_profile_refuses_a_bad_profile_without_creating_a_row(
    Setting, tables, admin
):
    with pytest.raises(ValueError):
        Setting.set_profile("&meshcast")

    assert _profile_rows(tables) == []


def test_set_profile_refuses_input_over_2000_characters_before_validating(
    Setting, tables, admin, monkeypatch, load_client_module
):
    vdo = load_client_module("services/vdo")
    seen = []
    monkeypatch.setattr(vdo, "validate_profile", lambda text: seen.append(text))

    with pytest.raises(ValueError):
        Setting.set_profile("a" * 2001)

    assert seen == []
    assert _profile_rows(tables) == []


def test_set_profile_accepts_exactly_2000_characters(Setting, tables, admin):
    text = "q=" + "a" * 1998

    assert Setting.set_profile(text) == text


@pytest.mark.parametrize("bad", [None, 5, b"quality=1", ["quality=1"]])
def test_set_profile_refuses_a_non_string(Setting, tables, admin, bad):
    with pytest.raises(ValueError):
        Setting.set_profile(bad)

    assert _profile_rows(tables) == []


def test_get_profile_returns_the_raw_stored_text(Setting, tables, admin):
    assert Setting.get_profile() == ""
    _put(tables, "vdo_profile", "quality=1")

    assert Setting.get_profile() == "quality=1"


@pytest.mark.parametrize("who", ["anonymous", "non-admin"])
def test_set_and_get_profile_refuse_anyone_but_admin(
    Setting, tables, permissions, as_user, make_user, who
):
    as_user(None if who == "anonymous" else make_user(is_admin=False))
    _put(tables, "vdo_profile", "quality=1")

    with pytest.raises(permissions.PermissionDenied):
        Setting.set_profile("quality=2")
    with pytest.raises(permissions.PermissionDenied):
        Setting.get_profile()

    assert _profile_rows(tables)[0]["value"] == "quality=1"


def test_profile_methods_are_registered_server_methods(Setting):
    registered = {
        r.name for r in anvil.server.registrations if r.kind == "server_method"
    }

    assert {"Setting.set_profile", "Setting.get_profile"} <= registered


def test_set_profile_refuses_an_unknown_key_with_a_clear_message(
    Setting, tables, admin
):
    with pytest.raises(ValueError) as caught:
        Setting.set_profile("quality=1&bogus=2")

    assert "'bogus' is not on the allowed list" in str(caught.value)
    assert _profile_rows(tables) == []


def test_the_extra_keys_setting_allows_one_more_key(Setting, tables, admin):
    _put(tables, "vdo_profile_extra_keys", "Bogus, other")

    assert Setting.set_profile("bogus=2") == "bogus=2"
    assert Setting.vdo_config()["profile"] == "bogus=2"
    with pytest.raises(ValueError):
        Setting.set_profile("relay")
