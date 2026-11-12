"""A clearly labelled example, not a substitute for the live collectors."""

from .models import Observation, Snapshot


def example() -> tuple[Snapshot, Snapshot, dict]:
    old = {
        "proxy": Observation(
            "ok",
            {
                "environment": {},
                "windows": {"enabled": False, "server": "", "bypass": "", "pac": ""},
            },
            "Пример WinINET Windows; данные вымышлены.",
        ),
        "path": Observation(
            "ok",
            {
                "entries": [
                    {"value": r"C:\Windows\System32", "exists": True},
                    {
                        "value": r"C:\Users\Alex\AppData\Local\Programs\Python\Python312",
                        "exists": True,
                    },
                    {"value": r"C:\Program Files\Git\cmd", "exists": True},
                ],
                "scope": "Сохранённый PATH",
            },
        ),
        "commands": Observation(
            "ok",
            {
                "python": r"C:\Users\Alex\AppData\Local\Programs\Python\Python312\python.exe",
                "git": r"C:\Program Files\Git\cmd\git.exe",
            },
        ),
        "hosts": Observation("ok", {"digest": "example", "entries": {"localhost": "127.0.0.1"}}),
        "services": Observation("ok", {"Dnscache": {"state": "running", "start": "automatic"}}),
    }
    new = dict(old)
    new["proxy"] = Observation(
        "ok",
        {
            "environment": {},
            "windows": {"enabled": True, "server": "127.0.0.1:7890", "bypass": "", "pac": ""},
        },
        "Пример WinINET Windows; данные вымышлены.",
    )
    new["path"] = Observation(
        "ok",
        {
            "entries": [old["path"].data["entries"][0], old["path"].data["entries"][2]],
            "scope": "Сохранённый PATH",
        },
    )
    new["commands"] = Observation(
        "ok", {"python": None, "git": r"C:\Program Files\Git\cmd\git.exe"}
    )
    baseline = Snapshot(
        "f4d8f60b-3969-46e8-89f5-d9c3ad34011b",
        "demo",
        "Всё работало",
        "2026-11-10T18:40:00+00:00",
        "Windows",
        old,
    )
    current = Snapshot(
        "b3bdd21e-f005-452e-9ac1-71d2625e0ed0",
        "demo",
        "После настройки VPN",
        "2026-11-11T19:12:00+00:00",
        "Windows",
        new,
    )
    probes = {"local_proxy": {"WinINET": {"host": "127.0.0.1", "port": 7890, "reachable": False}}}
    return baseline, current, probes
