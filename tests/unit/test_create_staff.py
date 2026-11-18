"""The first-staff script (scripts/CreateStaff.py) and its local launcher.

The script runs `main()` at module level, so each test executes it with
`exec`, `sys.argv` set to the launch arguments and fake `anvil.users`,
`anvil.tables` and `anvil.secrets` modules in `sys.modules`. The launcher is
plain Python and its pure functions are called directly with fakes.
"""

import ast
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "CreateStaff.py"

# Distinctive values, so a leak into any output line is easy to see.
PASSWORD = "Zq7-distinct-pw-4471"
ENV_PASSWORD = "Zq7-env-pw-5582"
SECRET_PASSWORD = "Zq7-secret-pw-6693"


class SecretsFake:
    def __init__(self, values=None, error=None):
        self.values = values or {}
        self.error = error
        self.asked = []

    def get_secret(self, name):
        self.asked.append(name)
        if self.error is not None:
            raise self.error
        if name not in self.values:
            raise KeyError(name)
        return self.values[name]


@pytest.fixture
def run_script(monkeypatch, tables):
    """Run the script. Returns the fake Users service so a test can inspect it."""
    for name in ("IRIS_STAFF_EMAIL", "IRIS_STAFF_PASSWORD"):
        monkeypatch.delenv(name, raising=False)

    def run(args=(), env=None, secrets=None, secret_error=None, script_args=None):
        for key, value in (env or {}).items():
            monkeypatch.setenv(key, value)
        calls = []

        def signup_with_email(email, password):
            calls.append((email, password))
            return tables.users.add_row(email=email, is_staff=None)

        users = types.ModuleType("anvil.users")
        users.signup_with_email = signup_with_email
        secret_module = types.ModuleType("anvil.secrets")
        fake_secrets = SecretsFake(secrets, secret_error)
        secret_module.get_secret = fake_secrets.get_secret
        run.secrets = fake_secrets
        anvil = sys.modules["anvil"]
        monkeypatch.setitem(sys.modules, "anvil.users", users)
        monkeypatch.setattr(anvil, "users", users, raising=False)
        monkeypatch.setitem(sys.modules, "anvil.secrets", secret_module)
        monkeypatch.setattr(anvil, "secrets", secret_module, raising=False)
        monkeypatch.setattr(sys, "argv", list(args))
        if script_args is not None:
            script = types.ModuleType("anvil.script")
            script.args = list(script_args)
            monkeypatch.setitem(sys.modules, "anvil.script", script)
            monkeypatch.setattr(anvil, "script", script, raising=False)
        # Not runpy.run_path: it overwrites sys.argv[0] with the script path,
        # and the runtime's argv is the launch arguments and nothing else.
        code = compile(SCRIPT.read_text(encoding="utf-8"), str(SCRIPT), "exec")
        exec(code, {"__name__": "create_staff_script"})  # noqa: S102
        return calls

    return run


def _lines(capsys):
    return capsys.readouterr().out.splitlines()


# --- script: where the values come from ------------------------------------


def test_arguments_create_a_staff_user(run_script, tables, capsys):
    calls = run_script(["Boss@Example.test", PASSWORD])

    assert calls == [("boss@example.test", PASSWORD)]
    row = tables.users.get(email="boss@example.test")
    assert row["is_staff"] is True
    out = capsys.readouterr().out
    assert "created staff user boss@example.test password from argument" in out
    assert PASSWORD not in out


def test_environment_is_used_without_arguments(run_script, capsys):
    calls = run_script(
        [],
        env={
            "IRIS_STAFF_EMAIL": "env@example.test",
            "IRIS_STAFF_PASSWORD": ENV_PASSWORD,
        },
    )

    assert calls == [("env@example.test", ENV_PASSWORD)]
    out = capsys.readouterr().out
    assert "env@example.test password from environment" in out
    assert ENV_PASSWORD not in out


def test_secrets_are_used_last(run_script, capsys):
    calls = run_script(
        [],
        secrets={
            "iris_staff_email": "secret@example.test",
            "iris_staff_password": SECRET_PASSWORD,
        },
    )

    assert calls == [("secret@example.test", SECRET_PASSWORD)]
    out = capsys.readouterr().out
    assert "secret@example.test password from secret" in out
    assert SECRET_PASSWORD not in out


def test_environment_beats_secret(run_script):
    secrets = {
        "iris_staff_email": "secret@example.test",
        "iris_staff_password": SECRET_PASSWORD,
    }
    env = {"IRIS_STAFF_EMAIL": "env@example.test", "IRIS_STAFF_PASSWORD": ENV_PASSWORD}

    assert run_script([], env=env, secrets=secrets) == [
        ("env@example.test", ENV_PASSWORD)
    ]


