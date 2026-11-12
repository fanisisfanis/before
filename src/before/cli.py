"""Small CLI for scripted snapshots, comparison and evidence export."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from .collect import capture
from .engine import analyze
from .i18n import set_language, tr
from .models import Snapshot
from .probes import local_proxy_checks, network_checks, validate_host
from .report import html_report, markdown
from .store import Store, atomic_write


def _load(path: str) -> Snapshot:
    file = Path(path)
    if file.stat().st_size > 2_000_000:
        raise ValueError("Снимок больше 2 МБ.")
    return Snapshot.from_json(file.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="before-cli", description="Local evidence for 'it worked yesterday'."
    )
    parser.add_argument("--lang", choices=("en", "ru"), default="en")
    sub = parser.add_subparsers(dest="action", required=True)
    snapshot = sub.add_parser("snapshot", help="Capture current settings without network requests")
    snapshot.add_argument("output")
    snapshot.add_argument("--label", default="Рабочее состояние")
    snapshot.add_argument("--command", default="")
    comparison = sub.add_parser("compare", help="Compare two exported snapshots offline")
    comparison.add_argument("baseline")
    comparison.add_argument("current")
    diagnosis = sub.add_parser("diagnose", help="Capture and inspect the current machine")
    diagnosis.add_argument("--baseline")
    diagnosis.add_argument(
        "--probe", metavar="HOST", help="Opt in to direct/proxy HTTPS checks, e.g. example.com"
    )
    for item in (comparison, diagnosis):
        item.add_argument("--command", default="")
        item.add_argument("--symptom", choices=("all", "internet", "command"), default="all")
        item.add_argument("--output", help="Write .md or .html (redacted)")
    sub.add_parser("history", help="List saved local snapshots")
    args = parser.parse_args(argv)
    set_language(args.lang)
    try:
        if args.action == "compare":
            analysis = analyze(
                _load(args.current), _load(args.baseline), args.symptom, args.command
            )
        else:
            store = Store()
            if args.action == "history":
                for item in store.list():
                    print(f"{item.id}  {item.captured_at}  {item.label}")
                return 0
            current = capture(store.machine_id, getattr(args, "label", "Сейчас"), args.command)
            if args.action == "snapshot":
                atomic_write(Path(args.output), current.to_json())
                store.save(current)
                print(tr(f"Снимок сохранён: {args.output}"))
                return 0
            probes = {"local_proxy": local_proxy_checks(current)}
            if args.probe:
                probes["network"] = network_checks(current, validate_host(args.probe))
            baseline = _load(args.baseline) if args.baseline else None
            analysis = analyze(current, baseline, args.symptom, args.command, probes)
        text = markdown(analysis)
        if args.output:
            output = Path(args.output)
            atomic_write(output, html_report(text) if output.suffix.lower() == ".html" else text)
            print(tr(f"Отчёт сохранён: {output}"))
        else:
            print(text)
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"BEFORE: {tr(str(exc))}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
