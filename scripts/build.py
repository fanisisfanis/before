"""Build on the target OS. Shared Qt libraries remain replaceable in onedir."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--name",
        "BEFORE",
        "--paths",
        "src",
        "--add-data",
        f"src/before/assets{os.pathsep}before/assets",
        "--copy-metadata",
        "PySide6-Essentials",
        "--copy-metadata",
        "shiboken6",
    ]
    if sys.platform == "win32":
        # A hidden console preserves pipe-based worker output on Windows.
        # Windowed bootloaders set sys.stdout=None, breaking the isolated probe.
        command += [
            "--console",
            "--hide-console",
            "hide-early",
            "--icon",
            "src/before/assets/icon.ico",
        ]
    else:
        command += ["--windowed"]
        if shutil.which("strip"):
            command += ["--strip"]
    command += ["run.py"]
    subprocess.run(command, cwd=ROOT, check=True)
    target = ROOT / "dist/BEFORE"
    for name in ("LICENSE", "THIRD_PARTY.md", "README.ru.md"):
        shutil.copy2(ROOT / name, target / name)
    if (ROOT / "licenses").exists():
        shutil.copytree(ROOT / "licenses", target / "licenses", dirs_exist_ok=True)
    print(f"Portable folder ready: {target}")


if __name__ == "__main__":
    main()
