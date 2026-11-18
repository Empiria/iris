# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import pytest


@pytest.fixture
def page_language(load_client_module):
    return load_client_module("services/page_language")


def test_apply_sets_lang_on_the_document(page_language):
    seen = []

    assert page_language.apply(lambda name, value: seen.append((name, value))) is True
    assert seen == [("lang", page_language.LANGUAGE)]


def test_apply_is_false_without_a_browser(page_language):
    assert page_language.apply() is False
