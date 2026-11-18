# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Empiria

"""S2: what do &salt, &password and &hash do on the live vdo.ninja build?

Standalone: no Anvil app and no stack. Run it with

    uv run python tools/spikes/vdo_hash/probe.py

It prints `Live build: ...` and then one line per case:

    S2a PASS|FAIL|OBSERVED <evidence>

and exits 0 once every case has run, whatever the verdicts. The origin comes from
IRIS_VDO_ORIGIN (default https://vdo.ninja).

Public vdo.ninja signalling is shared, so every room is `irisspike` plus random
letters, the media is Chromium's fake device, each peer lives under a minute, and
each case runs once. The only password used is the made-up PASSWORD below.

How the room id is observed: vdo.ninja does not keep the hashed id in a global, it
sends it in the signalling `joinroom` frame. The probe records the websocket frames
the page sends and reads `roomid` from them, then compares that with its own
`generate_hash` result.
"""

import json
import os
import random
import re
import string
import sys
from pathlib import Path
from urllib.parse import quote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import LOAD_TIMEOUT_MS, http_get  # noqa: E402

NEEDS_STACK = False

DEFAULT_SALT = "vdo.ninja"
PASSWORD = "irisSpikePw1"
OTHER_PASSWORD = "irisSpikePw2"
CUSTOM_SALT = "iris-test"
EXPECTED_BUILD = "31.1"
PEER_SECONDS = 40
ROOMID = re.compile(r'"roomid"\s*:\s*"([0-9a-f]+)"')
CHROMIUM_ARGS = [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
]


