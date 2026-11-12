"""Bounded, read-only operating system collectors. Never run user commands."""

from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from .models import Observation, Snapshot

DEFAULT_COMMANDS = ("python", "python3", "git", "node", "npm", "ffmpeg")
PROXY_KEYS = ("http_proxy", "https_proxy", "all_proxy", "no_proxy")


def safe_proxy(value: str) -> str:
    """Do not persist proxy credentials, including credentials in malformed URLs."""
    # ProxyServer may contain http=host:port;https=host:port. Remove userinfo
    # from each piece without assuming that it is a valid URI.
    value = re.sub(r"(?:(?<=://)|(?<==)|(?<=;)|^)[^/@;\s=]+@", "[credentials removed]@", value)
    # PAC URLs and nonstandard proxy URLs may carry access tokens in the query.
    return value.split("?", 1)[0].split("#", 1)[0][:4096]


def proxy_endpoint(value: str, scheme: str = "https") -> tuple[str, int] | None:
    """Understand WinINET scheme maps and ordinary HTTP proxy URLs."""
    if not value or "[credentials removed]" in value:
        return None
    if "=" in value and "://" not in value:
        parts = dict(x.strip().split("=", 1) for x in value.split(";") if "=" in x)
        value = parts.get(scheme, parts.get("http", ""))
    try:
        parsed = urlsplit(value if "://" in value else "http://" + value)
        if parsed.scheme not in ("http", "https", "socks", "socks5", "socks5h"):
            return None
        if not parsed.hostname or parsed.username or parsed.password:
            return None
        port = (
            parsed.port
            if parsed.port is not None
            else (
                443
                if parsed.scheme == "https"
                else 1080
                if parsed.scheme.startswith("socks")
                else 80
            )
        )
        return (parsed.hostname, port) if 1 <= port <= 65535 else None
    except ValueError:
        return None


def read_proxy() -> Observation:
    env: dict[str, str] = {}
    # Lowercase wins consistently. Keep uppercase separately only when it differs.
    for key in PROXY_KEYS:
        for source in (key.upper(), key):
            if os.environ.get(source):
                env[key] = safe_proxy(os.environ[source])
    windows = None
    note = "Переменные текущего процесса; настройки рабочего стола Linux не читаются."
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            ) as key:

                def value(name, default):
                    try:
                        return winreg.QueryValueEx(key, name)[0]
                    except FileNotFoundError:
                        return default

                windows = {
                    "enabled": bool(value("ProxyEnable", 0)),
                    "server": safe_proxy(str(value("ProxyServer", ""))),
                    "bypass": str(value("ProxyOverride", ""))[:4096],
                    "pac": safe_proxy(str(value("AutoConfigURL", ""))),
                }
            note = "WinINET текущего пользователя и окружение процесса. WinHTTP и автоматическое обнаружение прокси не проверяются."
        except OSError as exc:
            note = f"Не удалось прочитать WinINET ({type(exc).__name__}); доступно только окружение процесса."
    return Observation("ok", {"environment": env, "windows": windows}, note)


def _expand_windows(value: str) -> str:
    buffer = ctypes.create_unicode_buffer(32768)
    result = ctypes.windll.kernel32.ExpandEnvironmentStringsW(value, buffer, len(buffer))
    return buffer.value if 0 < result <= len(buffer) else value


def _remote_mounts() -> list[str]:
    if sys.platform != "linux":
        return []
    try:
        mounts = []
        for line in Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines():
            left, separator, right = line.partition(" - ")
            if not separator:
                continue
            fields, filesystem = left.split(), right.split()[0]
            if filesystem in (
                "nfs",
                "nfs4",
                "cifs",
                "smb3",
                "9p",
                "ceph",
                "afs",
                "glusterfs",
            ) or filesystem.startswith(("fuse.sshfs", "fuse.rclone", "fuse.davfs")):
                mounts.append(fields[4].replace(r"\040", " ").rstrip("/"))
        return mounts
    except (OSError, IndexError):
        return []


def _skip_directory(value: str, mounts: list[str]) -> bool:
    if not value or not os.path.isabs(value):
        return True
    if sys.platform == "win32":
        if value.startswith(("\\\\", "//")):
            return True
        drive = os.path.splitdrive(value)[0]
        return bool(drive and ctypes.windll.kernel32.GetDriveTypeW(drive + "\\") == 4)
    value = os.path.abspath(value)
    return any(value == root or value.startswith(root + "/") for root in mounts)


