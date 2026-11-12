"""Opt-in connectivity checks isolated in a time-bounded child process.

Each HTTPS route uses the same host and a fresh SSL context. No response body,
cookies, credentials or system configuration are sent to BEFORE or a backend.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import ssl
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
    proxy_bypass_environment,
)

from .collect import proxy_endpoint
from .models import Snapshot


def validate_host(host: str) -> str:
    host = host.strip().rstrip(".")
    if not host or len(host) > 253 or any(c in host for c in "/:@?#\\\n\r\t "):
        raise ValueError("Введите имя сайта без https://, порта и пути: example.com.")
    ascii_host = host.encode("idna").decode("ascii").lower()
    if any(
        not part
        or len(part) > 63
        or part.startswith("-")
        or part.endswith("-")
        or not all(c.isalnum() or c == "-" for c in part)
        for part in ascii_host.split(".")
    ):
        raise ValueError("Некорректное имя сайта.")
    return ascii_host


def configured_proxies(snapshot: Snapshot) -> list[tuple[str, str]]:
    data = snapshot.sections["proxy"].data
    env = data.get("environment", {})
    result = [
        (f"{name}", env[name])
        for name in ("https_proxy", "http_proxy", "all_proxy")
        if env.get(name)
    ]
    windows = data.get("windows")
    if windows and windows.get("enabled") and windows.get("server"):
        result.append(("WinINET", windows["server"]))
    return result


def local_proxy_checks(snapshot: Snapshot) -> dict:
    """Probe configured numeric loopback endpoints only; never scan a network."""
    results = {}
    for name, value in configured_proxies(snapshot):
        endpoint = proxy_endpoint(value)
        if endpoint is None:
            continue
        host, port = endpoint
        try:
            loopback = host.casefold() == "localhost" or ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            continue
        candidates = ["127.0.0.1", "::1"] if host.casefold() == "localhost" else [host]
        accepted = False
        for address in candidates:
            try:
                with socket.create_connection((address, port), timeout=0.35):
                    accepted = True
                    break
            except OSError:
                pass
        results[name] = {"host": host, "port": port, "reachable": accepted}
    return results


def route_proxy(snapshot: Snapshot, host: str) -> tuple[str | None, str]:
    data = snapshot.sections["proxy"].data
    env = data.get("environment", {})
    value = env.get("https_proxy") or env.get("all_proxy")
    if value:
        if proxy_bypass_environment(host, proxies={"no": env.get("no_proxy", "")}):
            return None, "Сайт исключён через no_proxy; маршрут через прокси пропущен."
        if "[credentials removed]" in value:
            return None, "Прокси требует учётные данные; BEFORE их не читает и не отправляет."
        parsed = urlsplit(value if "://" in value else "http://" + value)
        if parsed.scheme not in ("http", "https"):
            return (
                None,
                "Активный SOCKS/неизвестный прокси: HTTPS-проверка этого маршрута не поддерживается.",
            )
        return value if "://" in value else "http://" + value, "Прокси из окружения процесса."
    windows = data.get("windows")
    if windows and windows.get("pac"):
        return None, "Настроен PAC; BEFORE не исполняет скрипты автоматической настройки."
    if windows and windows.get("enabled"):
        bypass = windows.get("bypass", "")
        if bypass:
            return None, "Есть правила обхода WinINET; выбор маршрута оставлен браузеру."
        value = windows.get("server", "")
        if "=" in value:
            mapping = dict(x.split("=", 1) for x in value.split(";") if "=" in x)
            value = mapping.get("https", "")
        if value and proxy_endpoint(value):
            return value if "://" in value else "http://" + value, "Ручной прокси WinINET."
    return None, "Поддерживаемый явный HTTPS-прокси не настроен."


def _request(host: str, proxy: str | None) -> dict:
    try:

        class ExplicitProxyHandler(ProxyHandler):
            def proxy_open(self, req, value, scheme):
                parsed = urlsplit(value)
                # Route selection and no_proxy are already evaluated by
                # route_proxy. Avoid a second implicit OS/environment bypass
                # silently turning the proxy test into another direct test.
                if parsed.scheme not in ("http", "https") or parsed.username or parsed.password:
                    raise ValueError("Unsupported proxy")
                req.set_proxy(parsed.netloc, parsed.scheme)
                return None

        opener = build_opener(
            ExplicitProxyHandler({"https": proxy} if proxy else {}),
            HTTPSHandler(context=ssl.create_default_context()),
        )
        # Prevent redirects to a second host; the test only contacts the named target.
        from urllib.request import HTTPRedirectHandler

        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener.add_handler(NoRedirect())
        request = Request(
            f"https://{host}/",
            method="HEAD",
            headers={"User-Agent": "BEFORE/0.1 connectivity-check"},
        )
        with opener.open(request, timeout=3) as response:
            return {"status": "reachable", "http_status": response.status}
    except HTTPError as exc:
        # An HTTP response still proves the route reached an HTTP endpoint. It
        # says nothing about login success or whether the site's content works.
        return {"status": "reachable", "http_status": exc.code}
    except (URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"status": "failed", "error": type(reason).__name__}


def worker(payload: dict) -> dict:
    host = validate_host(payload["host"])
    try:
        socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        dns = "resolved"
    except OSError:
        dns = "failed"
    result = {"host": host, "dns": dns, "direct": _request(host, None)}
    if payload.get("proxy"):
        result["proxy"] = _request(host, payload["proxy"])
    return result


def network_checks(snapshot: Snapshot, host: str = "example.com") -> dict:
    host = validate_host(host)
    proxy, note = route_proxy(snapshot, host)
    command = (
        [sys.executable, "--probe-worker"]
        if getattr(sys, "frozen", False)
        else [sys.executable, "-m", "before.probes", "--worker"]
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = (
        str(Path(__file__).resolve().parent.parent) + os.pathsep + env.get("PYTHONPATH", "")
    )
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        process = subprocess.run(
            command,
            input=json.dumps({"host": host, "proxy": proxy}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=12,
            env=env,
            creationflags=flags,
            check=False,
        )
        if process.returncode:
            return {
                "host": host,
                "status": "unavailable",
                "note": "Сетевая проверка завершилась ошибкой.",
            }
        result = json.loads(process.stdout)
        result["route_note"] = note
        return result
    except subprocess.TimeoutExpired:
        return {
            "host": host,
            "status": "unavailable",
            "note": "Лимит 12 секунд исчерпан; результат неизвестен.",
        }
    except (OSError, ValueError):
        return {
            "host": host,
            "status": "unavailable",
            "note": "Не удалось выполнить сетевую проверку.",
        }


if __name__ == "__main__":
    print(json.dumps(worker(json.load(sys.stdin)), ensure_ascii=False))
