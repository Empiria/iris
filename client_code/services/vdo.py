# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""vdo.ninja origin and join URL rules.

This module imports nothing, so it runs in Skulpt and CPython alike and needs
no standard-library URL helpers. Every profile read and every URL build goes
through it, so a profile that forces relaying or meshcast can neither be stored
and used nor built into a URL.
"""

# The origin used when the vdo_origin setting has no row.
DEFAULT_ORIGIN = "https://vdo.ninja"

# The parameter profile used when the vdo_profile setting has no row. Empty on
# purpose: that is vdo.ninja's own defaults. A deployment's profile lives in
# the `setting` table, never here. Change this one value to change the default.
DEFAULT_PROFILE = ""

# Parameters that force relaying or change the media path. Lower-cased and
# percent-decoded before the check. Read from the vdo.ninja develop main.js on
# 2026-11-18, confidence MEDIUM until the S6c spike (plan 02-01) prints the
# live list. Widen these lists to widen the refusal; no code change is needed.
# A key that starts with one of these prefixes is refused.
DENY_PREFIXES = ("meshcast", "relay")
# A key that equals one of these is refused. `turn`, `stun` and `nomeshcast`
# are allowed.
DENY_NAMES = ("privacy", "private", "icefilter", "tcp")

# Parameters Iris sets itself, so a stored profile cannot redirect a join to
# another room or label. The short aliases are assumed from vdo.ninja habit;
# over-refusing a key is the safe direction.
RESERVED_NAMES = (
    "room",
    "r",
    "roomid",
    "label",
    "l",
    "salt",
    "hash",
    "h",
    "password",
    "pw",
    "p",
)

_HEX_LOWER = "0123456789abcdef"
_HEX_UPPER = "0123456789ABCDEF"
_UNRESERVED = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
_HOST_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789.-"
_DIGITS = "0123456789"
_LOCAL_HOSTS = ("localhost", "127.0.0.1")


def _unquote_once(text):
    out = []
    i = 0
    size = len(text)
    while i < size:
        ch = text[i]
        if ch == "%" and i + 2 < size:
            high = _HEX_LOWER.find(text[i + 1].lower())
            low = _HEX_LOWER.find(text[i + 2].lower())
            if high >= 0 and low >= 0 and high * 16 + low < 128:
                out.append(chr(high * 16 + low))
                i += 3
                continue
        out.append(ch)
        i += 1
    return "".join(out)


def unquote(text):
    """Decode `%XX` escapes that give ASCII, repeatedly until nothing changes.

    Escapes that are not ASCII, and malformed ones, are left as written.
    Decoding to a fixpoint stops double encoding hiding a denied key.
    """
    for _ in range(8):
        decoded = _unquote_once(text)
        if decoded == text:
            break
        text = decoded
    return text


def _utf8_bytes(code):
    if code < 0x80:
        return [code]
    if code < 0x800:
        return [0xC0 | (code >> 6), 0x80 | (code & 0x3F)]
    if code < 0x10000:
        return [
            0xE0 | (code >> 12),
            0x80 | ((code >> 6) & 0x3F),
            0x80 | (code & 0x3F),
        ]
    return [
        0xF0 | (code >> 18),
        0x80 | ((code >> 12) & 0x3F),
        0x80 | ((code >> 6) & 0x3F),
        0x80 | (code & 0x3F),
    ]


def quote(text):
    """Percent-encode everything except `A-Z a-z 0-9 - . _ ~`.

    Same result as the standard library quote with no safe characters. It works
    by arithmetic on `ord` with no `encode` call, so it runs in Skulpt.
    """
    out = []
    chars = list(text)
    i = 0
    while i < len(chars):
        ch = chars[i]
        i += 1
        if ch in _UNRESERVED:
            out.append(ch)
            continue
        code = ord(ch)
        # Skulpt strings are UTF-16: join a surrogate pair into one code point.
        if 0xD800 <= code < 0xDC00 and i < len(chars):
            low = ord(chars[i])
            if 0xDC00 <= low < 0xE000:
                code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                i += 1
        out.extend(
            "%" + _HEX_UPPER[byte >> 4] + _HEX_UPPER[byte & 15]
            for byte in _utf8_bytes(code)
        )
    return "".join(out)


def profile_keys(profile):
    """The raw parameter names in a profile, in order."""
    return [part.split("=", 1)[0] for part in (profile or "").split("&") if part]


def _decoded_name(raw_key):
    name = unquote(raw_key).strip().lower()
    return name.split("=", 1)[0].strip()


def _denied(name):
    if name in DENY_NAMES:
        return True
    return any(name.startswith(prefix) for prefix in DENY_PREFIXES)


def validate_profile(profile):
    """Return the profile normalised, or raise ValueError.

    Normalising drops a leading `?` and empty segments. The error names the
    offending key and never repeats a value.
    """
    if profile is None:
        return ""
    text = str(profile)
    for ch in text:
        code = ord(ch)
        if code < 33 or code > 126 or ch == "#":
            raise ValueError("profile has a character that is not allowed")
    parts = [part for part in text.lstrip("?").split("&") if part]
    for part in parts:
        name = _decoded_name(part.split("=", 1)[0])
        if _denied(name):
            raise ValueError(f"profile parameter '{name}' is not allowed")
        if name in RESERVED_NAMES:
            raise ValueError(f"profile parameter '{name}' is set by Iris")
    return "&".join(parts)


def _valid_port(port):
    return 0 < len(port) <= 5 and all(ch in _DIGITS for ch in port)


def _valid_host(host):
    if not host or host[0] in ".-" or host[-1] in ".-":
        return False
    if ".." in host:
        return False
    return all(ch in _HOST_CHARS for ch in host)


def _split_scheme(text):
    if text.startswith("https://"):
        return "https", text[8:]
    if text.startswith("http://"):
        return "http", text[7:]
    raise ValueError("origin must start with https://")


def _split_host_port(rest):
    if rest.endswith("/"):
        rest = rest[:-1]
    if "/" in rest:
        raise ValueError("origin must not have a path")
    host = rest
    port = ""
    if ":" in rest:
        host, port = rest.split(":", 1)
        if not _valid_port(port):
            raise ValueError("origin has a bad port")
    if not _valid_host(host):
        raise ValueError("origin has a bad host")
    return host, port


def normalise_origin(origin):
    """Return `scheme://host[:port]`, lower-cased, or raise ValueError.

    https only. http is allowed for localhost and 127.0.0.1. Userinfo, a path,
    a query, a fragment, backslashes and whitespace are refused.
    """
    if not isinstance(origin, str) or not origin:
        raise ValueError("origin is empty")
    text = origin.lower()
    for ch in text:
        if ord(ch) <= 32 or ord(ch) == 127 or ch in "@?#\\":
            raise ValueError("origin has a character that is not allowed")
    scheme, rest = _split_scheme(text)
    host, port = _split_host_port(rest)
    if scheme == "http" and host not in _LOCAL_HOSTS:
        raise ValueError("origin must be https unless it is localhost")
    return scheme + "://" + host + (":" + port if port else "")


_PASSWORD_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_PASSWORD_MAX = 49


def _valid_password(password):
    """True for 1 to 49 ASCII letters and digits, the shape Iris generates."""
    if not isinstance(password, str) or not 1 <= len(password) <= _PASSWORD_MAX:
        return False
    return all(ch in _PASSWORD_CHARS for ch in password)


def build_join_url(
    origin, vdo_room, profile, name, salt=None, password=None, in_fragment=False
):
    """Build the vdo.ninja URL for one participant.

    The origin and profile are revalidated here, so no caller can bypass them.
    With `in_fragment` the room, label, password and salt go after `#`, so the
    vdo.ninja host never receives them in a request, and the profile stays in
    the query. A password is only ever placed in the fragment: asking for one
    with `in_fragment` off raises ValueError, as does a password that is not 1
    to 49 letters and digits. The error text never carries the password.
    """
    base = normalise_origin(origin)
    clean = validate_profile(profile)
    if not vdo_room:
        raise ValueError("vdo_room is empty")
    if password is not None:
        if not _valid_password(password):
            raise ValueError("password must be 1 to 49 letters and digits")
        if not in_fragment:
            raise ValueError("a password can only go in the fragment")
    identity = ["room=" + quote(vdo_room), "label=" + quote(name or "")]
    if in_fragment:
        if password:
            identity.append("password=" + password)
        if salt:
            identity.append("salt=" + quote(salt))
        query = "?" + clean if clean else ""
        return base + "/" + query + "#" + "&".join(identity)
    parts = identity + ([clean] if clean else [])
    if salt:
        parts.append("salt=" + quote(salt))
    return base + "/?" + "&".join(parts)
