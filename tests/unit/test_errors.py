# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""`errors.user_message` reads the text of a server ValueError.

The browser client gets a server ValueError as AnvilWrappedError, with the
message in args.
"""

import pytest


@pytest.fixture
def errors(load_client_module):
    return load_client_module("services/errors.py")


class AnvilWrappedError(Exception):
    """Stands in for anvil.server.AnvilWrappedError: the message is in args."""


def test_plain_value_error(errors):
    assert errors.user_message(ValueError("Name taken.")) == "Name taken."


def test_wrapped_error_gives_its_message(errors):
    assert errors.user_message(AnvilWrappedError("Name taken.")) == "Name taken."


def test_wrapped_error_without_message_is_none(errors):
    assert errors.user_message(AnvilWrappedError()) is None
    assert errors.user_message(AnvilWrappedError("")) is None


def test_other_exception_is_none(errors):
    assert errors.user_message(RuntimeError("boom")) is None
