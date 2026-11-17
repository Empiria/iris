"""Contract tests for tools/leftovers.py.

The patterns are never spelled here: every sample line comes from the tool's own
SAMPLES, so this file cannot trip the scan it tests. The optional local pattern
file is exercised with a neutral made-up pattern only.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NEUTRAL = "zzqx-[0-9]+"


@pytest.fixture
def leftovers(load_tool):
    return load_tool("leftovers")


@pytest.fixture
def repo(tmp_path):
    """A throwaway git repo under tmp_path. The real repo is never touched."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def local_file(repo, leftovers, text):
    (repo / leftovers.LOCAL_FILE).write_text(text)


def test_samples_cover_exactly_the_patterns(leftovers):
    assert set(leftovers.SAMPLES) == set(leftovers.PATTERNS)


def test_each_sample_trips_its_pattern(leftovers, repo):
    for label, sample in leftovers.SAMPLES.items():
        (repo / "sample.txt").write_text(sample + "\n")

        hits = leftovers.scan(repo, local=False)

        assert len(hits) == 1, label
        assert hits[0].endswith(label)


def test_clean_file_has_no_hits(leftovers, repo):
    (repo / "clean.txt").write_text("nothing to see here\n")

    assert leftovers.scan(repo, local=False) == []


def test_skipped_directory_and_symlink_are_not_reported(leftovers, repo):
    sample = next(iter(leftovers.SAMPLES.values()))
    skipped = repo / sorted(leftovers.SKIP_DIRS)[0]
    skipped.mkdir()
    (skipped / "notes.txt").write_text(sample + "\n")
    (repo / "target.txt").write_text("clean\n")
    (repo / "link.txt").symlink_to(skipped / "notes.txt")

    assert leftovers.scan(repo, local=False) == []


def run_main(leftovers, repo, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["leftovers", str(repo)])
    return leftovers.main()


def test_main_returns_1_on_a_hit(leftovers, repo, monkeypatch, capsys):
    (repo / "sample.txt").write_text(next(iter(leftovers.SAMPLES.values())) + "\n")

    assert run_main(leftovers, repo, monkeypatch) == 1
    assert "problem(s) found" in capsys.readouterr().out


def test_main_returns_0_when_clean(leftovers, repo, monkeypatch, capsys):
    (repo / "clean.txt").write_text("fine\n")

    assert run_main(leftovers, repo, monkeypatch) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "leftovers: clean"


def test_real_tree_is_clean_without_the_local_file(leftovers):
    # local=False: an untracked local pattern file on a developer's machine must
    # not change a hermetic test. `just leftovers` covers the local file.
    assert leftovers.scan(ROOT, local=False) == []


def test_local_pattern_hit_is_labelled_by_its_own_line(leftovers, repo):
    local_file(repo, leftovers, f"# a comment\n\n{NEUTRAL}\n")
    (repo / "data.txt").write_text("zzqx-12345\n")

    hits = leftovers.scan(repo)

    assert hits == [f"data.txt:1: local pattern ({leftovers.LOCAL_FILE} line 3)"]


def test_local_file_is_ignored_with_local_false(leftovers, repo):
    local_file(repo, leftovers, f"{NEUTRAL}\n")
    (repo / "data.txt").write_text("zzqx-12345\n")

    assert leftovers.scan(repo, local=False) == []


def test_local_file_is_never_reported_against_itself(leftovers, repo):
    # The file is untracked and holds text its own pattern matches (in a comment).
    local_file(repo, leftovers, f"# zzqx-1 is an example\n{NEUTRAL}\n")

    assert leftovers.scan(repo) == []


def test_invalid_local_regex_exits_2_without_echoing_it(leftovers, repo):
    local_file(repo, leftovers, f"{NEUTRAL}\nzzqx-(\n")

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/leftovers.py"), str(repo)],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 2
    assert f"{leftovers.LOCAL_FILE} line 2" in result.stderr
    assert "zzqx" not in result.stdout + result.stderr
