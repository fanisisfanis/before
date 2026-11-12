"""Small, versioned document model shared by collectors, UI and CLI.

Snapshots are data, never executable instructions. Validate imported documents
before admitting them to the local history.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = 1
MAX_DOCUMENT_BYTES = 2_000_000
SECTIONS = ("proxy", "path", "commands", "hosts", "services")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Observation:
    status: str  # ok | unavailable
    data: dict[str, Any] = field(default_factory=dict)
    note: str = ""


@dataclass(frozen=True)
class Snapshot:
    id: str
    machine_id: str
    label: str
    captured_at: str
    platform: str
    sections: dict[str, Observation]
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def create(
        cls, machine_id: str, label: str, platform: str, sections: dict[str, Observation]
    ) -> Snapshot:
        return cls(
            str(uuid.uuid4()),
            machine_id,
            label.strip()[:100] or "Снимок",
            now(),
            platform,
            sections,
        )

    @classmethod
    def from_json(cls, text: str) -> Snapshot:
        if len(text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise ValueError("Снимок больше допустимых 2 МБ.")
        try:
            raw = json.loads(text)
        except (ValueError, RecursionError) as exc:
            raise ValueError("Файл не является корректным JSON-снимком.") from exc
        if (
            not isinstance(raw, dict)
            or type(raw.get("schema_version")) is not int
            or raw.get("schema_version") != SCHEMA_VERSION
        ):
            raise ValueError("Неподдерживаемая версия снимка.")
        for name in ("id", "machine_id", "label", "captured_at", "platform"):
            value = raw.get(name)
            if not isinstance(value, str) or not value or len(value) > 200:
                raise ValueError(f"Некорректное поле снимка: {name}.")
        try:
            uuid.UUID(raw["id"])
            parsed_date = datetime.fromisoformat(raw["captured_at"])
            if parsed_date.tzinfo is None:
                raise ValueError("Snapshot date must include a timezone")
        except ValueError as exc:
            raise ValueError("Некорректный идентификатор или дата снимка.") from exc
        sections = raw.get("sections")
        if not isinstance(sections, dict) or set(sections) != set(SECTIONS):
            raise ValueError("Снимок должен содержать все пять разделов BEFORE.")
        observations = {}
        for name, item in sections.items():
            if not isinstance(item, dict) or item.get("status") not in ("ok", "unavailable"):
                raise ValueError(f"Некорректный раздел: {name}.")
            data, note = item.get("data"), item.get("note", "")
            if not isinstance(data, dict) or not isinstance(note, str):
                raise ValueError(f"Некорректные данные раздела: {name}.")
            _validate_section(name, data)
            observations[name] = Observation(item["status"], data, note[:1000])
        return cls(
            raw["id"],
            raw["machine_id"],
            raw["label"],
            raw["captured_at"],
            raw["platform"],
            observations,
        )


def _string_map(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and len(value) <= 500
        and all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())
    )


def _validate_section(name: str, data: dict[str, Any]) -> None:
    valid = True
    if data:  # unavailable sections can legitimately be empty
        if name == "proxy":
            valid = _string_map(data.get("environment", {}))
            windows = data.get("windows")
            if windows is not None:
                valid = valid and isinstance(windows, dict)
                if valid:
                    valid = isinstance(windows.get("enabled"), bool) and all(
                        isinstance(windows.get(k, ""), str) for k in ("server", "bypass", "pac")
                    )
        elif name == "path":
            entries = data.get("entries")
            valid = isinstance(entries, list) and len(entries) <= 10000
            if valid:
                valid = all(
                    isinstance(x, dict)
                    and isinstance(x.get("value"), str)
                    and (x.get("exists") is None or isinstance(x["exists"], bool))
                    for x in entries
                )
            valid = valid and isinstance(data.get("scope", ""), str)
        elif name == "commands":
            valid = len(data) <= 500 and all(
                isinstance(k, str) and (v is None or isinstance(v, str)) for k, v in data.items()
            )
        elif name == "hosts":
            valid = isinstance(data.get("digest"), str) and _string_map(data.get("entries"))
        elif name == "services":
            valid = len(data) <= 100 and all(
                isinstance(k, str)
                and isinstance(v, dict)
                and all(isinstance(v.get(f, ""), str) for f in ("state", "start"))
                for k, v in data.items()
            )
    if not valid:
        raise ValueError(f"Неверная структура данных раздела: {name}.")


@dataclass(frozen=True)
class Change:
    section: str
    subject: str
    before: str
    after: str


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str  # warning | info
    certainty: str  # fact | hypothesis
    title: str
    explanation: str
    evidence: tuple[str, ...]
    steps: tuple[str, ...]


@dataclass
class Analysis:
    current: Snapshot
    baseline: Snapshot | None
    symptom: str
    command: str
    changes: list[Change]
    findings: list[Finding]
    limitations: list[str]
    probes: dict[str, Any] = field(default_factory=dict)
