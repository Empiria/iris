"""The Join page credits VDO.Ninja, with a safe link and no hardcoded colour."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = (ROOT / "client_code/Join/form_template.html").read_text(encoding="utf-8")
CSS = (ROOT / "theme/assets/theme.css").read_text(encoding="utf-8")


def _credit_link():
    match = re.search(r"<a\b[^>]*>\s*VDO\.Ninja\s*</a>", TEMPLATE)
    assert match, "no VDO.Ninja link on the Join page"
    return match.group(0)


def test_join_page_links_to_vdo_ninja_with_noopener():
    link = _credit_link()

    assert 'href="https://vdo.ninja"' in link
    assert re.search(r'rel="[^"]*\bnoopener\b', link)


def test_join_page_says_powered_by_and_not_affiliated():
    assert "Powered by" in TEMPLATE
    assert "not affiliated" in TEMPLATE


def test_credit_is_styled_with_iris_classes_and_no_hardcoded_colour():
    assert 'class="iris-footer"' in TEMPLATE
    block = CSS[CSS.index(".iris-footer {") : CSS.index("/* An error is carried")]
    assert "var(--iris-" in block
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgb\(|hsl\(", block)
