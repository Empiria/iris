"""anvil.yaml pins: sign-up off, and tables that clients cannot read.

Failure messages name the key, never a secret value.
"""

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]

USERS_COLUMNS = {
    "email",
    "enabled",
    "last_login",
    "password_hash",
    "n_password_failures",
    "confirmed_email",
    "signed_up",
    "remembered_logins",
    "is_staff",
}


@pytest.fixture(scope="module")
def config():
    return yaml.safe_load((ROOT / "anvil.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def users_service(config):
    found = [
        s
        for s in config["services"]
        if str(s.get("source", "")).endswith("services/anvil/users.yml")
    ]
    assert len(found) == 1, "services must hold exactly one Users service entry"
    return found[0]


def test_users_service_has_signup_off(users_service):
    assert users_service["client_config"]["allow_signup"] is False


def test_users_service_uses_the_users_table(users_service):
    assert users_service["server_config"]["user_table"] == "users"


def test_no_service_allows_signup(config):
    for service in config["services"]:
        client_config = service.get("client_config") or {}
        assert client_config.get("allow_signup") is not True, (
            f"allow_signup is true in {service.get('source')}"
        )


def test_users_table_columns(config):
    columns = {c["name"]: c["type"] for c in config["db_schema"]["users"]["columns"]}

    assert set(columns) == USERS_COLUMNS
    assert columns["is_staff"] == "bool"


@pytest.mark.parametrize("table", ["users", "room", "setting"])
def test_tables_are_client_invisible(config, table):
    schema = config["db_schema"][table]

    assert schema["client"] == "none", f"db_schema.{table}.client must be none"
    assert schema["server"] == "full", f"db_schema.{table}.server must be full"
