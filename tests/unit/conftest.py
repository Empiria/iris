# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

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


class TransactionConflict(Exception):
    """Stands in for anvil.tables.TransactionConflict."""


def in_transaction(func=None, relaxed=False):
    """Stands in for anvil.tables.in_transaction.

    Like Anvil's, it re-runs the function when it raises TransactionConflict,
    up to five tries, then lets the conflict out. Unlike Anvil's it does not
    isolate anything: it rolls the tables back to the state before a failed
    try, which is all the retry tests need.
    """
    if func is None:
        return lambda f: in_transaction(f, relaxed=relaxed)

    def wrapper(*args, **kwargs):
        for attempt in range(5):
            snapshot = FAKE_TABLES.snapshot()
            try:
                return func(*args, **kwargs)
            except TransactionConflict:
                FAKE_TABLES.restore(snapshot)
                if attempt == 4:
                    raise
        raise AssertionError("unreachable")

    return wrapper


def _get_user(*_args, **_kwargs):
    return _CURRENT["user"]


class SecretError(Exception):
    """Stands in for anvil.secrets.SecretError."""


def _make_secrets_stub():
    """A reversible stand-in for `anvil.secrets` encryption with named keys.

    `KEYS` holds the key names that exist. The "ciphertext" is the key name and
    the text reversed, so a test can tell it from the plaintext and a wrong key
    fails to decrypt, as the real one does.
    """
    secrets = types.ModuleType("anvil.secrets")
    secrets.KEYS = {"iris_passphrase_key"}
    secrets.SecretError = SecretError

    def encrypt_with_key(key_name, value):
        if key_name not in secrets.KEYS:
            raise SecretError("No such encryption key '" + key_name + "'")
        return "enc:" + key_name + ":" + value[::-1]

    def decrypt_with_key(key_name, value):
        if key_name not in secrets.KEYS:
            raise SecretError("No such encryption key '" + key_name + "'")
        prefix = "enc:" + key_name + ":"
        if not value.startswith(prefix):
            raise SecretError("Could not decrypt")
        return value[len(prefix) :][::-1]

    secrets.encrypt_with_key = encrypt_with_key
    secrets.decrypt_with_key = decrypt_with_key
    return secrets


def _install_anvil_stubs():
    secrets = _make_secrets_stub()
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
    tables.in_transaction = in_transaction
    tables.TransactionConflict = TransactionConflict

    users.get_user = _get_user
    users.AuthenticationFailed = AuthenticationFailed

    anvil.server = server
    anvil.tables = tables
    anvil.users = users
    anvil.secrets = secrets
    sys.modules["anvil.secrets"] = secrets
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
    """Build a `FakeUser`. Defaults to an admin."""

    def make(email="admin@example.test", is_admin=True):
        return FakeUser(email=email, is_admin=is_admin)

    return make


@pytest.fixture
def admin(as_user, make_user):
    """Sign in an admin and return it."""
    user = make_user(email="admin@example.test", is_admin=True)
    as_user(user)
    return user


@pytest.fixture
def Room(load_client_module):  # noqa: N802
    return load_client_module("services/model/room").Room


@pytest.fixture
def slugs(load_client_module):
    return load_client_module("services/slugs")


@pytest.fixture
def secret_keys():
    """The set of encryption key names the stubbed `anvil.secrets` knows.

    Restored after the test. Empty it to play a missing key.
    """
    keys = sys.modules["anvil.secrets"].KEYS
    saved = set(keys)
    yield keys
    keys.clear()
    keys.update(saved)


@pytest.fixture
def verifier():
    return importlib.import_module("iris.verifier")


@pytest.fixture
def fast_kdf(verifier, monkeypatch):
    """Cheap iterations, so a test of the logic does not pay for 600000."""
    monkeypatch.setattr(verifier, "ITERATIONS", 1000)


@pytest.fixture
def clock(Room, load_client_module, monkeypatch):
    """A frozen clock: the model reads `clock.now`, and `advance()` moves it."""
    import datetime

    from room_helpers import START

    module = load_client_module("services/model/room")

    class Clock:
        now = START

        def advance(self, **delta):
            self.now = self.now + datetime.timedelta(**delta)

    frozen = Clock()
    monkeypatch.setattr(module, "_now", lambda: frozen.now)
    return frozen
