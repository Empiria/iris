import anvil.server
from anvil.tables import app_tables

from iris.services import vdo  # pyright: ignore[reportAttributeAccessIssue]


class Setting(app_tables.setting.Row, buffered=True, attrs=True):
    """A deployment setting. Only the vdo.ninja keys are readable by callers."""

    # Everything these keys hold is released to anyone with a valid meeting
    # link anyway, so reading them is public by design.
    PUBLIC_KEYS = ("vdo_origin", "vdo_profile", "vdo_salt")

    @anvil.server.server_method
    @classmethod
    def get_value(cls, key):
        """The stored string for a public key, or None when there is no row."""
        if key not in cls.PUBLIC_KEYS:
            raise KeyError(key)
        row = app_tables.setting.get(key=key)
        if row is None:
            return None
        return row["value"]

    @anvil.server.server_method
    @classmethod
    def vdo_config(cls):
        """The origin, profile and salt a join needs, validated on every read.

        A bad stored value raises ValueError naming the key and not the value,
        so a misconfigured setting is visible and never reaches a client.
        """
        origin = cls.get_value("vdo_origin") or vdo.DEFAULT_ORIGIN
        profile = cls.get_value("vdo_profile") or vdo.DEFAULT_PROFILE
        try:
            origin = vdo.normalise_origin(origin)
        except ValueError as err:
            raise ValueError(f"setting vdo_origin is invalid: {err}")
        try:
            profile = vdo.validate_profile(profile)
        except ValueError as err:
            raise ValueError(f"setting vdo_profile is invalid: {err}")
        return {
            "origin": origin,
            "profile": profile,
            "salt": cls.get_value("vdo_salt") or None,
        }