def read_path() -> Observation:
    value = os.environ.get("PATH", "")
    scope = "Окружение запущенного BEFORE"
    note = "Изменения PATH в других терминалах станут видны после перезапуска BEFORE."
    if sys.platform == "win32":
        import winreg

        values = []
        try:
            for hive, name in (
                (
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
                ),
                (winreg.HKEY_CURRENT_USER, r"Environment"),
            ):
                with winreg.OpenKey(hive, name) as key:
                    try:
                        raw = winreg.QueryValueEx(key, "Path")[0]
                    except FileNotFoundError:
                        raw = ""
                    values.append(str(raw))
            value = ";".join(x for x in values if x)
            scope = "Сохранённые системный и пользовательский PATH"
            note = "PATH прочитан заново из реестра. Уже запущенные терминалы могут иметь другое окружение."
        except OSError:
            note = "Реестр PATH недоступен; прочитано только окружение запущенного BEFORE."
    entries = []
    mounts = _remote_mounts()
    for item in value.split(";" if sys.platform == "win32" else ":"):
        if not item:
            entries.append({"value": "", "exists": None})
            continue
        expanded = _expand_windows(item) if sys.platform == "win32" else item
        expanded = expanded.strip('"')
        if _skip_directory(expanded, mounts):
            entries.append({"value": expanded, "exists": None})
            continue
        try:
            exists = Path(expanded).is_dir()
        except (ValueError, OSError):
            exists = None
        entries.append({"value": expanded, "exists": exists})
    note += " Относительные и распознанные сетевые каталоги не проверяются."
    return Observation("ok", {"entries": entries, "scope": scope}, note)


def valid_command(name: str) -> bool:
    return bool(re.fullmatch(r"[\w.+-]{1,100}", name)) and name not in (".", "..")


def resolve_command(name: str, entries: list[dict], windows: bool | None = None) -> str | None:
    """Resolve a basename in the collected PATH only; never execute or search cwd implicitly."""
    if not valid_command(name):
        raise ValueError("Введите только имя команды, например python или ffmpeg, без аргументов.")
    windows = sys.platform == "win32" if windows is None else windows
    extensions = [""]
    if windows and not Path(name).suffix:
        extensions = [".exe", ".com", ".bat", ".cmd"]
    for entry in entries:
        directory = entry.get("value", "")
        if "exists" in entry and entry["exists"] is None:
            continue
        # Relative/current-directory entries depend on the launching shell. Do not
        # inspect those folders or imply that they resolve like a user's shell.
        if not directory or not Path(directory).is_absolute():
            continue
        for extension in extensions:
            candidate = Path(directory) / (name + extension)
            try:
                if candidate.is_file() and (windows or os.access(candidate, os.X_OK)):
                    return str(candidate)
            except OSError:
                continue
    return None


def read_hosts(path: Path | None = None) -> Observation:
    if path is None:
        path = (
            Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/drivers/etc/hosts"
            if sys.platform == "win32"
            else Path("/etc/hosts")
        )
    try:
        if path.stat().st_size > 1_000_000:
            return Observation("unavailable", note="Файл hosts больше 1 МБ; чтение пропущено.")
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        entries: dict[str, str] = {}
        for line in content.splitlines():
            parts = line.partition("#")[0].split()
            if len(parts) > 1:
                for name in parts[1:]:
                    key = name.casefold().rstrip(".")
                    old = entries.get(key, "")
                    entries[key] = ", ".join(
                        sorted(set(filter(None, [*old.split(", "), parts[0]])))
                    )
        digest = hashlib.sha256(repr(sorted(entries.items())).encode()).hexdigest()
        return Observation("ok", {"digest": digest, "entries": entries})
    except (OSError, ValueError) as exc:
        return Observation("unavailable", note=f"hosts недоступен: {type(exc).__name__}.")


