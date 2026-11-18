#!/usr/bin/env python3
"""Find the local stack's URL. The stack never uses a fixed host port.

`just up` publishes the app on a free loopback port it picks each time it creates
the container (`-p 127.0.0.1:<port>:3030`, with `--origin http://localhost:<port>`
so the page's asset and websocket URLs match) and writes the resolved URL to the
git-ignored `.anvil/stack-url`. Everything
else (`just seed`, `just e2e`, `just create-staff`, a bare `pytest tests/e2e`,
`tools/dev_seed.py`) reads it back here. Precedence, first match wins:

1. `IRIS_URL`, to point at another stack.
2. `.anvil/stack-url`.

If neither exists the error says how to start a stack. Standard library only, so
the other tools can import it and `python3 tools/stack_url.py` runs anywhere.

    python3 tools/stack_url.py              print the app URL
    python3 tools/stack_url.py uplink       print the uplink URL
    python3 tools/stack_url.py free-port    print a free loopback port
    python3 tools/stack_url.py refresh CTR  ask podman for CTR's published port,
                                            write .anvil/stack-url, print the URL
    python3 tools/stack_url.py clear        remove .anvil/stack-url

`refresh` fails quietly (exit 1, no file change) when podman can't answer, so a
recipe can try it and fall back to the file.
"""

import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
URL_FILE = ROOT / ".anvil" / "stack-url"

# The port the app listens on inside the container. Never the host port.
CONTAINER_PORT = 3030

NO_STACK = (
    "no stack URL: start the stack with 'just up' (it writes .anvil/stack-url), "
    "or set IRIS_URL to point at another stack"
)


class NoStack(ValueError):
    """There is no IRIS_URL and no stack-url file."""


def base_url(environ=None, url_file=None):
    """The app URL, with a trailing slash. Raises NoStack when there is none."""
    environ = os.environ if environ is None else environ
    url_file = URL_FILE if url_file is None else Path(url_file)
    text = (environ.get("IRIS_URL") or "").strip()
    if not text and url_file.is_file():
        text = url_file.read_text().strip()
    if not text:
        raise NoStack(NO_STACK)
    return text if text.endswith("/") else text + "/"


def uplink_url(environ=None, url_file=None):
    """The uplink URL: IRIS_UPLINK_URL, else the app URL's host with ws://."""
    environ = os.environ if environ is None else environ
    explicit = (environ.get("IRIS_UPLINK_URL") or "").strip()
    if explicit:
        return explicit
    parts = urlparse(base_url(environ, url_file))
    scheme = "wss" if parts.scheme == "https" else "ws"
    return f"{scheme}://{parts.netloc}/_/uplink"


def free_port():
    """A free loopback port. `just up` needs it before the container exists,
    because the app's --origin has to name the port the browser will use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def parse_published_port(text):
    """The host port from `podman port CTR 3030` output such as `127.0.0.1:41234`."""
    for line in text.splitlines():
        found = re.search(r":(\d{1,5})\s*$", line.strip())
        if found and 1 <= int(found.group(1)) <= 65535:
            return int(found.group(1))
    raise ValueError(f"no published port in {text!r}")


def published_port(container):
    """Ask podman for the host port the container's app port is published on."""
    result = subprocess.run(
        ["podman", "port", container, f"{CONTAINER_PORT}/tcp"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "podman port failed")
    return parse_published_port(result.stdout)


def write_url(port, url_file=None):
    """Record the stack's URL for the other tools. Returns the URL."""
    url_file = URL_FILE if url_file is None else Path(url_file)
    url = f"http://localhost:{int(port)}/"
    url_file.parent.mkdir(parents=True, exist_ok=True)
    url_file.write_text(url + "\n")
    return url


def main(argv):
    command = argv[1] if len(argv) > 1 else "url"
    try:
        if command == "url":
            print(base_url())
        elif command == "free-port":
            print(free_port())
        elif command == "uplink":
            print(uplink_url())
        elif command == "refresh" and len(argv) == 3:
            print(write_url(published_port(argv[2])))
        elif command == "clear":
            URL_FILE.unlink(missing_ok=True)
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except NoStack as error:
        print(f"stack_url: {error}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"stack_url: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
