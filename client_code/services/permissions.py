"""Who counts as staff.

`is_staff` is shaped for `@anvil.server.callable(require_user=is_staff)`.
`require_staff` is for model method bodies: a `server_method` is callable from
any browser, so a method that writes authorises inside its own body.
"""

import anvil.server
import anvil.users


def is_staff(user):
    """True only for a signed-in user whose `is_staff` column is true."""
    if user is None:
        return False
    return user["is_staff"] is True


def require_staff():
    """Return the signed-in staff user, or raise PermissionDenied."""
    user = anvil.users.get_user()
    if not is_staff(user):
        raise anvil.server.PermissionDenied("Staff only")
    return user
