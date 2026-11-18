"""Stub the Anvil runtime so server modules import without a server.

The stubs are installed unconditionally. Never wrap the install in a check for
an existing `anvil` entry in sys.modules: whichever suite imported first would
win.

What the stubs give a test:

- `anvil.server.callable`, `server_method`, `route` and `wellknown_endpoint`
  return the decorated object unchanged and record a `Registration` in
  `anvil.server.registrations`.
- `anvil.tables.app_tables` is a `FakeTables` (see fakes.py).
- `anvil.users.get_user()` returns the user set through the `as_user` fixture.
- `iris` is a package whose path is both `client_code/` and `server_code/`, as
  on the Anvil server, so `from iris.services import slugs` works.
"""

import importlib
import importlib.util
import sys
import types
from collections import namedtuple
from pathlib import Path

import pytest
from fakes import FakeTables, FakeUser

ROOT = Path(__file__).resolve().parents[2]

Registration = namedtuple("Registration", "kind name kwargs obj")

_REGISTRATIONS = []
_CURRENT = {"user": None}
FAKE_TABLES = FakeTables()


def _target_name(obj):
    inner = getattr(obj, "__func__", obj)
    return getattr(inner, "__qualname__", repr(inner))


def _is_target(obj):
    if isinstance(obj, str):
        return False
    return callable(obj) or isinstance(obj, (classmethod, staticmethod))


def _recorder(kind):
    """Build a stub decorator that records its use and changes nothing.

    Works bare (`@callable`), called with keywords (`@callable(require_user=p)`)
    and called with a leading positional such as a route path. Positional
    arguments other than the decorated object are kept under `kwargs["args"]`.
    """

    def record(obj, args, kwargs):
        extra = dict(kwargs)
        if args:
            extra["args"] = tuple(args)
        _REGISTRATIONS.append(Registration(kind, _target_name(obj), extra, obj))
        return obj

    def decorator(*args, **kwargs):
        if len(args) == 1 and not kwargs and _is_target(args[0]):
            return record(args[0], (), {})
        return lambda obj: record(obj, args, kwargs)

    decorator.__name__ = kind
    return decorator


class PermissionDenied(Exception):
    """Stands in for anvil.server.PermissionDenied."""


class AuthenticationFailed(Exception):
    """Stands in for anvil.users.AuthenticationFailed."""


def _get_user(*_args, **_kwargs):
    return _CURRENT["user"]


def _install_anvil_stubs():
    anvil = types.ModuleType("anvil")
    server = types.ModuleType("anvil.server")
    tables = types.ModuleType("anvil.tables")
    users = types.ModuleType("anvil.users")

    server.callable = _recorder("callable")
    server.server_method = _recorder("server_method")
    server.route = _recorder("route")
    server.wellknown_endpoint = _recorder("wellknown_endpoint")
    server.PermissionDenied = PermissionDenied
    server.registrations = _REGISTRATIONS

    tables.app_tables = FAKE_TABLES

    users.get_user = _get_user
    users.AuthenticationFailed = AuthenticationFailed

    anvil.server = server
    anvil.tables = tables
    anvil.users = users
    sys.modules["anvil"] = anvil
    sys.modules["anvil.server"] = server
    sys.modules["anvil.tables"] = tables
    sys.modules["anvil.users"] = users


def _install_iris_package():
    """Register `iris` over both source trees, as Anvil's flattened namespace."""
    package = types.ModuleType("iris")
    package.__path__ = [str(ROOT / "client_code"), str(ROOT / "server_code")]
    package.__package__ = "iris"
    sys.modules["iris"] = package
    # Drop cached submodules so a fresh install never serves stale ones.
    for name in [n for n in sys.modules if n.startswith("iris.")]:
        del sys.modules[name]


_install_anvil_stubs()
_install_iris_package()


def _load_by_path(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def load_server_module():
    """Load server_code/<name>.py by path, the way the server flattens it."""

    def load(name):
        return _load_by_path(f"server_code_{name}", ROOT / "server_code" / f"{name}.py")

    return load


@pytest.fixture
def load_tool():
    """Load tools/<name>.py by path. tools/ is not a package."""

    def load(name):
        return _load_by_path(f"tools_{name}", ROOT / "tools" / f"{name}.py")

    return load


@pytest.fixture
def load_client_module():
    """Import client_code/<relpath>.py as `iris.<dotted path>`.

    `relpath` looks like "services/model/room". The import is cached, so the
    module is the one the other modules import too.
    """

    def load(relpath):
        dotted = ".".join(Path(relpath).with_suffix("").parts)
        return importlib.import_module(f"iris.{dotted}")

    return load


@pytest.fixture
def tables():
    """The fake `app_tables`, emptied before and after the test."""
    FAKE_TABLES.clear()
    yield FAKE_TABLES
    FAKE_TABLES.clear()


@pytest.fixture
def as_user():
    """Set the signed-in user: `as_user(user)`. `as_user(None)` signs out."""

    def set_user(user):
        _CURRENT["user"] = user

    _CURRENT["user"] = None
    yield set_user
    _CURRENT["user"] = None


@pytest.fixture
def make_user():
    """Build a `FakeUser`. Defaults to a staff member."""

    def make(email="staff@example.test", is_staff=True):
        return FakeUser(email=email, is_staff=is_staff)

    return make
