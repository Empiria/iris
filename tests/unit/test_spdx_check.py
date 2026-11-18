# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""tools/spdx_check.py: headers, REUSE.toml globs and the repo's own state."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "spdx_check", ROOT / "tools/spdx_check.py"
)
spdx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(spdx)

HEADER = "# SPDX-License-Identifier: MIT\n# Copyright (c) 2026 Empiria\n"


def test_header_found_near_the_top():
    assert spdx.has_header("#!/usr/bin/env python3\n" + HEADER + "x = 1\n")


@pytest.mark.parametrize(
    "text",
    [
        "x = 1\n",
        "# SPDX-License-Identifier: MIT\nx = 1\n",
        "# Copyright (c) 2026 Empiria\nx = 1\n",
        "\n" * 30 + HEADER,
    ],
)
def test_header_missing_or_incomplete(text):
    assert not spdx.has_header(text)


@pytest.mark.parametrize(
    "pattern, path, expected",
    [
        ("uv.lock", "uv.lock", True),
        ("uv.lock", "sub/uv.lock", False),
        ("**/form_template.html", "client_code/Join/form_template.html", True),
        ("**/form_template.html", "form_template.html", True),
        ("LICENSES/**", "LICENSES/MIT.txt", True),
        ("*.json", "a/b.json", False),
        ("/anvil.yaml", "anvil.yaml", True),
    ],
)
def test_glob_matching(pattern, path, expected):
    assert spdx.covered_by(path, [pattern]) is expected


def test_missing_reports_uncovered_files_without_a_header():
    texts = {"a.py": HEADER, "b.py": "x = 1\n", "c.json": "{}\n"}

    bad = spdx.missing(list(texts), ["c.json"], texts.__getitem__)

    assert bad == ["b.py"]


def test_reuse_patterns_reads_string_and_list_paths():
    toml = (
        'version = 1\n[[annotations]]\npath = "a"\n'
        '[[annotations]]\npath = ["b", "c/**"]\n'
    )

    assert spdx.reuse_patterns(toml) == ["a", "b", "c/**"]


def test_every_tracked_file_in_this_repo_is_covered():
    patterns = spdx.reuse_patterns((ROOT / "REUSE.toml").read_text(encoding="utf-8"))

    def read(path):
        return (ROOT / path).read_bytes().decode("utf-8", errors="replace")

    assert spdx.missing(spdx.tracked_files(ROOT), patterns, read) == []
