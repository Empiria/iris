# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

import datetime

import anvil.server
from anvil.tables import app_tables

from iris.services import passphrase, permissions, slugs, vdo  # pyright: ignore[reportAttributeAccessIssue]
from iris.services.model.setting import Setting

_SLUG_ATTEMPTS = 10

# This many wrong passphrases in a row lock a room's unlock for a while.
UNLOCK_LIMIT = 10
UNLOCK_LOCK_MINUTES = 5

# vdo.ninja passwords run 1 to 49 characters. 24 hex characters is 96 bits.
_VDO_PASSWORD_LENGTH = 24


def _now():
    """The current time, naive and in UTC. Tests patch this."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def _verifier():
    """The server-only `verifier` module, loaded by name when first needed.

    This file loads in the browser too, where `verifier` does not exist, and
    `anvil validate` rejects a static import of it from client_code. Only server
    methods call this, so the browser never reaches it.
    """
    return __import__("iris.verifier", fromlist=["verifier"])


def _vault():
    """The server-only `vault` module, loaded by name when first needed.

    It seals and unseals room passphrases. Same reasons as `_verifier`. Only an
    admin-checked method may call `vault.unseal`.
    """
    return __import__("iris.vault", fromlist=["vault"])


def _in_transaction():
    """`anvil.tables.in_transaction`, loaded when first needed (server only)."""
    return __import__("anvil.tables", fromlist=["tables"]).in_transaction


def _transaction_conflict():
    """The `TransactionConflict` class: raised once Anvil's own retries run out."""
    return __import__("anvil.tables", fromlist=["tables"]).TransactionConflict


def _naive_utc(moment):
    """`moment` as a naive UTC datetime, so stored and current times compare.

    A datetime column can come back timezone-aware, and Python refuses to
    compare an aware time with a naive one.
    """
    offset = moment.utcoffset()
    if offset is None:
        return moment
    return moment.replace(tzinfo=None) - offset


def _normalise_input(passphrase_text):
    """(normalised, None) for a usable input, else (None, reason).

    The reason is "empty" for a non-string or blank input and "incorrect" for
    one over the length cap. Neither is hashed, and no text is carried out.
    """
    if not isinstance(passphrase_text, str):
        return None, "empty"
    try:
        return passphrase.normalise(passphrase_text), None
    except ValueError:
        if len(passphrase_text) > passphrase.MAX_INPUT:
            return None, "incorrect"
        return None, "empty"


def _store_attempts(row, failed, locked_until):
    """Write the failed-unlock count and the lock time on a room row.

    This runs inside a transaction, where `save()` on a buffered row fails: the
    save is itself a transaction and Anvil does not nest them. So the row is
    switched to write-through first, and `update()` then writes at once.
    """
    changes = {"failed_unlocks": failed, "locked_until": locked_until}
    row.buffer_changes(False)
    row.update(**changes)


def _reserve_attempt(slug):
    """Count one unlock attempt on `slug` before its passphrase is checked.

    Server only: never make this a callable.

    Returns {"status": "missing"} or {"status": "throttled"} when the guess
    must be refused, else {"status": "reserved", "record": {...}} with the
    verifier fields to check against. The read, the limit test and the
    write run in one transaction, so parallel guesses each take their own
    slot and cannot together pass UNLOCK_LIMIT. The count goes up here, not
    after the slow hash, and a correct guess clears it again in `_release`.
    """
    in_transaction = _in_transaction()

    def reserve():
        row = app_tables.room.get(slug=slug)
        if row is None or row["active"] is not True or row["kind"] != "permanent":
            return {"status": "missing"}
        now = _now()
        failed = row["failed_unlocks"] or 0
        locked_until = row["locked_until"]
        if locked_until is not None:
            if _naive_utc(locked_until) > now:
                return {"status": "throttled"}
            # The lock has run out: this guess starts a fresh count.
            failed = 0
        failed += 1
        lock = None
        if failed >= UNLOCK_LIMIT:
            lock = now + datetime.timedelta(minutes=UNLOCK_LOCK_MINUTES)
        _store_attempts(row, failed, lock)
        return {
            "status": "reserved",
            "record": {
                "verifier": row["verifier"],
                "verifier_salt": row["verifier_salt"],
                "kdf_iterations": row["kdf_iterations"],
            },
        }

    return in_transaction(reserve)()


def _release(slug, verifier_salt):
    """After a right passphrase: clear the count and return the room's details.

    Server only: never make this a callable.

    None if the room was deleted, deactivated or given a new passphrase
    while the hash ran, so a rotation cannot hand out the old details. The
    details are read here, in the same transaction as the reset.
    """
    in_transaction = _in_transaction()

    def release():
        row = app_tables.room.get(slug=slug)
        if (
            row is None
            or row["active"] is not True
            or row["kind"] != "permanent"
            or row["verifier_salt"] != verifier_salt
        ):
            return None
        _store_attempts(row, 0, None)
        return {
            "vdo_room": row["vdo_room"],
            "password": row["vdo_password"],
            "title": row["title"],
        }

    return in_transaction(release)()


