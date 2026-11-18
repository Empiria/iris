# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""The control border meets the 3:1 non-text contrast minimum (WCAG 1.4.11).

axe-core does not measure a border, so this reads the colours from
theme/parameters.yaml and checks them against the surfaces an input sits on.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _colours():
    data = yaml.safe_load((ROOT / "theme/parameters.yaml").read_text("utf-8"))
    return {c["name"]: c["color"] for c in data["color_scheme"]["colors"]}


def _luminance(hex_colour):
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _ratio(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_control_border_has_three_to_one_contrast():
    colours = _colours()
    for surface in ("Background", "Surface"):
        assert _ratio(colours["Control Border"], colours[surface]) >= 3


def test_inputs_and_buttons_use_the_control_border():
    css = (ROOT / "theme/assets/theme.css").read_text("utf-8")
    for selector in (".iris-input {", ".iris-button {"):
        block = css[css.index(selector) :].split("}")[0]
        assert "var(--iris-control-border)" in block