def test_argument_beats_environment(run_script, tables):
    tables.clear()
    env = {"IRIS_STAFF_EMAIL": "env@example.test", "IRIS_STAFF_PASSWORD": ENV_PASSWORD}

    assert run_script(["arg@example.test", PASSWORD], env=env) == [
        ("arg@example.test", PASSWORD)
    ]


def test_anvil_script_args_are_preferred_when_the_module_exists(run_script):
    calls = run_script(
        ["ignored@example.test"], script_args=["new@example.test", PASSWORD]
    )

    assert calls == [("new@example.test", PASSWORD)]


def test_a_generated_password_is_printed_once(run_script, capsys):
    calls = run_script(["gen@example.test"])

    assert len(calls) == 1
    email, password = calls[0]
    assert email == "gen@example.test"
    assert len(password) >= 20
    lines = _lines(capsys)
    printed = [ln for ln in lines if password in ln]
    assert printed == [f"generated password: {password}"]
    assert any("password from generated" in ln for ln in lines)


def test_an_unreadable_secret_is_treated_as_absent(run_script, capsys):
    calls = run_script(
        ["a@example.test"], secret_error=RuntimeError("detail-never-printed")
    )

    assert len(calls) == 1
    out = capsys.readouterr().out
    assert "RuntimeError" in out
    assert "detail-never-printed" not in out


# --- script: validation -----------------------------------------------------


def test_the_email_is_stripped_and_lowercased(run_script):
    calls = run_script(["  MiXed@Example.TEST  ", PASSWORD])

    assert calls == [("mixed@example.test", PASSWORD)]


@pytest.mark.parametrize("email", ["   ", "", "nope", "a@b@c", "a b@c.d"])
def test_a_bad_email_is_refused(run_script, email):
    with pytest.raises(ValueError):
        run_script([email, PASSWORD])


def test_a_short_password_is_refused_without_echoing_it(run_script):
    with pytest.raises(ValueError) as caught:
        run_script(["a@example.test", "short"])

    assert "short" not in str(caught.value)


def test_no_email_anywhere_names_every_source(run_script):
    with pytest.raises(SystemExit) as caught:
        run_script([])

    message = str(caught.value)
    assert "IRIS_STAFF_EMAIL" in message
    assert "iris_staff_email" in message


# --- script: refusals --------------------------------------------------------


def test_it_refuses_when_a_staff_user_exists(run_script, tables):
    tables.users.add_row(email="old@example.test", is_staff=True)

    with pytest.raises(RuntimeError, match="a staff user already exists"):
        run_script(["new@example.test", PASSWORD])

    assert tables.users.get(email="new@example.test") is None


def test_it_does_not_read_a_password_after_finding_staff(run_script, tables):
    tables.users.add_row(email="old@example.test", is_staff=True)
    with pytest.raises(RuntimeError):
        run_script(["new@example.test"], secrets={})

    assert "iris_staff_password" not in run_script.secrets.asked


def test_it_does_not_touch_an_existing_row_for_the_email(run_script, tables):
    row = tables.users.add_row(email="same@example.test", is_staff=None)

    with pytest.raises(RuntimeError):
        run_script(["same@example.test", PASSWORD])

    assert row["is_staff"] is None
    assert row.saves == 0


# --- script: shape ------------------------------------------------------------


