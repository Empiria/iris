"""staff_status reports the caller's own sign-in state and nothing else."""

import importlib

import anvil.server
import pytest


@pytest.fixture
def staff_status():
    return importlib.import_module("iris.auth").staff_status


def test_signed_out(staff_status, as_user):
    as_user(None)

    assert staff_status() == {"signed_in": False, "is_staff": False, "email": None}


def test_staff_user(staff_status, as_user, make_user):
    as_user(make_user(email="staff@example.test", is_staff=True))

    assert staff_status() == {
        "signed_in": True,
        "is_staff": True,
        "email": "staff@example.test",
    }


@pytest.mark.parametrize("flag", [False, None])
def test_non_staff_user_learns_only_its_own_status(
    staff_status, as_user, make_user, flag
):
    as_user(make_user(email="viewer@example.test", is_staff=flag))

    assert staff_status() == {"signed_in": True, "is_staff": False, "email": None}


def test_staff_status_is_a_public_callable():
    importlib.import_module("iris.auth")
    found = [
        r
        for r in anvil.server.registrations
        if r.kind == "callable" and r.name == "staff_status"
    ]

    assert found, "staff_status is not registered as a callable"
    assert all("require_user" not in r.kwargs for r in found)
