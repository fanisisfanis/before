import time

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QLabel, QPushButton

from before.app import STYLE, ReportDialog, Window
from before.demo import example
from before.store import Store


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    return app


@pytest.fixture
def window(tmp_path, qapp):
    widget = Window(Store(tmp_path))
    widget.show()
    qapp.processEvents()
    yield widget
    widget.close()
    widget.pool.waitForDone(15000)
    qapp.processEvents()


def wait_until(qapp, condition, seconds=5):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and not condition():
        qapp.processEvents()
        QTest.qWait(10)
    assert condition(), "UI operation did not finish within its deadline"


def test_empty_state_and_demo_are_operable(window, qapp):
    assert not window.report_button.isEnabled()
    window.show_demo()
    qapp.processEvents()
    assert window.demo
    assert window.demo_bar.isVisible()
    assert window.report_button.isEnabled()
    assert len(window.analysis.changes) == 4
    window.leave_demo()
    assert window.analysis is None
    assert not window.demo


def test_diagnostic_cards_do_not_collapse_or_clip(window, qapp):
    window.show_demo()
    qapp.processEvents()
    window.resize(960, 680)
    qapp.processEvents()
    titles = [
        item
        for item in window.findChildren(QLabel)
        if item.objectName() == "cardTitle" and "Local proxy" in item.text()
    ]
    assert titles and titles[0].height() >= 19
    assert window.scroll.widget().height() > window.scroll.viewport().height()


def test_capture_compare_export_flow_uses_background_worker(window, qapp, monkeypatch, tmp_path):
    old, current, probes = example()
    # Keep actual store IO, task scheduling and widgets; replace only OS input.
    import before.app as app_module

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Рабочая точка", True))
    monkeypatch.setattr(app_module, "capture", lambda *a, **k: old)
    window.save_snapshot()
    assert window.busy
    wait_until(qapp, lambda: not window.busy)
    assert window.baseline == old
    assert len(window.store.list()) == 1
    monkeypatch.setattr(app_module, "capture", lambda *a, **k: current)
    monkeypatch.setattr(app_module, "local_proxy_checks", lambda *a, **k: probes["local_proxy"])
    QTest.mouseClick(window.compare_button, Qt.MouseButton.LeftButton)
    wait_until(qapp, lambda: not window.busy)
    assert len(window.analysis.changes) == 4
    dialog = ReportDialog(window.analysis, window)
    output = tmp_path / "reviewed.html"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(output), "HTML (*.html)")
    )
    dialog.editor.setPlainText("# Проверено\nРедактирование до экспорта работает.")
    dialog.save()
    assert "Редактирование до экспорта" in output.read_text(encoding="utf-8")
    dialog.copy()
    assert QApplication.clipboard().text() == dialog.editor.toPlainText()
    dialog.close()


def test_all_visible_primary_actions_have_text(window):
    assert all(item.text().strip() for item in window.findChildren(QPushButton) if item.isVisible())
