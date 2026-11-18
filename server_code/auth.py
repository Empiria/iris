import anvil.server
import anvil.users

from iris.services import permissions  # pyright: ignore[reportAttributeAccessIssue]


@anvil.server.callable
def staff_status():
    """The caller's own sign-in state, for the staff page.

    Public by design: it reports only the caller's own state, and the page needs
    it to tell a staff account from any other signed-in account. The email is
    returned only to staff, so a non-staff account learns nothing beyond that.
    """
    user = anvil.users.get_user()
    if user is None:
        return {"signed_in": False, "is_staff": False, "email": None}
    if not permissions.is_staff(user):
        return {"signed_in": True, "is_staff": False, "email": None}
    return {"signed_in": True, "is_staff": True, "email": user["email"]}
