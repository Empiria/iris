"""Who counts as admin.

`is_admin` is shaped for `@anvil.server.callable(require_user=is_admin)`.
`require_admin` is for model method bodies: a `server_method` is callable from
any browser, so a method that writes authorises inside its own body.
"""

import anvil.server
import anvil.users


class AdminOnly(Exception):
    """Fallback if the runtime has no anvil.server.PermissionDenied."""


# A failed `require_user` raises anvil.server.PermissionDenied, and so does
# `require_admin`, so a client catches one exception for both. The stubs that
# `anvil validate` and `just check` bundle omit it, so it is reached by name.
PermissionDenied = getattr(anvil.server, "PermissionDenied", AdminOnly)


def _column(user, name):
    """The column's value, or None when the table has no such column."""
    try:
        return user[name]
    except Exception:
        # A column that does not exist raises (NoSuchColumnError on Anvil,
        # KeyError on a plain mapping). Both mean "not set".
        return None


def is_admin(user):
    """True only for a signed-in user whose `is_admin` column is true.

    The column used to be called `is_staff`. While a deployment's schema still
    has the old name (code deployed before the column is renamed in the Anvil
    editor), or has both columns with `is_admin` not yet set, the old column
    decides, so an existing admin is never locked out. An `is_admin` that is
    set, true or false, always wins. Once every deployment has renamed the
    column, the `is_staff` fallback can go.
    """
    if user is None:
        return False
    flag = _column(user, "is_admin")
    if flag is None:
        flag = _column(user, "is_staff")
    return flag is True


def require_admin():
    """Return the signed-in admin user, or raise PermissionDenied."""
    user = anvil.users.get_user()
    if not is_admin(user):
        raise PermissionDenied("Admin only")
    return user