def generate_hash(text: str, length: int = 0) -> str:
    """vdo.ninja's generateHash: SHA-256, hex, cut to length // 2 bytes."""
    import hashlib

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    if length:
        digest = digest[: length // 2]
    return digest.hex()


def room_id(room: str, password: str, salt: str, token: str = "") -> str:
    """The signalling room id: generateHash(room + password + salt + token, 16)."""
    return generate_hash(room + password + salt + token, 16)


def password_hash(password: str, salt: str, length: int = 4) -> str:
    """The value for &hash: the first `length` (4 to 6) hex digits of
    generateHash(password + salt, 6)."""
    return generate_hash(password + salt, 6)[:length]


def random_room() -> str:
    letters = "".join(random.choice(string.ascii_lowercase) for _ in range(10))
    return "irisspike" + letters


def build_url(
    origin: str,
    room: str,
    password=None,
    salt=None,
    hash_value=None,
    password_in_fragment=False,
    join=True,
) -> str:
    """A vdo.ninja URL. The password goes in the fragment when asked, else the
    query. `join` adds the params that join the room straight away with the
    fake camera."""
    query = [f"room={quote(room)}"]
    fragment = []
    if password is not None:
        (fragment if password_in_fragment else query).append(
            f"password={quote(password)}"
        )
    if salt is not None:
        query.append(f"salt={quote(salt)}")
    if hash_value is not None:
        query.append(f"hash={quote(hash_value)}")
    if join:
        query += ["webcam", "autostart", "label=Spike"]
    url = f"{origin.rstrip('/')}/?{'&'.join(query)}"
    return url + (f"#{'&'.join(fragment)}" if fragment else "")


def room_ids_in(frames) -> list:
    """The distinct `roomid` values found in websocket frames, in order."""
    found = []
    for frame in frames:
        for value in ROOMID.findall(frame if isinstance(frame, str) else ""):
            if value not in found:
                found.append(value)
    return found


def format_line(case: str, verdict: str, evidence: str) -> str:
    return f"{case} {verdict} {' '.join(str(evidence).split())}"


def build_of(text: str):
    """The build version in a page or script, or None."""
    match = re.search(r"""session\.version\s*=\s*["']([0-9][0-9.]*)["']""", text)
    return match.group(1) if match else None


def _origin() -> str:
    return os.environ.get("IRIS_VDO_ORIGIN", "https://vdo.ninja").rstrip("/")


def _proxy():
    """The environment's proxy as a Playwright dict. Credentials in the proxy URL
    have to be passed as separate fields."""
    raw = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if not raw:
        return None
    parts = urlparse(raw)
    proxy = {"server": f"{parts.scheme}://{parts.hostname}:{parts.port}"}
    if parts.username:
        proxy["username"] = parts.username
        proxy["password"] = parts.password or ""
    return proxy


class Peer:
    """One browser context and page on a vdo.ninja URL, with its signalling
    frames recorded."""

    def __init__(self, browser, url: str):
        self.url = url
        self.frames: list = []
        self.sockets: list = []
        self.context = browser.new_context(permissions=["camera", "microphone"])
        self.page = self.context.new_page()
        self.errors: list = []
        self.page.on("websocket", self._socket)
        self.page.on(
            "pageerror", lambda e: self.errors.append(f"pageerror {str(e)[:120]}")
        )

    def _socket(self, ws):
        self.sockets.append(ws.url)
        ws.on("framesent", lambda payload: self.frames.append(str(payload)))

    def open(self):
        self.page.goto(self.url, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT_MS)
        self.page.wait_for_function(
            "typeof session !== 'undefined' && !!session.salt",
            timeout=LOAD_TIMEOUT_MS,
        )
        return self

    def settle(self, ms: int = 6000):
        self.page.wait_for_timeout(ms)

    def read(self, expression: str):
        return self.page.evaluate(expression)

    def room_ids(self) -> list:
        return room_ids_in(self.frames)

    def peers(self) -> int:
        return self.read(
            "typeof session !== 'undefined' && session.rpcs"
            " ? Object.keys(session.rpcs).length : -1"
        )

    def states(self) -> list:
        """The WebRTC connection state of each remote peer."""
        return self.read(
            "typeof session !== 'undefined' && session.rpcs"
            " ? Object.values(session.rpcs).map(r => r.connectionState) : []"
        )

    def close(self):
        self.context.close()


def _row(case, verdict, evidence):
    return (case, verdict, evidence)


def _error(case, exc):
    return _row(
        case,
        "FAIL",
        f"could not run: {type(exc).__name__}: {str(exc).splitlines()[0][:240]}",
    )


def live_build(origin: str):
    """(version, source) of the live build: the page's session.version string."""
    status, _headers, body = http_get(f"{origin}/", timeout=60)
    version = build_of(body)
    return version, f"{origin}/ status {status}"


def case_a(browser, origin):
    room = random_room()
    peer = Peer(browser, build_url(origin, room, PASSWORD)).open()
    try:
        peer.settle()
        salt = peer.read("session.salt")
        ids = peer.room_ids()
        want = room_id(room, PASSWORD, DEFAULT_SALT)
        evidence = (
            f"session.salt = {salt!r}; joinroom roomid {ids}; "
            f"generate_hash(room+password+'vdo.ninja', 16) = {want}"
        )
        ok = salt == DEFAULT_SALT and want in ids
        return _row("S2a", "PASS" if ok else "FAIL", evidence), ids
    finally:
        peer.close()


def case_b(browser, origin, default_ids):
    room = random_room()
    peer = Peer(browser, build_url(origin, room, PASSWORD, salt=CUSTOM_SALT)).open()
    try:
        peer.settle()
        salt = peer.read("session.salt")
        ids = peer.room_ids()
        want = room_id(room, PASSWORD, CUSTOM_SALT)
        stale = room_id(room, PASSWORD, DEFAULT_SALT)
        evidence = (
            f"session.salt = {salt!r}; joinroom roomid {ids}; with salt "
            f"{CUSTOM_SALT!r} expected {want}, with the default salt it would "
            f"have been {stale} (S2a rooms differ by room name: {default_ids})"
        )
        ok = salt == CUSTOM_SALT and want in ids and stale not in ids
        return _row("S2b", "PASS" if ok else "FAIL", evidence)
    finally:
        peer.close()


def case_c(browser, origin):
    room = random_room()
    url = build_url(origin, room, PASSWORD, password_in_fragment=True)
    peer = Peer(browser, url).open()
    try:
        peer.settle()
        password = peer.read("session.password")
        prompt = peer.read(
            "Array.from(document.querySelectorAll('dialog, .promptModal, "
            "#promptAlt, .modal')).filter(e => e.offsetParent !== null).length"
        )
        ids = peer.room_ids()
        want = room_id(room, PASSWORD, DEFAULT_SALT)
        evidence = (
            f"url ...#password=<made-up> ; session.password = {password!r}; "
            f"visible prompts {prompt}; joinroom roomid {ids}, expected {want}"
        )
        ok = password == PASSWORD and want in ids
        return _row("S2c", "PASS" if ok else "FAIL", evidence)
    finally:
        peer.close()


def _wait_peers(peers, seconds: int) -> list:
    counts = [p.peers() for p in peers]
    waited = 0
    while waited < seconds * 1000 and not all(c > 0 for c in counts):
        peers[0].page.wait_for_timeout(2000)
        waited += 2000
        counts = [p.peers() for p in peers]
    return counts


def case_d_and_f(browser, origin):
    """S2d: same room and password, two peers. S2f: a third peer with a wrong
    password and no &hash, in the same room."""
    room = random_room()
    rows = []
    a = b = c = None
    try:
        a = Peer(
            browser, build_url(origin, room, PASSWORD, password_in_fragment=True)
        ).open()
        b = Peer(
            browser, build_url(origin, room, PASSWORD, password_in_fragment=True)
        ).open()
        counts = _wait_peers([a, b], PEER_SECONDS)
        same_ids = a.room_ids() == b.room_ids() and bool(a.room_ids())
        sockets = sorted(set(a.sockets))
        states = [a.states(), b.states()]
        for _ in range(8):
            if all("connected" in st for st in states):
                break
            a.page.wait_for_timeout(2000)
            states = [a.states(), b.states()]
        linked = all("connected" in st for st in states)
        verdict = "PASS" if linked else "OBSERVED"
        rows.append(
            _row(
                "S2d",
                verdict,
                f"same room and password: remote peer counts {counts}, WebRTC "
                f"connection states {states}; both sent "
                f"the same roomid {a.room_ids()} = {same_ids}; signalling {sockets}. "
                "A remote peer count above 0 means signalling put the two peers "
                "in one room. A connection state other than 'connected' means no "
                "WebRTC link formed, which a network with no UDP route explains; "
                "it says nothing about the password.",
            )
        )
        c = Peer(
            browser, build_url(origin, room, OTHER_PASSWORD, password_in_fragment=True)
        ).open()
        c.settle(8000)
        text = " ".join(c.read("document.body.innerText").split())[:200]
        prompt = c.read(
            "(function(){var e=document.getElementById('request_info_prompt');"
            "return e ? (e.style.display + ':' + e.innerText.trim()) : null;})()"
        )
        different = c.room_ids() != a.room_ids() and bool(c.room_ids())
        counts_after = [a.peers(), c.peers()]
        rows.append(
            _row(
                "S2f",
                "OBSERVED",
                f"wrong password, no &hash: wrong-password peer roomid "
                f"{c.room_ids()} vs correct {a.room_ids()} (different = "
                f"{different}); remote peer counts [correct peer, wrong peer] "
                f"{counts_after}; request_info_prompt {prompt!r}; page text "
                f"{text!r}; tainted {c.read('session.taintedSession')!r}",
            )
        )
    except Exception as exc:
        done = {r[0] for r in rows}
        rows += [_error(x, exc) for x in ("S2d", "S2f") if x not in done]
    finally:
        for peer in (a, b, c):
            if peer:
                peer.close()
    return rows


def case_e(browser, origin):
    room = random_room()
    good = password_hash(PASSWORD, DEFAULT_SALT)
    bad = "0000" if good != "0000" else "ffff"
    seen = []
    for label, value in (("correct", good), ("wrong", bad)):
        peer = Peer(browser, build_url(origin, room, PASSWORD, hash_value=value)).open()
        try:
            peer.settle(8000)
            prompt = peer.read(
                "(function(){var e=document.getElementById('request_info_prompt');"
                "return e ? (e.style.display + ':' + e.innerText.trim()) : null;})()"
            )
            seen.append(
                f"{label} &hash={value}: taintedSession "
                f"{peer.read('session.taintedSession')!r}; "
                f"request_info_prompt {prompt!r}; joinroom roomid {peer.room_ids()}; "
                f"remote peers {peer.peers()}"
            )
        finally:
            peer.close()
    return _row("S2e", "OBSERVED", "; ".join(seen))


def run(base_url=""):
    origin = _origin()
    rows = []
    try:
        version, source = live_build(origin)
    except Exception as exc:
        return [
            _row(
                "S2a",
                "FAIL",
                f"could not fetch {origin}/: {type(exc).__name__}: {exc}",
            )
        ]
    rows.append(("Live build", "", f"{version} ({source}); research read 31.1"))
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            kwargs = {"args": CHROMIUM_ARGS}
            proxy = _proxy()
            if proxy:
                kwargs["proxy"] = proxy
            browser = p.chromium.launch(**kwargs)
            try:
                row_a, ids = case_a(browser, origin)
                rows.append(row_a)
                rows.append(case_b(browser, origin, ids))
                rows.append(case_c(browser, origin))
                rows += case_d_and_f(browser, origin)
                rows.append(case_e(browser, origin))
            finally:
                browser.close()
    except Exception as exc:
        done = {r[0] for r in rows}
        rows += [
            _error(c, exc)
            for c in ("S2a", "S2b", "S2c", "S2d", "S2e", "S2f")
            if c not in done
        ]
    return rows


def main() -> int:
    rows = run()
    for case, verdict, evidence in rows:
        if case == "Live build":
            print(f"Live build: {evidence}")
        else:
            print(format_line(case, verdict, evidence), flush=True)
    print(json.dumps({"cases": [r[0] for r in rows]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
