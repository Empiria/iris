"""admin_status reports the caller's own sign-in state and nothing else."""

import importlib

import anvil.server
import pytest


@pytest.fixture
def admin_status():
    return importlib.import_module("iris.auth").admin_status


def test_signed_out(admin_status, as_user):
    as_user(None)

    assert admin_status() == {"signed_in": False, "is_admin": False, "email": None}


def test_admin_user(admin_status, as_user, make_user):
    as_user(make_user(email="admin@example.test", is_admin=True))

    assert admin_status() == {
        "signed_in": True,
        "is_admin": True,
        "email": "admin@example.test",
    }


@pytest.mark.parametrize("flag", [False, None])
def test_non_admin_user_learns_only_its_own_status(
    admin_status, as_user, make_user, flag
):
    as_user(make_user(email="viewer@example.test", is_admin=flag))

    assert admin_status() == {"signed_in": True, "is_admin": False, "email": None}


def test_admin_status_is_a_public_callable():
    importlib.import_module("iris.auth")
    found = [
        r
        for r in anvil.server.registrations
        if r.kind == "callable" and r.name == "admin_status"
    ]

    assert found, "admin_status is not registered as a callable"
    assert all("require_user" not in r.kwargs for r in found)
