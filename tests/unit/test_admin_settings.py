import importlib

import anvil.server
import pytest


@pytest.fixture
def admin_settings(load_client_module):
    # The model and permissions load first, as they do on the server.
    load_client_module("services/model/setting")
    return importlib.import_module("iris.admin_settings")


@pytest.fixture
def permissions(load_client_module):
    return load_client_module("services/permissions")


@pytest.fixture
def Setting(load_client_module):  # noqa: N802
    return load_client_module("services/model/setting").Setting


@pytest.fixture
def admin(as_user, make_user):
    user = make_user(email="admin@example.test", is_admin=True)
    as_user(user)
    return user


def _registration(name):
    found = [
        r for r in anvil.server.registrations if r.kind == "callable" and r.name == name
    ]
    assert len(found) == 1, name
    return found[0]


@pytest.mark.parametrize("name", ["get_profile", "update_profile"])
def test_the_callables_require_admin(admin_settings, permissions, name):
    assert _registration(name).kwargs.get("require_user") is permissions.is_admin


def test_update_then_get_round_trips_through_vdo_config(
    admin_settings, Setting, tables, admin
):
    stored = admin_settings.update_profile("&quality=1&screensharequality=2")

    assert stored == "quality=1&screensharequality=2"
    assert admin_settings.get_profile() == stored
    assert Setting.vdo_config()["profile"] == stored


def test_update_with_an_empty_profile_clears_it(admin_settings, Setting, tables, admin):
    admin_settings.update_profile("quality=1")

    assert admin_settings.update_profile("") == ""
    assert admin_settings.get_profile() == ""
    assert Setting.vdo_config()["profile"] == ""


@pytest.mark.parametrize("bad", ["&meshcast", "&relay", "&password=x", "&room=x"])
def test_a_rejected_profile_raises_and_leaves_the_stored_one(
    admin_settings, tables, admin, bad
):
    admin_settings.update_profile("quality=1")

    with pytest.raises(ValueError) as caught:
        admin_settings.update_profile(bad)

    assert "not allowed" in str(caught.value) or "set by Iris" in str(caught.value)
    assert admin_settings.get_profile() == "quality=1"


def test_an_oversize_profile_is_refused(admin_settings, tables, admin):
    with pytest.raises(ValueError):
        admin_settings.update_profile("a" * 2001)


@pytest.mark.parametrize("who", ["anonymous", "non-admin"])
def test_the_model_refuses_when_the_runtime_gate_is_bypassed(
    admin_settings, tables, permissions, as_user, make_user, who
):
    # The stubs do not enforce `require_user`, so this is the model's own check.
    as_user(None if who == "anonymous" else make_user(is_admin=False))

    with pytest.raises(permissions.PermissionDenied):
        admin_settings.update_profile("quality=1")
    with pytest.raises(permissions.PermissionDenied):
        admin_settings.get_profile()

    assert tables.setting.rows == []


def test_the_module_does_not_touch_tables_directly():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[2] / "server_code/admin_settings.py"
    ).read_text()
    assert "app_tables" not in source
