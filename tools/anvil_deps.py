#!/usr/bin/env -S uv run --script
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""Fetch the Anvil dependency apps named in anvil.yaml, with no Anvil login.

Pinned refs come from anvil.yaml (`version.version_tag`); the only thing kept
here is where each app's public source lives (REPOS, keyed by package_name).

Writes two things under <root>/.anvil/ (gitignored):

  deps/<package_name>/   the layout `anvil deps fetch` writes, plus manifest.json,
                         so `anvil validate` treats its dependency cache as fresh
  src/<package_name>/    the full source tree at the tag, for the app-server image
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

# package_name -> public git repo. Add a row when anvil.yaml gains a dependency.
REPOS = {
    "routing": "https://github.com/anvil-works/routing.git",
    "anvil_reactive": "https://github.com/anvilistas/reactive.git",
}
MANIFEST_VERSION = 3  # DEPS_MANIFEST_VERSION in anvil-cli 0.8.1


def read_dependencies(root: Path) -> list:
    data = yaml.safe_load((root / "anvil.yaml").read_text()) or {}
    return data.get("dependencies") or []


def normalise(value):
    """Mirror anvil-cli's normalizeForComparison: sort mapping keys recursively."""
    if isinstance(value, list):
        return [normalise(v) for v in value]
    if isinstance(value, dict):
        return {k: normalise(value[k]) for k in sorted(value)}
    return value


def is_fresh(root: Path, deps: list) -> bool:
    try:
        manifest = json.loads((root / ".anvil/deps/manifest.json").read_text())
    except (OSError, ValueError):
        return False
    if normalise(manifest.get("source_dependencies")) != normalise(deps):
        return False
    resolved = manifest.get("resolved_dependencies") or []
    cached = {c["app_id"]: c for c in manifest.get("cached_dependencies", [])}
    return bool(resolved) and all(
        r["app_id"] in cached
        and (
            root / ".anvil/deps" / cached[r["app_id"]]["package_name"] / "anvil.yaml"
        ).exists()
        for r in resolved
    )


def dep_id_args(deps: list) -> list:
    """The anvil-app-server flags that map each dependency to its directory.

    The runtime resolves by the local dep_id, and the app_id is mapped as well.
    """
    args = []
    for dep in deps:
        package = dep["resolution_hints"]["package_name"]
        for ident in (dep["dep_id"], dep["resolution_hints"]["app_id"]):
            args += ["--dep-id", f"{ident}={package}"]
    return args


def fetch(dep: dict, tmp: Path) -> tuple:
    hints = dep["resolution_hints"]
    package = hints["package_name"]
    tag = (dep.get("version") or {}).get("version_tag")
    if package not in REPOS:
        sys.exit(f"anvil_deps: no public repo known for {package}; add it to REPOS")
    if not tag:
        sys.exit(f"anvil_deps: {package} has no version_tag in anvil.yaml; pin one")
    clone = tmp / package
    subprocess.run(
        [
            "git",
            "clone",
            "--quiet",
            "--depth",
            "1",
            "--branch",
            tag,
            REPOS[package],
            str(clone),
        ],
        check=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    sha = subprocess.run(
        ["git", "-C", str(clone), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return hints["app_id"], package, tag, sha, clone


def main() -> None:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--dep-id-args",
        action="store_true",
        help="print the anvil-app-server --dep-id flags and exit",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    deps = read_dependencies(root)
    if args.dep_id_args:
        print(" ".join(dep_id_args(deps)))
        return
    if not deps:
        print("anvil_deps: anvil.yaml declares no dependencies")
        return
    if not args.force and is_fresh(root, deps):
        print("anvil_deps: .anvil/deps is up to date")
        return

    shutil.rmtree(root / ".anvil/deps", ignore_errors=True)
    shutil.rmtree(root / ".anvil/src", ignore_errors=True)
    (root / ".anvil/deps").mkdir(parents=True)
    (root / ".anvil/src").mkdir(parents=True)
    resolved, cached = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for dep in deps:
            app_id, package, tag, sha, clone = fetch(dep, Path(tmp))
            shutil.rmtree(clone / ".git")
            shutil.copytree(clone, root / ".anvil/src" / package)
            target = root / ".anvil/deps" / package
            for tree in ("client_code", "server_code"):
                src = clone / tree
                if src.is_dir():
                    shutil.copytree(src, target / tree)
                else:
                    (target / tree).mkdir(parents=True)
            (target / "anvil.yaml").write_text(yaml.dump({"package_name": package}))
            resolved.append({"app_id": app_id, "commit_id": sha})
            cached.append({"app_id": app_id, "commit_id": sha, "package_name": package})
            print(f"anvil_deps: {package} {tag} ({sha[:9]})")
    manifest = {
        "version": MANIFEST_VERSION,
        "includeDocs": False,
        "source_dependencies": normalise(deps),
        "resolved_dependencies": resolved,
        "cached_dependencies": cached,
    }
    (root / ".anvil/deps/manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