def test_the_script_has_no_prompt_and_no_network():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    forbidden_modules = {"getpass", "socket", "urllib", "requests", "http", "httpx"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "input", "a prompt raises EOFError (S7i)"
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden_modules
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden_modules


def test_the_script_names_its_run_instructions():
    doc = ast.get_docstring(ast.parse(SCRIPT.read_text(encoding="utf-8")))

    for needle in ("DEPL-03", "iris_staff_password", "just create-staff"):
        assert needle in doc


# --- launcher -------------------------------------------------------------------


@pytest.fixture
def launcher(load_tool):
    return load_tool("create_staff")


class FakeTask:
    def __init__(self, statuses, error=None):
        self.statuses = list(statuses)
        self.error = error
        self.polls = 0

    def get_termination_status(self):
        self.polls += 1
        if len(self.statuses) > 1:
            return self.statuses.pop(0)
        return self.statuses[0]

    def get_error(self):
        return self.error


class FakeServer:
    def __init__(self, task):
        self.task = task
        self.launched = []

    def launch_background_task(self, name, *args):
        self.launched.append((name, args))
        return self.task


def _no_sleep(_seconds):
    return None


def test_default_connection_follows_the_stack_url_file(launcher, tmp_path):
    url_file = tmp_path / "stack-url"
    url_file.write_text("http://localhost:41234/\n")
    assert launcher.resolve_connection({}, url_file) == (
        "ws://localhost:41234/_/uplink",
        "dev-uplink",
    )


def test_the_launcher_names_no_stack_when_there_is_none(launcher, tmp_path):
    with pytest.raises(ValueError, match="just up"):
        launcher.resolve_connection({}, tmp_path / "missing")


@pytest.mark.parametrize(
    "url", ["ws://localhost:3030/_/uplink", "ws://127.0.0.1:3031/_/uplink"]
)
def test_loopback_urls_are_accepted(launcher, url):
    assert launcher.resolve_connection({"IRIS_UPLINK_URL": url})[0] == url


def test_the_key_can_be_overridden_by_environment(launcher):
    env = {"IRIS_UPLINK_KEY": "other", "IRIS_URL": "http://localhost:41234/"}
    assert launcher.resolve_connection(env)[1] == "other"


@pytest.mark.parametrize(
    "url",
    [
        "wss://user:secret-token@iris.example.com/_/uplink",
        "ws://iris.example.com/_/uplink",
        "wss://localhost:3030/_/uplink",
        "http://localhost:3030/_/uplink",
    ],
)
def test_a_non_local_url_is_refused_without_leaking_it(launcher, url):
    with pytest.raises(ValueError) as caught:
        launcher.resolve_connection(
            {"IRIS_UPLINK_URL": url, "IRIS_UPLINK_KEY": "key-never-printed"}
        )

    message = str(caught.value)
    assert "Anvil editor" in message
    assert "key-never-printed" not in message
    assert "secret-token" not in message
    assert "iris.example.com" not in message


def test_launch_passes_email_and_password(launcher):
    server = FakeServer(FakeTask([None, "completed"]))

    result = launcher.launch_script(
        server, "a@example.test", PASSWORD, 30, sleep=_no_sleep
    )

    assert result == ("created", None)
    assert server.launched == [("script:CreateStaff", ("a@example.test", PASSWORD))]


def test_launch_passes_only_the_email_when_there_is_no_password(launcher):
    server = FakeServer(FakeTask(["completed"]))

    launcher.launch_script(server, "a@example.test", None, 30, sleep=_no_sleep)

    assert server.launched == [("script:CreateStaff", ("a@example.test",))]


def test_launch_reports_a_failed_task_with_its_error(launcher):
    task = FakeTask(["failed"], error="RuntimeError: a staff user already exists")

    result = launcher.launch_script(
        FakeServer(task), "a@example.test", PASSWORD, 30, sleep=_no_sleep
    )

    assert result == ("failed", "RuntimeError: a staff user already exists")


class RaisingErrorTask(FakeTask):
    """The uplink's get_error re-raises the task's exception instead of returning it."""

    def get_error(self):
        raise RuntimeError(self.error)


def test_launch_reports_a_failure_when_get_error_raises(launcher):
    task = RaisingErrorTask(["failed"], error="a staff user already exists")

    result = launcher.launch_script(
        FakeServer(task), "a@example.test", PASSWORD, 30, sleep=_no_sleep
    )

    assert result[0] == "failed"
    assert "a staff user already exists" in result[1]
    assert PASSWORD not in result[1]


def test_launch_times_out(launcher):
    ticks = iter(range(0, 1000, 10))
    task = FakeTask([None])

    with pytest.raises(TimeoutError) as caught:
        launcher.launch_script(
            FakeServer(task),
            "a@example.test",
            PASSWORD,
            30,
            sleep=_no_sleep,
            clock=lambda: next(ticks),
        )

    assert PASSWORD not in str(caught.value)


def test_a_failed_task_error_never_echoes_the_password(launcher):
    task = FakeTask(["failed"], error=f"ValueError: {PASSWORD}")

    status, text = launcher.launch_script(
        FakeServer(task), "a@example.test", PASSWORD, 30, sleep=_no_sleep
    )

    assert status == "failed"
    assert PASSWORD not in text


def test_ensure_staff_is_idempotent(launcher, tables):
    tables.users.add_row(email="a@example.test", is_staff=True)
    server = FakeServer(FakeTask(["completed"]))

    result = launcher.ensure_staff("a@example.test", PASSWORD, server, tables)

    assert result == "present"
    assert server.launched == []


def test_ensure_staff_launches_when_the_row_is_not_staff(launcher, tables):
    tables.users.add_row(email="a@example.test", is_staff=None)
    server = FakeServer(FakeTask(["completed"]))

    result = launcher.ensure_staff(
        "a@example.test", PASSWORD, server, tables, sleep=_no_sleep
    )

    assert result == "created"
    assert len(server.launched) == 1


def test_ensure_staff_raises_with_the_script_error(launcher, tables):
    server = FakeServer(FakeTask(["failed"], error="RuntimeError: nope"))

    with pytest.raises(launcher.ScriptFailed, match="nope"):
        launcher.ensure_staff(
            "a@example.test", PASSWORD, server, tables, sleep=_no_sleep
        )


class FakeUsersApi:
    def __init__(self, tables):
        self.tables = tables
        self.calls = []

    def signup_with_email(self, email, password):
        self.calls.append((email, password))
        return self.tables.users.add_row(email=email, is_staff=None)


def test_ensure_viewer_creates_a_non_staff_user_once(launcher, tables):
    users_api = FakeUsersApi(tables)

    first = launcher.ensure_viewer("v@example.test", PASSWORD, users_api, tables)
    second = launcher.ensure_viewer("v@example.test", PASSWORD, users_api, tables)

    assert (first, second) == ("created", "present")
    assert users_api.calls == [("v@example.test", PASSWORD)]
    assert not tables.users.get(email="v@example.test")["is_staff"]


def test_dev_credentials_are_local_constants(launcher):
    assert launcher.DEV_STAFF_EMAIL == "staff@example.test"
    assert launcher.DEV_VIEWER_EMAIL == "viewer@example.test"
    assert len(launcher.DEV_STAFF_PASSWORD) >= 8
    assert len(launcher.DEV_VIEWER_PASSWORD) >= 8


# --- launcher: command line ---------------------------------------------------


def test_parser_takes_no_secret_arguments():
    source = (ROOT / "tools" / "create_staff.py").read_text(encoding="utf-8")

    for flag in ("--password", "--key", "--token"):
        assert f'"{flag}"' not in source
        assert f"'{flag}'" not in source


def test_dev_mode_uses_the_dev_constants(launcher):
    parsed = launcher.parse_args(["--dev"], {})

    assert parsed == (
        launcher.DEV_STAFF_EMAIL,
        launcher.DEV_STAFF_PASSWORD,
        True,
    )


def test_without_dev_the_email_is_required(launcher):
    with pytest.raises(SystemExit):
        launcher.parse_args([], {})


def test_without_dev_the_password_comes_from_the_environment(launcher):
    parsed = launcher.parse_args(
        ["me@example.test"], {"IRIS_STAFF_PASSWORD": ENV_PASSWORD}
    )

    assert parsed == ("me@example.test", ENV_PASSWORD, False)
    assert launcher.parse_args(["me@example.test"], {}) == (
        "me@example.test",
        None,
        False,
    )


class FakeConnection:
    def __init__(self, server, users_api, tables):
        self.parts = (server, users_api, tables)

    def __call__(self, url, key):
        outer = self

        class Context:
            def __enter__(self):
                return outer.parts

            def __exit__(self, *exc):
                return False

        return Context()


def _main(launcher, tables, statuses, argv, environ=None, error=None):
    server = FakeServer(FakeTask(statuses, error=error))
    connect = FakeConnection(server, FakeUsersApi(tables), tables)
    # The stack has no fixed port, so every run names one.
    environ = {"IRIS_URL": "http://localhost:41234/", **(environ or {})}
    return server, launcher.main(argv, environ, connect=connect, sleep=_no_sleep)


def test_main_creates_dev_accounts_and_exits_zero(launcher, tables, capsys):
    server, code = _main(launcher, tables, ["completed"], ["--dev"])

    assert code == 0
    out = capsys.readouterr().out
    assert "staff account created (staff@example.test)" in out
    assert "viewer account created (viewer@example.test)" in out
    assert launcher.DEV_STAFF_PASSWORD not in out
    assert launcher.DEV_VIEWER_PASSWORD not in out


def test_main_says_where_a_generated_password_is(launcher, tables, capsys):
    server, code = _main(launcher, tables, ["completed"], ["me@example.test"])

    assert code == 0
    assert server.launched == [("script:CreateStaff", ("me@example.test",))]
    out = capsys.readouterr().out
    assert "password generated: read it in just logs" in out


def test_main_exits_one_with_the_script_error(launcher, tables, capsys):
    server, code = _main(
        launcher,
        tables,
        ["failed"],
        ["me@example.test"],
        {"IRIS_STAFF_PASSWORD": ENV_PASSWORD},
        error="RuntimeError: a staff user already exists",
    )

    assert code == 1
    captured = capsys.readouterr()
    assert "a staff user already exists" in captured.err
    assert ENV_PASSWORD not in captured.out + captured.err


def test_main_refuses_a_hosted_url(launcher, tables, capsys):
    code = launcher.main(
        ["--dev"], {"IRIS_UPLINK_URL": "wss://iris.example.com/_/uplink"}
    )

    assert code == 1
    assert "Anvil editor" in capsys.readouterr().err
