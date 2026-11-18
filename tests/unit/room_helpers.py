# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""Constants and helpers the room model tests share."""

import datetime

START = datetime.datetime(2026, 11, 18, 12, 0, 0)

PERMANENT_COLUMNS = (
    "slug",
    "vdo_room",
    "title",
    "kind",
    "active",
    "created_by",
    "created",
    "verifier",
    "verifier_salt",
    "kdf_iterations",
    "vdo_password",
    "failed_unlocks",
    "locked_until",
    "updated",
)


def permanent(Room, slug="Acme Board", title="Acme quarterly"):  # noqa: N803
    return Room.create_permanent(slug, title=title)
