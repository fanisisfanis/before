import os
import socket
from pathlib import Path

import pytest

from before.collect import (
    capture,
    proxy_endpoint,
    read_hosts,
    read_path,
    read_proxy,
    resolve_command,
    safe_proxy,
    valid_command,
)


@pytest.mark.parametrize(
    "value",
    [
        "http://alice:supersecret@proxy.test:8080",
        "alice:supersecret@proxy.test:8080",
        "http=alice:supersecret@proxy.test:80;https=bob:othersecret@proxy.test:443",
        "https://proxy.test:8080/?token=supersecret",
    ],
)
def test_proxy_credentials_and_tokens_are_not_saved(value):
    sanitized = safe_proxy(value)
    assert "supersecret" not in sanitized
    assert "othersecret" not in sanitized
    assert "alice" not in sanitized


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("127.0.0.1:7890", ("127.0.0.1", 7890)),
        ("http=127.0.0.1:80;https=127.0.0.1:443", ("127.0.0.1", 443)),
        ("http://[::1]:8080", ("::1", 8080)),
        ("socks5://localhost:1080", ("localhost", 1080)),
        ("http://user:pass@host:80", None),
        ("host:9999999", None),
    ],
)
def test_proxy_endpoint_parser(value, expected):
    assert proxy_endpoint(value) == expected


def test_hosts_comments_are_not_changes(tmp_path):
    path = tmp_path / "hosts"
    path.write_text("127.0.0.1 localhost\n# a comment\n", encoding="utf-8")
    first = read_hosts(path)
    path.write_text("# new comment\n127.0.0.1   localhost  # comment\n", encoding="utf-8")
    assert first.data == read_hosts(path).data


def test_hosts_retains_multiple_addresses(tmp_path):
    path = tmp_path / "hosts"
    path.write_text("127.0.0.1 localhost\n::1 localhost\n", encoding="utf-8")
    assert read_hosts(path).data["entries"]["localhost"] == "127.0.0.1, ::1"


def test_unreadable_hosts_is_unknown(tmp_path):
    assert read_hosts(tmp_path / "missing").status == "unavailable"


def test_command_resolution_is_read_only(tmp_path):
    executable = tmp_path / ("example.exe" if os.name == "nt" else "example")
    executable.write_text("this is deliberately not executable code", encoding="utf-8")
    executable.chmod(0o700)
    assert resolve_command("example", [{"value": str(tmp_path)}]) == str(executable)


def test_command_rejects_shell_input():
    for command in ("python --version", "echo;whoami", "../program", "C:\\program.exe", "$(id)"):
        assert not valid_command(command)
        with pytest.raises(ValueError):
            resolve_command(command, [])


def test_current_directory_is_not_implicitly_searched(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    executable = Path("example")
    executable.write_text("data")
    executable.chmod(0o700)
    assert resolve_command("example", [{"value": ""}, {"value": "."}]) is None


def test_uninspected_path_entries_are_not_opened(tmp_path):
    executable = tmp_path / ("example.exe" if os.name == "nt" else "example")
    executable.write_text("data")
    executable.chmod(0o700)
    assert resolve_command("example", [{"value": str(tmp_path), "exists": None}]) is None


@pytest.mark.skipif(os.name == "nt", reason="Linux mount collector")
def test_known_network_mounts_are_skipped_before_filesystem_access(monkeypatch):
    import before.collect as collector

    monkeypatch.setenv("PATH", "/remote/tools")
    monkeypatch.setattr(collector, "_remote_mounts", lambda: ["/remote"])

    def forbidden(*args, **kwargs):
        raise AssertionError("network path was inspected")

    monkeypatch.setattr(Path, "is_dir", forbidden)
    assert read_path().data["entries"] == [{"value": "/remote/tools", "exists": None}]


def test_collecting_a_snapshot_does_not_open_network_sockets(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("snapshot collector attempted a network request")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    snapshot = capture("test-installation", "test")
    assert len(snapshot.sections) == 5
    assert snapshot.sections["commands"].status == "ok"


def test_only_whitelisted_environment_is_read(monkeypatch):
    monkeypatch.setenv("PRIVATE_API_KEY", "do-not-store-this")
    monkeypatch.setenv("https_proxy", "http://alice:supersecret@localhost:8080")
    proxy = read_proxy()
    assert "do-not-store-this" not in str(proxy)
    assert "supersecret" not in str(proxy)


@pytest.mark.skipif(os.name == "nt", reason="Linux process PATH collector")
def test_process_path_explicitly_records_empty_entry(monkeypatch):
    monkeypatch.setenv("PATH", "/bin::/missing")
    observation = read_path()
    assert [x["value"] for x in observation.data["entries"]] == ["/bin", "", "/missing"]