def _summary(row):
    """The fields an admin's room list shows. No secret of the room is in it."""
    return {
        "slug": row["slug"],
        "title": row["title"] or "",
        "kind": row["kind"],
        "created": row["created"],
    }


def _find_room(slug):
    """The row for `slug` (any kind, active or not), or ValueError "No such room."."""
    slug = slugs.normalise(slug) if isinstance(slug, str) else ""
    row = app_tables.room.get(slug=slug) if slugs.looks_like_slug(slug) else None
    if row is None:
        raise ValueError("No such room.")
    return row


def _newest_first(rows):
    """Rows by creation time, newest first, slug order within a tie, undated last."""
    dated = [row for row in rows if row["created"] is not None]
    undated = [row for row in rows if row["created"] is None]
    dated.sort(key=lambda row: row["slug"])
    dated.sort(key=lambda row: _naive_utc(row["created"]), reverse=True)
    undated.sort(key=lambda row: row["slug"])
    return dated + undated


class Room(app_tables.room.Row, buffered=True, attrs=True):
    """A meeting room. Its methods return plain dicts, not rows.

    The `room` table has no client access, so a client could not read a returned
    row. The dict carries only the fields the caller may see.
    """

    @anvil.server.server_method
    @classmethod
    def lookup(cls, slug):
        """Everything a join needs for `slug`, or None.

        Public by design: it is how a meeting link is opened. It returns None
        for a slug no admin created, and for an inactive row, so an
        invented slug releases no vdo_room. A permanent room releases only that
        it exists and is locked: its vdo_room, title and password come out of
        `unlock`, after the passphrase checks.
        """
        slug = slugs.normalise(slug)
        if not slugs.looks_like_slug(slug):
            return None
        row = app_tables.room.get(slug=slug)
        if row is None or row["active"] is not True:
            return None
        if row["kind"] == "permanent":
            return {"kind": "permanent", "locked": True}
        config = Setting.vdo_config()
        return {
            "kind": "one-off",
            "vdo_room": row["vdo_room"],
            "title": row["title"],
            "origin": config["origin"],
            "profile": config["profile"],
            "salt": config["salt"],
        }

    @anvil.server.server_method
    @classmethod
    def create_one_off(cls, title=""):
        """Create a one-off room. Admin only. Returns its slug and title."""
        user = permissions.require_admin()
        slug = None
        for _ in range(_SLUG_ATTEMPTS):
            candidate = slugs.new_one_off_slug()
            if candidate in slugs.RESERVED_SLUGS:
                continue
            if app_tables.room.get(slug=candidate) is None:
                slug = candidate
                break
        if slug is None:
            raise RuntimeError("Could not find a free slug")
        # The table has no uniqueness constraint, so two admins creating links
        # at the same instant could in theory draw the same slug. At 31 ** 8
        # slugs the odds are negligible.
        app_tables.room.add_row(
            slug=slug,
            vdo_room=slugs.new_vdo_room(),
            title=title,
            kind="one-off",
            active=True,
            created_by=user["email"],
            created=_now(),
        )
        return {"slug": slug, "title": title}

    @anvil.server.server_method
    @classmethod
    def create_permanent(cls, slug_text, title=""):
        """Create a permanent room. Admins only.

        Returns the slug, the title and the generated passphrase. The passphrase
        is stored as its slow hash and, encrypted with the app's key, so an
        admin can reveal it later (`reveal_passphrase`). Raises ValueError (slug
        rules, or "That name is taken.") or VaultError (no usable key).
        """
        user = permissions.require_admin()
        slug = slugs.clean_room_slug(slug_text)
        # Duplicates are refused across both kinds of room, and across inactive
        # rows. The table has no uniqueness constraint, so two admins creating
        # the same name at the same instant could both pass; the odds are low
        # and a later list would show both.
        if app_tables.room.get(slug=slug) is not None:
            raise ValueError("That name is taken.")
        phrase = passphrase.generate()
        record = _verifier().hash_passphrase(passphrase.normalise(phrase))
        # Sealed before the row exists: a missing key refuses the creation,
        # rather than leaving a room whose passphrase nobody can read again.
        sealed = _vault().seal(phrase)
        now = _now()
        row = app_tables.room.add_row(
            slug=slug,
            vdo_room=slugs.new_vdo_room(),
            title=title,
            kind="permanent",
            active=True,
            created_by=user["email"],
            created=now,
            updated=now,
            verifier=record["verifier"],
            verifier_salt=record["verifier_salt"],
            kdf_iterations=record["kdf_iterations"],
            passphrase_sealed=sealed,
            vdo_password=slugs.random_string(vdo.HEX_LOWER, _VDO_PASSWORD_LENGTH),
            failed_unlocks=0,
            locked_until=None,  # pyright: ignore[reportArgumentType]
        )
        row.save()
        return {"slug": slug, "title": title, "passphrase": phrase}

    @anvil.server.server_method
    @classmethod
    def unlock(cls, slug, passphrase_text):
        """Check a passphrase for a permanent room and release its join info.

        Public by design: a client without an account unlocks a room here. It
        returns {"ok": True, "found": {...}} on a match, otherwise
        {"ok": False, "reason": ...} with a reason of "missing", "empty",
        "throttled" or "incorrect". The reasons carry no input text. An empty
        input, an oversized one and a locked room return before any hashing, and
        10 wrong attempts in a row lock the room for 5 minutes. Each attempt is
        counted in a transaction before it is hashed, so parallel guesses
        cannot exceed the limit. A room that is unknown, inactive or one-off
        answers "missing" alike.
        """
        slug = slugs.normalise(slug) if isinstance(slug, str) else ""
        if not slugs.looks_like_slug(slug):
            return {"ok": False, "reason": "missing"}
        normalised, refusal = _normalise_input(passphrase_text)
        if refusal is not None:
            return {"ok": False, "reason": refusal}

        try:
            reserved = _reserve_attempt(slug)
        except _transaction_conflict():
            # Too many writers at once, even after Anvil's own retries. Fail
            # closed: refuse the guess without hashing it.
            return {"ok": False, "reason": "throttled"}
        if reserved["status"] != "reserved":
            return {"ok": False, "reason": reserved["status"]}

        if not _verifier().check_passphrase(normalised, reserved["record"]):
            # The miss was counted when the attempt was reserved.
            return {"ok": False, "reason": "incorrect"}

        try:
            found = _release(slug, reserved["record"]["verifier_salt"])
        except _transaction_conflict():
            return {"ok": False, "reason": "throttled"}
        if found is None:
            return {"ok": False, "reason": "incorrect"}
        config = Setting.vdo_config()
        found.update(
            origin=config["origin"],
            profile=config["profile"],
            salt=config["salt"],
            kind="permanent",
        )
        return {"ok": True, "found": found}

    @anvil.server.server_method
    @classmethod
    def list_for_admin(cls):
        """Every room, newest first, as plain summaries. Admins only.

        Each summary has the slug, title, kind and creation time. The vdo room,
        vdo password and verifier never leave the server.
        """
        permissions.require_admin()
        return [_summary(row) for row in _newest_first(list(app_tables.room.search()))]

    @anvil.server.server_method
    @classmethod
    def update_title(cls, slug, title):
        """Change a room's title. Admins only. The slug stays as it is."""
        permissions.require_admin()
        row = _find_room(slug)
        if not isinstance(title, str):
            raise ValueError("Title must be text")
        row.update(title=title, updated=_now())
        row.save()
        return _summary(row)

    @anvil.server.server_method
    @classmethod
    def remove(cls, slug):
        """Delete a room for good. Admins only. Its link stops working."""
        permissions.require_admin()
        row = _find_room(slug)
        row_slug = row["slug"]
        row.delete()
        return {"slug": row_slug}

    @anvil.server.server_method
    @classmethod
    def rotate(cls, slug):
        """Give a permanent room a new passphrase. Admins only.

        The vdo room and vdo password are replaced too, so a person holding the
        old details is out of the room, and any lock is cleared. The new
        passphrase is returned, and stored encrypted for `reveal_passphrase`
        beside its slow hash. Raises VaultError when there is no usable key.
        """
        permissions.require_admin()
        row = _find_room(slug)
        if row["kind"] != "permanent":
            raise ValueError("Only permanent rooms have a passphrase.")
        phrase = passphrase.generate()
        record = _verifier().hash_passphrase(passphrase.normalise(phrase))
        sealed = _vault().seal(phrase)
        row.update(
            passphrase_sealed=sealed,
            verifier=record["verifier"],
            verifier_salt=record["verifier_salt"],
            kdf_iterations=record["kdf_iterations"],
            vdo_room=slugs.new_vdo_room(),
            vdo_password=slugs.random_string(vdo.HEX_LOWER, _VDO_PASSWORD_LENGTH),
            failed_unlocks=0,
            locked_until=None,  # pyright: ignore[reportArgumentType]
            updated=_now(),
        )
        row.save()
        return {"slug": row["slug"], "passphrase": phrase}

    @anvil.server.server_method
    @classmethod
    def reveal_passphrase(cls, slug):
        """A permanent room's passphrase, decrypted. Admins only.

        {"status": "ok", "passphrase": ...} for a room that stored one, and
        {"status": "none"} for a room made before passphrases were stored, which
        only a rotation can fix. A one-off or unknown room raises ValueError.
        A missing key or an undecryptable value raises VaultError, whose
        message is safe to show. The admin check comes first, so a caller who
        is not an admin gets nothing, not even whether the room exists.
        """
        permissions.require_admin()
        row = _find_room(slug)
        if row["kind"] != "permanent":
            raise ValueError("Only permanent rooms have a passphrase.")
        sealed = row["passphrase_sealed"]
        if not sealed:
            return {"status": "none"}
        return {"status": "ok", "passphrase": _vault().unseal(sealed)}
