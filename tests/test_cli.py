from before.cli import main
from before.demo import example


def test_compare_export_is_an_offline_end_to_end_flow(tmp_path):
    baseline, current, _ = example()
    old, new, report = tmp_path / "old.json", tmp_path / "new.json", tmp_path / "report.html"
    old.write_text(baseline.to_json(), encoding="utf-8")
    new.write_text(current.to_json(), encoding="utf-8")
    assert main(["compare", str(old), str(new), "--output", str(report)]) == 0
    text = report.read_text(encoding="utf-8")
    assert "python: file not found" in text
    assert "Alex" not in text
    assert text.startswith("<!doctype html>")


def test_bad_input_has_a_clean_exit_code(tmp_path, capsys):
    file = tmp_path / "bad.json"
    file.write_text("[]")
    assert main(["compare", str(file), str(file)]) == 2
    assert "Traceback" not in capsys.readouterr().err
