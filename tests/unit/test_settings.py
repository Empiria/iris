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
