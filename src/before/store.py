"""Transactional local history. No daemon, account or network service."""

from __future__ import annotations

import os
import sqlite3
import sys
import uuid
from pathlib import Path

from .models import MAX_DOCUMENT_BYTES, Snapshot


def data_directory() -> Path:
    override = os.environ.get("BEFORE_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "Before"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "before"


class Store:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or data_directory()
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.directory / "history.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY, captured_at TEXT NOT NULL, payload TEXT NOT NULL
                );
            """)
            db.execute(
                "INSERT OR IGNORE INTO settings VALUES ('machine_id', ?)", (str(uuid.uuid4()),)
            )
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    @property
    def machine_id(self) -> str:
        with self.connect() as db:
            return db.execute("SELECT value FROM settings WHERE key='machine_id'").fetchone()[0]

    def save(self, snapshot: Snapshot) -> None:
        validated = Snapshot.from_json(snapshot.to_json())
        with self.connect() as db:
            db.execute(
                "INSERT OR IGNORE INTO snapshots VALUES (?, ?, ?)",
                (validated.id, validated.captured_at, validated.to_json()),
            )

    def list(self) -> list[Snapshot]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM snapshots ORDER BY captured_at DESC, rowid DESC"
            ).fetchall()
        result = []
        for (payload,) in rows:
            try:
                result.append(Snapshot.from_json(payload))
            except ValueError:
                continue  # a damaged row must not make every good snapshot inaccessible
        return result

    def get(self, snapshot_id: str) -> Snapshot:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM snapshots WHERE id=?", (snapshot_id,)).fetchone()
        if row is None:
            raise ValueError("Снимок не найден.")
        return Snapshot.from_json(row[0])

    def delete(self, snapshot_id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM snapshots WHERE id=?", (snapshot_id,))

    def import_file(self, path: Path) -> Snapshot:
        if path.stat().st_size > MAX_DOCUMENT_BYTES:
            raise ValueError("Снимок больше допустимых 2 МБ.")
        snapshot = Snapshot.from_json(path.read_text(encoding="utf-8"))
        self.save(snapshot)
        return snapshot


def atomic_write(path: Path, content: str) -> None:
    """Write next to destination, then replace atomically; do not leave partial reports."""
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
