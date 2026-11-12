import json
from dataclasses import replace

import pytest

from before.demo import example
from before.engine import analyze
from before.models import Snapshot
from before.report import html_report, markdown, redact
from before.store import Store, atomic_write


def test_snapshot_roundtrip():
    baseline, _, _ = example()
    assert Snapshot.from_json(baseline.to_json()) == baseline


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(schema_version=99),
        lambda d: d.update(schema_version=True),
        lambda d: d.update(captured_at="2026-11-12"),
        lambda d: d.update(id="not-a-uuid"),
        lambda d: d["sections"].pop("proxy"),
        lambda d: d["sections"]["path"].update(data={"entries": "not-a-list"}),
        lambda d: d["sections"]["proxy"].update(data={"windows": {"enabled": "yes"}}),
        lambda d: d["sections"]["commands"].update(data={"python": []}),
    ],
)
def test_invalid_imports_are_rejected(mutation):
    baseline, _, _ = example()
    data = baseline.to_dict()
    mutation(data)
    with pytest.raises(ValueError):
        Snapshot.from_json(json.dumps(data))


def test_oversized_import_is_rejected():
    with pytest.raises(ValueError):
        Snapshot.from_json(" " * 2_000_001)


def test_sqlite_history_is_transactional_and_deduplicated(tmp_path):
    first, second, _ = example()
    store = Store(tmp_path)
    store.save(first)
    store.save(second)
    store.save(first)
    assert store.list() == [second, first]
    assert store.machine_id == Store(tmp_path).machine_id
    store.delete(second.id)
    assert store.get(first.id) == first
    with pytest.raises(ValueError):
        store.get(second.id)


def test_corrupt_row_does_not_hide_good_snapshots(tmp_path):
    first, _, _ = example()
    store = Store(tmp_path)
    store.save(first)
    with store.connect() as db:
        db.execute("INSERT INTO snapshots VALUES ('bad', '2099', 'broken')")
    assert store.list() == [first]


def test_export_redacts_paths_but_keeps_the_useful_suffix():
    text = redact(r"C:\Users\Alex\Apps\python.exe /home/alex/bin/python https://me:secret@proxy:80")
    assert "Alex" not in text and "alex" not in text and "secret" not in text
    assert r"%USERPROFILE%\Apps\python.exe" in text
    assert "~/bin/python" in text


def test_html_export_never_interprets_report_content():
    html = html_report("# <script>alert(1)</script>\n- <img src=x onerror=alert(1)>")
    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html
    assert "default-src 'none'" in html


def test_report_contains_only_reviewable_evidence_not_machine_identifier():
    baseline, current, probes = example()
    current = replace(current, machine_id="private-machine-identifier")
    text = markdown(analyze(current, baseline, probes=probes))
    assert "private-machine-identifier" not in text
    assert "127.0.0.1:7890" in text
    assert "Alex" not in text


def test_atomic_report_write(tmp_path):
    path = tmp_path / "report.md"
    atomic_write(path, "first")
    atomic_write(path, "second\nстрока")
    assert path.read_text(encoding="utf-8") == "second\nстрока"
    assert list(tmp_path.iterdir()) == [path]