def _windows_services() -> Observation:
    from ctypes import wintypes as w

    class Status(ctypes.Structure):
        _fields_ = [
            (x, w.DWORD)
            for x in ("type", "state", "controls", "exit", "specific", "checkpoint", "wait")
        ]

    class Config(ctypes.Structure):
        _fields_ = [
            ("type", w.DWORD),
            ("start", w.DWORD),
            ("error", w.DWORD),
            ("binary", w.LPWSTR),
            ("group", w.LPWSTR),
            ("tag", w.DWORD),
            ("dependencies", w.LPWSTR),
            ("account", w.LPWSTR),
            ("display", w.LPWSTR),
        ]

    api = ctypes.WinDLL("advapi32", use_last_error=True)
    api.OpenSCManagerW.argtypes = [w.LPCWSTR, w.LPCWSTR, w.DWORD]
    api.OpenSCManagerW.restype = w.HANDLE
    api.OpenServiceW.argtypes = [w.HANDLE, w.LPCWSTR, w.DWORD]
    api.OpenServiceW.restype = w.HANDLE
    api.QueryServiceStatus.argtypes = [w.HANDLE, ctypes.POINTER(Status)]
    api.QueryServiceStatus.restype = w.BOOL
    api.QueryServiceConfigW.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    api.QueryServiceConfigW.restype = w.BOOL
    api.CloseServiceHandle.argtypes = [w.HANDLE]
    api.CloseServiceHandle.restype = w.BOOL
    manager = api.OpenSCManagerW(None, None, 1)  # SC_MANAGER_CONNECT
    if not manager:
        return Observation("unavailable", note="Нет доступа к диспетчеру служб.")
    states = {1: "stopped", 2: "start_pending", 3: "stop_pending", 4: "running", 7: "paused"}
    starts = {0: "boot", 1: "system", 2: "automatic", 3: "manual", 4: "disabled"}
    result = {}
    try:
        for name in ("Dhcp", "Dnscache", "BITS"):
            handle = api.OpenServiceW(manager, name, 0x0001 | 0x0004)  # QUERY_CONFIG | QUERY_STATUS
            if not handle:
                continue
            try:
                status, needed = Status(), w.DWORD()
                if not api.QueryServiceStatus(handle, ctypes.byref(status)):
                    continue
                api.QueryServiceConfigW(handle, None, 0, ctypes.byref(needed))
                buffer = ctypes.create_string_buffer(needed.value) if needed.value else None
                start = "unknown"
                if buffer is not None and api.QueryServiceConfigW(
                    handle, buffer, needed, ctypes.byref(needed)
                ):
                    config = ctypes.cast(buffer, ctypes.POINTER(Config)).contents
                    start = starts.get(config.start, "unknown")
                result[name] = {"state": states.get(status.state, "unknown"), "start": start}
            finally:
                api.CloseServiceHandle(handle)
    finally:
        api.CloseServiceHandle(manager)
    return Observation(
        "ok" if result else "unavailable",
        result,
        "Только Dhcp, Dnscache и BITS; остановка службы сама по себе не доказывает неисправность.",
    )


def read_services() -> Observation:
    if sys.platform == "win32":
        return _windows_services()
    if sys.platform != "linux":
        return Observation("unavailable", note="Службы поддерживаются в Windows и systemd Linux.")
    result = {}
    process_env = {**os.environ, "LC_ALL": "C", "SYSTEMD_PAGER": ""}
    if getattr(sys, "frozen", False):
        # System utilities must load the host's libraries, not PyInstaller's
        # Qt/runtime libraries. The probe child deliberately keeps the bundle.
        if "LD_LIBRARY_PATH_ORIG" in os.environ:
            process_env["LD_LIBRARY_PATH"] = os.environ["LD_LIBRARY_PATH_ORIG"]
        else:
            process_env.pop("LD_LIBRARY_PATH", None)
    for unit in ("NetworkManager.service", "systemd-resolved.service"):
        try:
            process = subprocess.run(
                ["systemctl", "show", unit, "--property=LoadState,ActiveState,UnitFileState"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
                env=process_env,
            )
            if process.returncode:
                continue
            values = dict(line.split("=", 1) for line in process.stdout.splitlines() if "=" in line)
            if values.get("LoadState") != "loaded":
                continue
            result[unit] = {
                "state": values.get("ActiveState", "unknown"),
                "start": values.get("UnitFileState", "unknown"),
            }
        except (OSError, subprocess.TimeoutExpired):
            continue
    return Observation(
        "ok" if result else "unavailable",
        result,
        "Только NetworkManager и systemd-resolved, если установлены. Другие сетевые службы не проверяются.",
    )


def capture(machine_id: str, label: str = "Сейчас", command: str = "") -> Snapshot:
    path = read_path()
    names = list(DEFAULT_COMMANDS)
    if command:
        if not valid_command(command):
            raise ValueError("Введите имя команды без аргументов: например python или ffmpeg.")
        names.append(command)
    commands = {
        name: resolve_command(name, path.data.get("entries", [])) for name in dict.fromkeys(names)
    }
    sections = {
        "proxy": read_proxy(),
        "path": path,
        "commands": Observation(
            "ok",
            commands,
            "Проверено наличие файлов в абсолютных каталогах PATH. Команды не запускались; aliases, shell functions и App Execution Aliases не учитываются.",
        ),
        "hosts": read_hosts(),
        "services": read_services(),
    }
    return Snapshot.create(machine_id, label, platform.system(), sections)
