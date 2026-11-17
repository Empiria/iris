"""Contract tests for tools/anvil_deps.py.

The justfile (`deps`, `up`), the image build and `anvil validate` all lean on
this tool, so its pure functions are pinned here. Nothing is derived from
hardcoded ids or tags: the real-config tests read anvil.yaml, so a version bump
in the IDE never breaks the suite.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def anvil_deps(load_tool):
    return load_tool("anvil_deps")


def make_dep(package, tag="v1.0.0", dep_id=None, app_id=None):
    return {
        "dep_id": dep_id or f"dep_{package}",
        "resolution_hints": {
            "app_id": app_id or f"APP{package.upper()}",
            "name": package,
            "package_name": package,
        },
        "version": {"version_tag": tag},
    }


def write_cache(root, deps, source=None, resolved=None):
    """Write a manifest and cached package files shaped like `anvil deps fetch`."""
    cached = [
        {
            "app_id": d["resolution_hints"]["app_id"],
            "commit_id": "abc",
            "package_name": d["resolution_hints"]["package_name"],
        }
        for d in deps
    ]
    manifest = {
        "version": 3,
        "source_dependencies": deps if source is None else source,
        "resolved_dependencies": (
            [{"app_id": c["app_id"], "commit_id": "abc"} for c in cached]
            if resolved is None
            else resolved
        ),
        "cached_dependencies": cached,
    }
    cache = root / ".anvil/deps"
    cache.mkdir(parents=True)
    (cache / "manifest.json").write_text(json.dumps(manifest))
    for c in cached:
        (cache / c["package_name"]).mkdir()
        (cache / c["package_name"] / "anvil.yaml").write_text("package_name: x\n")


def test_normalise_sorts_keys_recursively_and_keeps_list_order(anvil_deps):
    first = {"b": {"y": 1, "x": [3, 1, 2]}, "a": 1}
    second = {"a": 1, "b": {"x": [3, 1, 2], "y": 1}}

    assert anvil_deps.normalise(first) == anvil_deps.normalise(second)
    assert list(anvil_deps.normalise(first)) == ["a", "b"]
    assert anvil_deps.normalise(first)["b"]["x"] == [3, 1, 2]


def test_is_fresh_when_cache_matches(anvil_deps, tmp_path):
    deps = [make_dep("one"), make_dep("two")]
    write_cache(tmp_path, deps)

    assert anvil_deps.is_fresh(tmp_path, deps) is True


def test_is_fresh_ignores_key_order(anvil_deps, tmp_path):
    deps = [make_dep("one")]
    write_cache(tmp_path, deps)
    reordered = [dict(reversed(list(deps[0].items())))]

    assert anvil_deps.is_fresh(tmp_path, reordered) is True


def test_is_fresh_false_without_manifest(anvil_deps, tmp_path):
    assert anvil_deps.is_fresh(tmp_path, [make_dep("one")]) is False


def test_is_fresh_false_when_source_differs(anvil_deps, tmp_path):
    write_cache(tmp_path, [make_dep("one", tag="v1.0.0")])

    assert anvil_deps.is_fresh(tmp_path, [make_dep("one", tag="v2.0.0")]) is False


def test_is_fresh_false_when_cached_package_is_missing(anvil_deps, tmp_path):
    deps = [make_dep("one")]
    write_cache(tmp_path, deps)
    (tmp_path / ".anvil/deps/one/anvil.yaml").unlink()

    assert anvil_deps.is_fresh(tmp_path, deps) is False


def test_is_fresh_false_when_nothing_resolved(anvil_deps, tmp_path):
    deps = [make_dep("one")]
    write_cache(tmp_path, deps, resolved=[])

    assert anvil_deps.is_fresh(tmp_path, deps) is False


def test_dep_id_args_maps_both_ids_in_dependency_order(anvil_deps):
    deps = [
        make_dep("one", dep_id="dep_a", app_id="APPA"),
        make_dep("two", dep_id="dep_b", app_id="APPB"),
    ]

    assert anvil_deps.dep_id_args(deps) == [
        "--dep-id",
        "dep_a=one",
        "--dep-id",
        "APPA=one",
        "--dep-id",
        "dep_b=two",
        "--dep-id",
        "APPB=two",
    ]


def test_repos_has_a_row_for_every_anvil_yaml_dependency(anvil_deps):
    packages = {
        d["resolution_hints"]["package_name"]
        for d in anvil_deps.read_dependencies(ROOT)
    }

    assert packages == set(anvil_deps.REPOS)


def test_every_dependency_is_pinned_to_a_tag(anvil_deps):
    for dep in anvil_deps.read_dependencies(ROOT):
        assert (dep.get("version") or {}).get("version_tag")


def test_real_dep_id_args_cover_each_dep_id_and_app_id(anvil_deps):
    deps = anvil_deps.read_dependencies(ROOT)
    args = anvil_deps.dep_id_args(deps)

    for dep in deps:
        package = dep["resolution_hints"]["package_name"]
        assert f"{dep['dep_id']}={package}" in args
        assert f"{dep['resolution_hints']['app_id']}={package}" in args


def test_cli_dep_id_args_matches_the_function(anvil_deps):
    # This is the output the `up` recipe splices into the podman run command.
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/anvil_deps.py"),
            "--dep-id-args",
            "--root",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    expected = anvil_deps.dep_id_args(anvil_deps.read_dependencies(ROOT))
    assert result.stdout.split() == expected
