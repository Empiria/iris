import anvil.server
import pytest


@pytest.fixture
def permissions(load_client_module):
    return load_client_module("services/permissions")


def test_is_staff_false_for_signed_out(permissions):
    assert permissions.is_staff(None) is False


def test_is_staff_true_for_staff(permissions, make_user):
    assert permissions.is_staff(make_user(is_staff=True)) is True


@pytest.mark.parametrize("flag", [False, None])
def test_is_staff_false_when_flag_not_true(permissions, make_user, flag):
    assert permissions.is_staff(make_user(is_staff=flag)) is False


def test_require_staff_returns_the_staff_user(permissions, make_user, as_user):
    staff = make_user()
    as_user(staff)

    assert permissions.require_staff() is staff


def test_require_staff_refuses_signed_out(permissions, as_user):
    as_user(None)

    with pytest.raises(anvil.server.PermissionDenied):
        permissions.require_staff()


def test_require_staff_refuses_non_staff(permissions, make_user, as_user):
    as_user(make_user(is_staff=False))

    with pytest.raises(anvil.server.PermissionDenied):
        permissions.require_staff()
