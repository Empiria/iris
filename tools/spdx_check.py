#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria
"""Fail if a tracked file has neither an SPDX header nor a REUSE.toml cover.

Every tracked file must either carry both lines near the top:

    SPDX-License-Identifier: MIT
    Copyright (c) 2026 Empiria

or match a `path` pattern in an `[[annotations]]` entry of REUSE.toml (REUSE
specification 3.x). Files that can't hold a comment (JSON, lock files, images,
the LICENSE) and files that an editor rewrites (anvil.yaml and the Anvil form
templates) are covered by REUSE.toml.

Usage: python3 tools/spdx_check.py
"""

import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python before 3.11: fall back to reading the path lists.
    tomllib = None

ROOT = Path(__file__).resolve().parents[1]
HEADER_LINES = 20
IDENTIFIER = "SPDX-License-Identifier:"
COPYRIGHT = "Copyright (c) 2026 Empiria"


def tracked_files(root=ROOT):
    """Every tracked path, relative to the repo root, with `/` separators."""
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    return [name for name in out.decode("utf-8").split("\0") if name]


def has_header(text):
    """True when the top of `text` holds the licence line and the copyright."""
    head = "\n".join(text.splitlines()[:HEADER_LINES])
    return IDENTIFIER in head and COPYRIGHT in head


def reuse_patterns(toml_text):
    """The `path` patterns of every [[annotations]] entry in a REUSE.toml."""
    if tomllib is not None:
        data = tomllib.loads(toml_text)
        patterns = []
        for entry in data.get("annotations", []):
            path = entry.get("path", [])
            patterns.extend([path] if isinstance(path, str) else path)
        return patterns
    patterns = []
    for block in re.findall(r"^path\s*=\s*(\[.*?\]|\".*?\")", toml_text, re.S | re.M):
        patterns.extend(re.findall(r'"([^"]+)"', block))
    return patterns


def _glob_to_regex(pattern):
    """REUSE globs: `*` stops at `/`, `**` crosses it, `**/` may match nothing."""
    pattern = pattern.lstrip("/")
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def covered_by(path, patterns):
    return any(_glob_to_regex(p).match(path) for p in patterns)


def missing(files, patterns, read):
    """The files with neither a header nor a cover. `read(path)` gives text."""
    bad = []
    for path in files:
        if covered_by(path, patterns):
            continue
        if not has_header(read(path)):
            bad.append(path)
    return bad


def main():
    toml_path = ROOT / "REUSE.toml"
    if not toml_path.exists():
        print("spdx: REUSE.toml is missing", file=sys.stderr)
        return 1
    patterns = reuse_patterns(toml_path.read_text(encoding="utf-8"))

    def read(path):
        # Undecodable bytes (a binary file) just won't contain the header.
        return (ROOT / path).read_bytes().decode("utf-8", errors="replace")

    bad = missing(tracked_files(), patterns, read)
    if bad:
        print("spdx: no SPDX header and no REUSE.toml cover for:", file=sys.stderr)
        for path in bad:
            print("  " + path, file=sys.stderr)
        return 1
    print("spdx: every tracked file has a header or a REUSE.toml cover")
    return 0


if __name__ == "__main__":
    sys.exit(main())
