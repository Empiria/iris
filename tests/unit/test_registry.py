"""STAFF-06 gate: every public entry point is named here, or it requires staff.

The server never trusts the client, so each callable, server method and route
the app registers must either be on an allow-list below or check staff itself.
A new registration that is neither fails this test. Adding to an allow-list is a
deliberate public endpoint and must be justified in the plan that adds it.
"""

import ast
import importlib
import inspect
import textwrap
from pathlib import Path

import anvil.server
import pytest

ROOT = Path(__file__).resolve().parents[2]

# Callables any browser may call. ping: the stack health check. staff_status:
# reports only the caller's own sign-in state (plan 02-03).
PUBLIC_CALLABLES = {"ping", "staff_status"}

# Server methods any browser may call. Room.lookup is how a meeting link opens
# and releases nothing for a slug no staff member created. Setting methods read
# only the vdo.ninja keys that a valid link releases anyway (plan 02-02).
PUBLIC_SERVER_METHODS = {"Room.lookup", "Setting.vdo_config", "Setting.get_value"}

# Routes and well-known endpoints any browser may fetch. None yet.
PUBLIC_ROUTES = set()

# Files that may call signup_with_email or force_login. A browser cannot launch
# a script (spike S7d), so the first-staff script is not a public entry point.
SIGNUP_ALLOWED = {"scripts/CreateStaff.py"}

ACCOUNT_CREATORS = {"signup_with_email", "force_login"}
CODE_DIRS = ("client_code", "server_code", "scripts")


def _app_module_names():
    paths = sorted((ROOT / "server_code").glob("*.py"))
    paths += sorted((ROOT / "client_code" / "services" / "model").glob("*.py"))
    names = []
    for path in paths:
        if path.name == "__init__.py":
            continue
        # Drop the client_code or server_code root: both flatten into `iris`.
        dotted = path.relative_to(ROOT).with_suffix("").parts[1:]
        names.append("iris." + ".".join(dotted))
    return names


def _app_registrations():
    """Registrations made by the app's own modules, and no one else's."""
    names = _app_module_names()
    for name in names:
        importlib.import_module(name)
    found = []
    for reg in anvil.server.registrations:
        func = getattr(reg.obj, "__func__", reg.obj)
        if getattr(func, "__module__", None) in names:
            found.append(reg)
    return found


def _of_kind(*kinds):
    return [r for r in _app_registrations() if r.kind in kinds]


def _first_statement_calls_require_staff(func):
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    definition = tree.body[0]
    body = list(definition.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    if not body:
        return False
    first = body[0]
    if isinstance(first, (ast.Expr, ast.Assign)):
        call = first.value
    else:
        return False
    if not isinstance(call, ast.Call):
        return False
    target = call.func
    if isinstance(target, ast.Name):
        return target.id == "require_staff"
    return isinstance(target, ast.Attribute) and target.attr == "require_staff"


def _source_files():
    for directory in CODE_DIRS:
        yield from sorted((ROOT / directory).rglob("*.py"))


def _names_used(path):
    """Every identifier and attribute name in a file, ignoring comments and strings."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                used.add(alias.name.split(".")[-1])
    return used


def test_the_registry_sees_the_app():
    names = {r.name for r in _app_registrations()}

    assert {"ping", "staff_status", "Room.lookup", "Room.create_one_off"} <= names


def test_every_callable_is_public_or_requires_staff():
    permissions = importlib.import_module("iris.services.permissions")
    for reg in _of_kind("callable"):
        if reg.name in PUBLIC_CALLABLES:
            continue
        assert reg.kwargs.get("require_user") is permissions.is_staff, (
            f"callable {reg.name} is not public and does not require staff: "
            "add require_user=permissions.is_staff, or add it to "
            "PUBLIC_CALLABLES and justify it"
        )


def test_every_server_method_is_public_or_checks_staff_first():
    for reg in _of_kind("server_method"):
        if reg.name in PUBLIC_SERVER_METHODS:
            continue
        func = getattr(reg.obj, "__func__", reg.obj)
        assert _first_statement_calls_require_staff(func), (
            f"server method {reg.name} is not public and its first statement "
            "is not a require_staff call: call require_staff first, or add it "
            "to PUBLIC_SERVER_METHODS and justify it"
        )


def test_every_route_is_public():
    for reg in _of_kind("route", "wellknown_endpoint"):
        assert reg.name in PUBLIC_ROUTES, (
            f"{reg.kind} {reg.name} is not on PUBLIC_ROUTES: "
            "add it to the allow-list and justify it"
        )


@pytest.mark.parametrize(
    ("allow_list", "kinds"),
    [
        (PUBLIC_CALLABLES, ("callable",)),
        (PUBLIC_SERVER_METHODS, ("server_method",)),
        (PUBLIC_ROUTES, ("route", "wellknown_endpoint")),
    ],
    ids=["callables", "server_methods", "routes"],
)
def test_allow_list_entries_name_real_registrations(allow_list, kinds):
    existing = {r.name for r in _of_kind(*kinds)}

    stale = sorted(allow_list - existing)

    assert not stale, f"allow-list entries with no registration: {stale}"


def test_no_account_creation_outside_the_first_staff_script():
    for path in _source_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative in SIGNUP_ALLOWED:
            continue
        used = _names_used(path) & ACCOUNT_CREATORS
        assert not used, (
            f"{relative} uses {sorted(used)}: only {sorted(SIGNUP_ALLOWED)} "
            "may create accounts or force a login"
        )


def test_the_first_staff_script_is_the_only_script():
    # The script's own behaviour is pinned in test_create_staff.py.
    scripts = sorted(
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "scripts").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )

    assert set(scripts) <= {"scripts/CreateStaff.py"}, (
        "a new script is a deliberate, reviewed addition: update this test "
        "and SIGNUP_ALLOWED together"
    )


def test_app_tables_only_in_model_files():
    models = ROOT / "client_code" / "services" / "model"
    for directory in ("client_code", "server_code"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            if models in path.parents:
                continue
            assert "app_tables" not in _names_used(path), (
                f"{path.relative_to(ROOT).as_posix()} uses app_tables: "
                "data access goes through a model class"
            )


def test_a_registration_from_another_module_is_ignored():
    @anvil.server.callable
    def throwaway_unguarded_callable():
        return "x"

    names = {r.name for r in _app_registrations()}

    assert not any("throwaway_unguarded_callable" in n for n in names)
    assert any(
        r.name.endswith("throwaway_unguarded_callable")
        for r in anvil.server.registrations
    )
