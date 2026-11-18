import anvil.server
import anvil.users

from iris.services import permissions  # pyright: ignore[reportAttributeAccessIssue]


@anvil.server.callable
def admin_status():
    """The caller's own sign-in state, for the admin page.

    Public by design: it reports only the caller's own state, and the page needs
    it to tell an admin account from any other signed-in account. The email is
    returned only to admin, so a non-admin account learns nothing beyond that.
    """
    user = anvil.users.get_user()
    if user is None:
        return {"signed_in": False, "is_admin": False, "email": None}
    if not permissions.is_admin(user):
        return {"signed_in": True, "is_admin": False, "email": None}
    return {"signed_in": True, "is_admin": True, "email": user["email"]}
