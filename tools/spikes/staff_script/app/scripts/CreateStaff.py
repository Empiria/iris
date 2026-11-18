"""Create the first staff user. Spike candidate for scripts/CreateStaff.py.

Arguments: [EMAIL [PASSWORD]]. Each value comes from, in order, the launch
argument, the environment variable (IRIS_STAFF_EMAIL, IRIS_STAFF_PASSWORD), the
app secret (iris_staff_email, iris_staff_password). With no password anywhere a
random one is generated and printed once.
"""

import os
import secrets
import sys

import anvil.users
from anvil.tables import app_tables


def _args():
    try:
        import anvil.script

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
        print("secret", name, "not readable:", type(exc).__name__)
        return None


def _value(args, index, env_name, secret_name):
    """The launch argument, else the environment, else the secret."""
    if len(args) > index and args[index]:
        return args[index], "argument"
    if os.environ.get(env_name):
        return os.environ[env_name], "environment"
    found = _secret(secret_name)
    if found:
        return found, "secret"
    return None, "none"


def main():
    args = _args()
    email, email_source = _value(args, 0, "IRIS_STAFF_EMAIL", "iris_staff_email")
    if not email:
        raise SystemExit(
            "no email: pass one, or set IRIS_STAFF_EMAIL / iris_staff_email"
        )
    email = email.strip().lower()
    if app_tables.users.get(is_staff=True) is not None:
        raise RuntimeError("a staff user already exists; refusing to create another")
    password, source = _value(args, 1, "IRIS_STAFF_PASSWORD", "iris_staff_password")
    if password is None:
        password, source = secrets.token_urlsafe(18), "generated"
    user = anvil.users.signup_with_email(email, password)
    user["is_staff"] = True
    print("created staff user", user["email"], "password from", source)
    if source == "generated":
        print("generated password:", password)


main()
