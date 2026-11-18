"""tools/stack_url.py: how the tools find the local stack, which has no fixed port."""

import pytest


@pytest.fixture
def stack_url(load_tool):
    return load_tool("stack_url")


@pytest.fixture
def url_file(tmp_path):
    path = tmp_path / ".anvil" / "stack-url"
    path.parent.mkdir()
    return path


def test_iris_url_wins_over_the_file(stack_url, url_file):
    url_file.write_text("http://localhost:41234/\n")
    env = {"IRIS_URL": "http://localhost:50000/"}
    assert stack_url.base_url(env, url_file) == "http://localhost:50000/"


def test_the_file_is_used_without_iris_url(stack_url, url_file):
    url_file.write_text("http://localhost:41234/\n")
    assert stack_url.base_url({}, url_file) == "http://localhost:41234/"


def test_a_missing_slash_is_added(stack_url, url_file):
    assert stack_url.base_url({"IRIS_URL": "http://localhost:50000"}, url_file) == (
        "http://localhost:50000/"
    )


def test_neither_source_is_a_clear_error(stack_url, url_file):
    with pytest.raises(stack_url.NoStack) as caught:
        stack_url.base_url({}, url_file)
    assert "just up" in str(caught.value)
    assert "IRIS_URL" in str(caught.value)


def test_an_empty_file_is_no_stack(stack_url, url_file):
    url_file.write_text("\n")
    with pytest.raises(stack_url.NoStack):
        stack_url.base_url({}, url_file)


def test_there_is_no_default_port(stack_url, url_file):
    with pytest.raises(stack_url.NoStack):
        stack_url.uplink_url({}, url_file)


def test_the_uplink_url_follows_the_app_url(stack_url, url_file):
    url_file.write_text("http://localhost:41234/\n")
    assert stack_url.uplink_url({}, url_file) == "ws://localhost:41234/_/uplink"
    secure = {"IRIS_URL": "https://iris.example.com/"}
    assert stack_url.uplink_url(secure, url_file) == "wss://iris.example.com/_/uplink"


def test_an_explicit_uplink_url_wins(stack_url, url_file):
    env = {"IRIS_UPLINK_URL": "ws://localhost:4000/_/uplink"}
    assert stack_url.uplink_url(env, url_file) == "ws://localhost:4000/_/uplink"


@pytest.mark.parametrize(
    "text, port",
    [
        ("127.0.0.1:41234\n", 41234),
        ("127.0.0.1:41234\n[::1]:41234\n", 41234),
        ("0.0.0.0:3030", 3030),
    ],
)
def test_the_published_port_is_read_from_podman_port(stack_url, text, port):
    assert stack_url.parse_published_port(text) == port


@pytest.mark.parametrize("text", ["", "no ports here", "127.0.0.1:99999"])
def test_podman_port_output_without_a_port_is_refused(stack_url, text):
    with pytest.raises(ValueError):
        stack_url.parse_published_port(text)


def test_write_url_makes_the_directory_and_records_a_loopback_url(stack_url, tmp_path):
    target = tmp_path / "deep" / "stack-url"
    assert stack_url.write_url(41234, target) == "http://localhost:41234/"
    assert target.read_text() == "http://localhost:41234/\n"
