# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import anvil.server
from anvil.tables import app_tables

from iris.services import permissions, vdo  # pyright: ignore[reportAttributeAccessIssue]


class Setting(app_tables.setting.Row, buffered=True, attrs=True):
    """A deployment setting. Only the vdo.ninja keys are readable by callers."""

    # Everything these keys hold is released to anyone with a valid meeting
    # link anyway, so reading them is public by design.
    PUBLIC_KEYS = ("vdo_origin", "vdo_profile", "vdo_salt", "vdo_profile_extra_keys")

    # Upper bound on a profile admin may save. It stops an absurd paste being
    # stored, and is checked before any validation work.
    MAX_PROFILE_LENGTH = 2000

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

    @classmethod
    def _extra_keys(cls):
        """Extra allowed profile keys from the optional comma-separated
        vdo_profile_extra_keys setting. Never read by a client."""
        return vdo.parse_extra_keys(cls.get_value("vdo_profile_extra_keys"))

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
            profile = vdo.validate_profile(profile, cls._extra_keys())
        except ValueError as err:
            raise ValueError(f"setting vdo_profile is invalid: {err}")
        return {
            "origin": origin,
            "profile": profile,
            "salt": cls.get_value("vdo_salt") or None,
        }

    @anvil.server.server_method
    @classmethod
    def get_profile(cls):
        """The stored vdo.ninja profile text as saved, or "". Admin only."""
        permissions.require_admin()
        row = app_tables.setting.get(key="vdo_profile")
        if row is None:
            return ""
        return row["value"] or ""

    @anvil.server.server_method
    @classmethod
    def set_profile(cls, text):
        """Validate and store the vdo.ninja profile. Admin only.

        Returns the normalised profile that was stored. An invalid profile
        raises ValueError with the validator's message and changes nothing.
        The empty profile is allowed and means plain vdo.ninja.
        """
        permissions.require_admin()
        if not isinstance(text, str):
            raise ValueError("The settings must be text.")
        if len(text) > cls.MAX_PROFILE_LENGTH:
            raise ValueError(
                "The settings are too long (at most "
                + str(cls.MAX_PROFILE_LENGTH)
                + " characters)."
            )
        profile = vdo.validate_profile(text, cls._extra_keys())
        row = app_tables.setting.get(key="vdo_profile")
        if row is None:
            app_tables.setting.add_row(key="vdo_profile", value=profile)
        else:
            row.update(value=profile)
            row.save()
        return profile
