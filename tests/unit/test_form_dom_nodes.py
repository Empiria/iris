"""Every `self.dom_nodes["x"]` in form code has a matching `anvil:dom-node="x"`.

In an HTML form template, only `anvil:dom-node` puts a plain element in
`dom_nodes`. `anvil:name` turns it into a child HtmlComponent reached as
`self.x` instead, so a `dom_nodes` lookup for it raises KeyError in the browser.
pytest can't run client code, so this reads the source of each form.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FORMS = sorted(p.parent for p in (ROOT / "client_code").rglob("form_template.html"))

LOOKUP = re.compile(r"""dom_nodes\[\s*["']([^"']+)["']\s*\]""")
DOM_NODE = re.compile(r"""anvil:dom-node\s*=\s*["']([^"']+)["']""")


def test_there_are_forms_to_check():
    assert FORMS


@pytest.mark.parametrize("form", FORMS, ids=lambda p: p.name)
def test_dom_node_lookups_name_a_dom_node(form):
    code = (form / "__init__.py").read_text(encoding="utf-8")
    template = (form / "form_template.html").read_text(encoding="utf-8")

    missing = set(LOOKUP.findall(code)) - set(DOM_NODE.findall(template))

    assert not missing, (
        f"{form.name}: dom_nodes lookups with no anvil:dom-node in the template:"
        f" {sorted(missing)}"
    )
