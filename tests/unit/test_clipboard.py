# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import pytest


@pytest.fixture
def clipboard(load_client_module):
    return load_client_module("services/clipboard")


def test_copy_reports_success_and_passes_the_text(clipboard):
    seen = []

    assert clipboard.copy("https://x/y", write=seen.append) is True
    assert seen == ["https://x/y"]


def test_copy_reports_a_refusal_as_false(clipboard):
    def refuse(text):
        raise PermissionError("denied")

    assert clipboard.copy("secret", write=refuse) is False


def test_copy_is_false_without_a_browser(clipboard):
    # No `anvil.js` here, so the default writer can't be built: still a clean False.
    assert clipboard.copy("x") is False
