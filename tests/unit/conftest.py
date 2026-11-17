"""Stub the Anvil runtime so server modules import without a server.

The stubs are installed unconditionally. Never wrap the install in a check for
an existing `anvil` entry in sys.modules: whichever suite imported first would
win.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _identity_decorator(func=None, **_kwargs):
    """Work bare (`@callable`) and called (`@callable(require_user=True)`)."""
    if func is None:
        return lambda inner: inner
    return func


def _install_anvil_stubs():
    anvil = types.ModuleType("anvil")
    server = types.ModuleType("anvil.server")
    server.callable = _identity_decorator
    server.server_method = _identity_decorator
    anvil.server = server
    sys.modules["anvil"] = anvil
    sys.modules["anvil.server"] = server


_install_anvil_stubs()


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
