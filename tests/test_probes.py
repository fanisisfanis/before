import socket
import subprocess
import threading
from dataclasses import replace

import pytest

from before.demo import example
from before.models import Observation
from before.probes import local_proxy_checks, network_checks, route_proxy, validate_host


def test_explicit_proxy_route_is_not_silently_bypassed(monkeypatch):
    from before.probes import _request

    received = []
    monkeypatch.setenv("no_proxy", "*")
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        server.settimeout(3)

        def accept():
            try:
                connection, _ = server.accept()
                with connection:
                    connection.settimeout(3)
                    received.append(connection.recv(4096))
                    connection.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass

        thread = threading.Thread(target=accept, daemon=True)
        thread.start()
        result = _request("before.invalid", f"http://127.0.0.1:{server.getsockname()[1]}")
        thread.join(4)
    assert received and received[0].startswith(b"CONNECT before.invalid:443 ")
    assert result["status"] == "failed"


def proxy_snapshot(environment=None, windows=None):
    snapshot = example()[0]
    return replace(
        snapshot,
        sections={
            **snapshot.sections,
            "proxy": Observation(
                "ok",
                {
                    "environment": environment or {},
                    "windows": windows,
                },
            ),
        },
    )


@pytest.mark.parametrize(
    "host",
    [
        "https://example.com",
        "example.com:443",
        "user@example.com",
        "a/b",
        "a b",
        "",
        "a..b",
        "-bad.test",
    ],
)
def test_host_input_cannot_smuggle_a_url_or_credentials(host):
    with pytest.raises((ValueError, UnicodeError)):
        validate_host(host)


def test_hostname_normalization():
    assert validate_host(" EXAMPLE.COM. ") == "example.com"
    assert validate_host("пример.рф").startswith("xn--")


def test_only_loopback_proxy_ports_are_probed(monkeypatch):
    snapshot = proxy_snapshot({"https_proxy": "http://192.0.2.1:8080"})

    def forbidden(*args, **kwargs):
        raise AssertionError("remote port scanned")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert local_proxy_checks(snapshot) == {}


def test_closed_real_loopback_endpoint_is_reported():
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
        # Bound but not listening: no unrelated machine is contacted and no
        # race exists where another process can claim the reserved port.
        snapshot = proxy_snapshot({"https_proxy": f"http://127.0.0.1:{port}"})
        assert local_proxy_checks(snapshot)["https_proxy"]["reachable"] is False


def test_listening_real_loopback_endpoint_is_reported():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        snapshot = proxy_snapshot({"https_proxy": f"http://127.0.0.1:{server.getsockname()[1]}"})
        assert local_proxy_checks(snapshot)["https_proxy"]["reachable"] is True


def test_no_proxy_exclusion_is_respected():
    snapshot = proxy_snapshot({"https_proxy": "http://127.0.0.1:8080", "no_proxy": "example.com"})
    proxy, note = route_proxy(snapshot, "example.com")
    assert proxy is None and "исключён" in note


def test_pac_is_never_executed():
    snapshot = proxy_snapshot(
        windows={
            "enabled": True,
            "server": "127.0.0.1:8080",
            "pac": "https://example.com/config.pac",
        }
    )
    proxy, note = route_proxy(snapshot, "example.com")
    assert proxy is None and "PAC" in note


def test_socks_is_disclosed_instead_of_silently_testing_direct():
    snapshot = proxy_snapshot({"all_proxy": "socks5://127.0.0.1:1080"})
    proxy, note = route_proxy(snapshot, "example.com")
    assert proxy is None and "SOCKS" in note


def test_network_worker_is_bounded(monkeypatch):
    snapshot = proxy_snapshot()

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 12
        raise subprocess.TimeoutExpired("probe", 12)

    monkeypatch.setattr(subprocess, "run", timeout)
    result = network_checks(snapshot)
    assert result["status"] == "unavailable"
    assert "12 секунд" in result["note"]
