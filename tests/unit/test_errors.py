"""`errors.user_message` reads the text of a server ValueError.

The Anvil runtime may hand the client the original ValueError or an
AnvilWrappedError carrying `error_obj`. Both must give the message.
"""

import pytest


@pytest.fixture
def errors(load_client_module):
    return load_client_module("services/errors.py")


class _Wrapped(Exception):
    def __init__(self, error_obj):
        super().__init__("wrapped")
        self.error_obj = error_obj


def test_plain_value_error(errors):
    assert errors.user_message(ValueError("Name taken.")) == "Name taken."


def test_wrapped_value_error(errors):
    wrapped = _Wrapped({"type": "ValueError", "message": "Name taken."})
    assert errors.user_message(wrapped) == "Name taken."


def test_wrapped_other_type_is_none(errors):
    assert errors.user_message(_Wrapped({"type": "KeyError", "message": "x"})) is None


def test_other_exception_is_none(errors):
    assert errors.user_message(RuntimeError("boom")) is None
