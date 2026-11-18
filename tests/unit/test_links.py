# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESULTS = (
    ROOT
    / ".planning"
    / "phases"
    / "02-one-off-meetings-admin-to-client"
    / "02-SPIKE-RESULTS.md"
)


@pytest.fixture
def links(load_client_module):
    return load_client_module("services/links")


@pytest.mark.parametrize("owner", ["runtime", "own"])
def test_link_for_path_owners_give_a_path_link(links, owner):
    assert (
        links.link_for("https://meet.example", "dk2wjd9d", owner)
        == "https://meet.example/dk2wjd9d"
    )


def test_link_for_query_owner_gives_a_query_link(links):
    assert (
        links.link_for("https://meet.example", "dk2wjd9d", "query")
        == "https://meet.example/?m=dk2wjd9d"
    )


def test_link_for_trims_trailing_slashes_on_the_base(links):
    assert (
        links.link_for("https://meet.example//", "dk2wjd9d", "runtime")
        == "https://meet.example/dk2wjd9d"
    )


def test_link_for_lowercases_and_trims_the_slug(links):
    assert (
        links.link_for("https://meet.example", "  DK2WJD9D ", "runtime")
        == "https://meet.example/dk2wjd9d"
    )


def test_link_for_accepts_a_hyphenated_permanent_slug(links):
    assert (
        links.link_for("https://meet.example", "team-room", "runtime")
        == "https://meet.example/team-room"
    )


@pytest.mark.parametrize(
    "base, slug, owner",
    [
        ("https://meet.example", "dk2wjd9d", "other"),
        ("https://meet.example", "dk2wjd9d", ""),
        ("https://meet.example", "", "runtime"),
        ("https://meet.example", "   ", "runtime"),
        ("https://meet.example", "dk2/jd9d", "runtime"),
        ("https://meet.example", "dk2w jd9d", "runtime"),
        ("https://meet.example", "dk2wjd9d?x=1", "runtime"),
        ("https://meet.example", "dk2wjd9d#x", "runtime"),
        ("", "dk2wjd9d", "runtime"),
        ("///", "dk2wjd9d", "runtime"),
    ],
)
def test_link_for_rejects_bad_input(links, base, slug, owner):
    with pytest.raises(ValueError):
        links.link_for(base, slug, owner)


@pytest.mark.parametrize(
    "origin, pathname, expected",
    [
        ("https://meet.example", "/admin", "https://meet.example"),
        ("https://x.anvil.app", "/KEY/admin", "https://x.anvil.app/KEY"),
        ("http://localhost:3030", "/admin/", "http://localhost:3030"),
        ("http://localhost:3030", "/", "http://localhost:3030"),
        ("https://meet.example", "/KEY", "https://meet.example/KEY"),
        ("https://meet.example/", "/admin", "https://meet.example"),
        ("https://meet.example", "", "https://meet.example"),
        # The page's old path, still reachable from existing bookmarks.
        ("https://meet.example", "/staff", "https://meet.example"),
        ("https://x.anvil.app", "/KEY/staff/", "https://x.anvil.app/KEY"),
    ],
)
def test_base_from_location(links, origin, pathname, expected):
    assert links.base_from_location(origin, pathname) == expected


def test_route_owner_is_an_allowed_value(links):
    assert links.ROUTE_OWNER in ("runtime", "own", "query")


def test_route_owner_matches_the_recorded_decision(links):
    if not RESULTS.exists():
        pytest.skip("02-SPIKE-RESULTS.md is not present in this checkout")
    match = re.search(r"^Route owner:\s*(\S+)\s*$", RESULTS.read_text("utf-8"), re.M)
    assert match, "no 'Route owner:' line in 02-SPIKE-RESULTS.md"
    assert match.group(1) == links.ROUTE_OWNER


def test_links_module_is_client_safe():
    source = (ROOT / "client_code" / "services" / "links.py").read_text("utf-8")
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported.update(
                (node.module or "") + "." + alias.name for alias in node.names
            )

    assert imported <= {"iris.services", "iris.services.slugs"}
    assert "app_tables" not in source
