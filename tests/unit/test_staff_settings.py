import importlib

import anvil.server
import pytest


@pytest.fixture
def staff_settings(load_client_module):
    # The model and permissions load first, as they do on the server.
    load_client_module("services/model/setting")
    return importlib.import_module("iris.staff_settings")


@pytest.fixture
def permissions(load_client_module):
    return load_client_module("services/permissions")


@pytest.fixture
def Setting(load_client_module):  # noqa: N802
    return load_client_module("services/model/setting").Setting


@pytest.fixture
def staff(as_user, make_user):
    user = make_user(email="staff@example.test", is_staff=True)
    as_user(user)
    return user


def _registration(name):
    found = [
        r for r in anvil.server.registrations if r.kind == "callable" and r.name == name
    ]
    assert len(found) == 1, name
    return found[0]


@pytest.mark.parametrize("name", ["get_profile", "update_profile"])
def test_the_callables_require_staff(staff_settings, permissions, name):
    assert _registration(name).kwargs.get("require_user") is permissions.is_staff


def test_update_then_get_round_trips_through_vdo_config(
    staff_settings, Setting, tables, staff
):
    stored = staff_settings.update_profile("&quality=1&screensharequality=2")

    assert stored == "quality=1&screensharequality=2"
    assert staff_settings.get_profile() == stored
    assert Setting.vdo_config()["profile"] == stored


def test_update_with_an_empty_profile_clears_it(staff_settings, Setting, tables, staff):
    staff_settings.update_profile("quality=1")

    assert staff_settings.update_profile("") == ""
    assert staff_settings.get_profile() == ""
    assert Setting.vdo_config()["profile"] == ""


@pytest.mark.parametrize("bad", ["&meshcast", "&relay", "&password=x", "&room=x"])
def test_a_rejected_profile_raises_and_leaves_the_stored_one(
    staff_settings, tables, staff, bad
):
    staff_settings.update_profile("quality=1")

    with pytest.raises(ValueError) as caught:
        staff_settings.update_profile(bad)

    assert "not allowed" in str(caught.value) or "set by Iris" in str(caught.value)
    assert staff_settings.get_profile() == "quality=1"


def test_an_oversize_profile_is_refused(staff_settings, tables, staff):
    with pytest.raises(ValueError):
        staff_settings.update_profile("a" * 2001)


@pytest.mark.parametrize("who", ["anonymous", "non-staff"])
def test_the_model_refuses_when_the_runtime_gate_is_bypassed(
    staff_settings, tables, permissions, as_user, make_user, who
):
    # The stubs do not enforce `require_user`, so this is the model's own check.
    as_user(None if who == "anonymous" else make_user(is_staff=False))

    with pytest.raises(permissions.PermissionDenied):
        staff_settings.update_profile("quality=1")
    with pytest.raises(permissions.PermissionDenied):
        staff_settings.get_profile()

    assert tables.setting.rows == []


def test_the_module_does_not_touch_tables_directly():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2] / "server_code/staff_settings.py"
    ).read_text()
    assert "app_tables" not in source
