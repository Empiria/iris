"""The reset glue only calls the Users service and shows one fixed message."""

import anvil.users
import pytest


@pytest.fixture
def reset(load_client_module):
    return load_client_module("services/password_reset")


@pytest.fixture
def sent(monkeypatch):
    calls = []
    monkeypatch.setattr(
        anvil.users, "send_password_reset_email", calls.append, raising=False
    )
    return calls


def test_sends_through_the_users_service(reset, sent):
    assert reset.request_reset("  admin@example.test ") == reset.SENT
    assert sent == ["admin@example.test"]


def test_blank_email_sends_nothing(reset, sent):
    assert reset.request_reset("   ") == reset.ENTER_EMAIL
    assert sent == []


def test_unknown_address_shows_the_same_text(reset, monkeypatch):
    def refuse(email):
        raise anvil.users.AuthenticationFailed("This username does not exist")

    monkeypatch.setattr(anvil.users, "send_password_reset_email", refuse, raising=False)

    assert reset.request_reset("nobody@example.test") == reset.SENT


def test_mail_failure_is_not_hidden(reset, monkeypatch):
    def broken(email):
        raise RuntimeError("no mail")

    monkeypatch.setattr(anvil.users, "send_password_reset_email", broken, raising=False)

    with pytest.raises(RuntimeError):
        reset.request_reset("admin@example.test")


def test_offer_pending_reset_calls_get_user_and_never_raises(reset, monkeypatch):
    calls = []

    def get_user(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("boom")

    monkeypatch.setattr(anvil.users, "get_user", get_user)

    reset.offer_pending_reset()

    assert calls == [1]
