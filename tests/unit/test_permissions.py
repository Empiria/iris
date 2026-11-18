import anvil.server
import pytest


@pytest.fixture
def permissions(load_client_module):
    return load_client_module("services/permissions")


def test_is_admin_false_for_signed_out(permissions):
    assert permissions.is_admin(None) is False


def test_is_admin_true_for_admin(permissions, make_user):
    assert permissions.is_admin(make_user(is_admin=True)) is True


@pytest.mark.parametrize("flag", [False, None])
def test_is_admin_false_when_flag_not_true(permissions, make_user, flag):
    assert permissions.is_admin(make_user(is_admin=flag)) is False


def test_require_admin_returns_the_admin_user(permissions, make_user, as_user):
    admin = make_user()
    as_user(admin)

    assert permissions.require_admin() is admin


def test_require_admin_refuses_signed_out(permissions, as_user):
    as_user(None)

    with pytest.raises(anvil.server.PermissionDenied):
        permissions.require_admin()


def test_require_admin_refuses_non_admin(permissions, make_user, as_user):
    as_user(make_user(is_admin=False))

    with pytest.raises(anvil.server.PermissionDenied):
        permissions.require_admin()


# The users column was renamed from is_staff to is_admin. Code ships before the
# schema is resolved in the Anvil editor, so the old column must still work.


def test_is_admin_falls_back_to_legacy_column_when_missing(permissions):
    from fakes import MISSING, FakeUser

    user = FakeUser(is_admin=MISSING, is_staff=True)

    assert permissions.is_admin(user) is True


def test_is_admin_falls_back_to_legacy_column_when_none(permissions):
    from fakes import FakeUser

    assert permissions.is_admin(FakeUser(is_admin=None, is_staff=True)) is True


def test_is_admin_set_value_beats_legacy_column(permissions):
    from fakes import FakeUser

    assert permissions.is_admin(FakeUser(is_admin=False, is_staff=True)) is False


def test_is_admin_false_with_neither_column_set(permissions):
    from fakes import MISSING, FakeUser

    assert permissions.is_admin(FakeUser(is_admin=MISSING)) is False
    assert permissions.is_admin(FakeUser(is_admin=MISSING, is_staff=False)) is False
