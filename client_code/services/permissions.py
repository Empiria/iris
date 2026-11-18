"""Who counts as staff.

`is_staff` is shaped for `@anvil.server.callable(require_user=is_staff)`.
`require_staff` is for model method bodies: a `server_method` is callable from
any browser, so a method that writes authorises inside its own body.
"""

import anvil.server
import anvil.users


class StaffOnly(Exception):
    """Fallback if the runtime has no anvil.server.PermissionDenied."""


# A failed `require_user` raises anvil.server.PermissionDenied, and so does
# `require_staff`, so a client catches one exception for both. The stubs that
# `anvil validate` and `just check` bundle omit it, so it is reached by name.
PermissionDenied = getattr(anvil.server, "PermissionDenied", StaffOnly)


def is_staff(user):
    """True only for a signed-in user whose `is_staff` column is true."""
    if user is None:
        return False
    return user["is_staff"] is True


def require_staff():
    """Return the signed-in staff user, or raise PermissionDenied."""
    user = anvil.users.get_user()
    if not is_staff(user):
        raise PermissionDenied("Staff only")
    return user
