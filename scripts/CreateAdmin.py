# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Create the first admin user.

Sign-up is off and a browser cannot launch a script, so this is the only way
the first admin account comes to exist. It refuses to run once any admin user
exists, so it cannot be used to add a second one or to take over an account.

Arguments: [EMAIL [PASSWORD]]. Each value comes from, in order, the launch
argument, the environment variable (IRIS_ADMIN_EMAIL, IRIS_ADMIN_PASSWORD), the
app secret (iris_admin_email, iris_admin_password). With no password anywhere a
random one is generated and printed once, on a line `generated password: ...`.
The password is never printed from any other source. The generated password is
printed because nothing else gets the first admin in: sign-up is off, and a
password reset needs working email, which a fresh or local deployment may not
have. To avoid printing one at all, supply your own (argument, environment or
secret). Either way the password must meet the Users service's secure-password
rule (`require_secure_passwords` in `anvil.yaml`). Once email works, the Forgot
password flow replaces a generated password. The older names
IRIS_STAFF_EMAIL, IRIS_STAFF_PASSWORD, iris_staff_email and iris_staff_password
are still read as a fallback.

Hosted: set the `iris_admin_email` app secret and, if you want to choose it, the
`iris_admin_password` secret. Press Run on `CreateAdmin` in the Anvil editor,
read the output, then remove the password secret.

Local: `just create-admin --dev`, or `just create-admin you@example.com`. The
launcher passes the values as launch arguments. A generated password is in
`just logs`.
"""

import os
import secrets
import sys

import anvil.users
from anvil.tables import app_tables

# This is the only place that calls signup_with_email, and a unit test holds it
# to that. It also reads app_tables directly rather than through a model class:
# it runs once, outside the request path, and the User model would need a table
# class that a script cannot import before the app is set up.

MIN_PASSWORD_LENGTH = 8


def _args():
    try:
        import anvil.script  # pyright: ignore[reportMissingImports]

        return list(anvil.script.args)
    except ImportError:
        # anvil-app-server 1.17.0 has no anvil.script and sets sys.argv to the
        # launch arguments with no program name in front.
        return list(sys.argv)


def _secret(name):
    try:
        import anvil.secrets

        return anvil.secrets.get_secret(name) or None
    except Exception as exc:
        # The type only: an exception message can carry a value.
        print("secret", name, "not readable:", type(exc).__name__)
        return None


def _value(args, index, env_name, secret_name):
    """The launch argument, else the environment, else the secret.

    The names this script used before the staff-to-admin rename
    (IRIS_STAFF_*, iris_staff_*) are still read, after the new ones, so a
    deployment that set them keeps working.
    """
    if len(args) > index:
        return args[index], "argument"
    old_env = env_name.replace("ADMIN", "STAFF")
    old_secret = secret_name.replace("admin", "staff")
    for name in (env_name, old_env):
        if os.environ.get(name):
            return os.environ[name], "environment"
    for name in (secret_name, old_secret):
        found = _secret(name)
        if found:
            return found, "secret"
    return None, "none"


def _clean_email(email):
    email = email.strip().lower()
    local, _, domain = email.partition("@")
    if not local or not domain or "@" in domain or any(c.isspace() for c in email):
        raise ValueError("the email address is not valid")
    return email


def _refuse_existing(email):
    if next(iter(app_tables.users.search(is_admin=True)), None) is not None:
        raise RuntimeError("an admin user already exists; refusing to create another")
    if app_tables.users.get(email=email) is not None:
        raise RuntimeError("an account for this email already exists; not changing it")


def _password(args):
    password, source = _value(args, 1, "IRIS_ADMIN_PASSWORD", "iris_admin_password")
    if password is None:
        return secrets.token_urlsafe(18), "generated"
    if len(password) < MIN_PASSWORD_LENGTH:
        # Never echo the value.
        raise ValueError(
            f"the password must have at least {MIN_PASSWORD_LENGTH} characters"
        )
    return password, source


def main():
    args = _args()
    email, _source = _value(args, 0, "IRIS_ADMIN_EMAIL", "iris_admin_email")
    if email is None:
        raise SystemExit(
            "no email: pass one as the first argument, or set the "
            "IRIS_ADMIN_EMAIL environment variable or the iris_admin_email secret"
        )
    email = _clean_email(email)
    _refuse_existing(email)
    password, source = _password(args)
    user = anvil.users.signup_with_email(email, password)
    if user is None:
        raise RuntimeError("the account was not created")
    user["is_admin"] = True
    print("created admin user", user["email"], "password from", source)
    if source == "generated":
        print("generated password:", password)


main()
