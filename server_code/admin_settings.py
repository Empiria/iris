import anvil.server

from iris.services import permissions  # pyright: ignore[reportAttributeAccessIssue]
from iris.services.model.setting import Setting


@anvil.server.callable(require_user=permissions.is_admin)
def get_profile():
    """The vdo.ninja parameter profile as saved, for the admin page's editor.

    Admin only. The runtime enforces `require_user`, and `Setting.get_profile`
    repeats the check, because a model method is callable on its own.
    """
    return Setting.get_profile()


@anvil.server.callable(require_user=permissions.is_admin)
def update_profile(text):
    """Validate and save the vdo.ninja profile, and return what was stored.

    Admin only. A profile the validator rejects (for example one with &meshcast,
    &relay, &password or &room) raises ValueError with its message and leaves
    the stored profile unchanged. The next join reads the saved profile, because
    `Setting.vdo_config` reads it on every call.
    """
    return Setting.set_profile(text)
