#!/usr/bin/env python3
"""Fail if anything left over from mini-app-starter has come back.

Scans every tracked or unignored file. This file and the optional local
pattern file are skipped, because they have to name the patterns they look for.
The patterns here are generic. A personal link list is not spelled here: it
lives in an untracked .leftovers-local file at the repo root, one regex per
line (blank lines and lines starting with # are ignored).
"""

import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "Farcaster or frame integration": r"farcaster|warpcast|fc:frame|frame-sdk",
    "esm.sh import": r"esm\.sh",
    "mini-app-starter clone link or URL": r"(https?://|git@|ssh://)\S*mini-app-starter",
    # The shape of a private-link URL is an assumption (A5), not a verified format.
    "private-link anvil.app URL": r"https?://[\w.-]+\.anvil\.app/[\w-]{16,}",
    "framing allowed": r"^allow_embedding:\s*true\b",
}
# One line per pattern that must trip it. tests/unit/test_leftovers.py uses these,
# so the test file never has to spell a pattern out (and trip the scan itself).
SAMPLES = {
    "Farcaster or frame integration": "import farcaster",
    "esm.sh import": "import x from 'https://esm.sh/x'",
    "mini-app-starter clone link or URL": "git clone https://github.com/x/mini-app-starter",
    "private-link anvil.app URL": "https://example-app.anvil.app/ABCDEFGHIJKLMNOP",
    "framing allowed": "allow_embedding: true",
}
LOCAL_FILE = ".leftovers-local"
SKIP = {"tools/leftovers.py", LOCAL_FILE}
SKIP_DIRS = {".planning"}


def tracked_files(root: Path) -> list:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [p for p in out.split("\0") if p]


def load_local_patterns(root: Path) -> list:
    """Return (line number, compiled regex) for each optional local pattern."""
    path = root / LOCAL_FILE
    if not path.is_file():
        return []
    patterns = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        try:
            patterns.append((number, re.compile(text, re.IGNORECASE)))
        except re.error:
            # Name the line only: the regex is the thing that must stay private.
            print(
                f"leftovers: invalid regex in {LOCAL_FILE} line {number}",
                file=sys.stderr,
            )
            sys.exit(2)
    return patterns


def scan_line(rel: str, number: int, line: str, extra: list) -> list:
    hits = [
        f"{rel}:{number}: {label}"
        for label, pattern in PATTERNS.items()
        if re.search(pattern, line, re.IGNORECASE)
    ]
    hits.extend(
        f"{rel}:{number}: local pattern ({LOCAL_FILE} line {local_number})"
        for local_number, regex in extra
        if regex.search(line)
    )
    return hits


def scan(root: Path, local: bool = True) -> list:
    extra = load_local_patterns(root) if local else []
    hits = []
    for rel in tracked_files(root):
        if rel in SKIP or rel.split("/")[0] in SKIP_DIRS:
            continue
        path = root / rel
        if not path.is_file() or path.is_symlink():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, 1):
            hits.extend(scan_line(rel, number, line, extra))
    return hits


def main() -> int:
    hits = scan(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    for hit in hits:
        print(hit)
    if hits:
        print(f"leftovers: {len(hits)} problem(s) found")
        return 1
    print("leftovers: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
