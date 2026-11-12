"""Native Qt desktop UI. One workflow: remember, compare, inspect evidence."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .collect import capture, valid_command
from .demo import example
from .engine import SECTION_NAMES, analyze
from .models import Analysis, Snapshot
from .probes import local_proxy_checks, network_checks, validate_host
from .report import html_report, markdown
from .store import Store, atomic_write

STYLE = """
QWidget {color:#233b37;font-family:'DejaVu Sans','Segoe UI',sans-serif;font-size:13px;}
QMainWindow,#main {background:#f3f5f1;}
#sidebar {background:#192e2b;}
#sidebar QLabel {color:#c1d2c9;background:transparent;}
#brand {color:#f5f7ef !important;font-size:30px;font-weight:800;letter-spacing:4px;}
#sideCaption {color:#8ea69a !important;font-size:11px;letter-spacing:1px;}
#sideTitle {color:#d9e4dc !important;font-size:12px;font-weight:600;}
QLabel {background:transparent;}
#eyebrow {color:#6a8276;font-size:11px;font-weight:700;letter-spacing:2px;}
#heading {color:#1c3430;font-size:30px;font-weight:700;letter-spacing:-1px;}
#subheading {color:#718178;font-size:13px;}
#heroTitle {font-size:33px;font-weight:700;letter-spacing:-1px;color:#203b33;}
#heroText {font-size:14px;color:#687d71;}
#cardTitle {font-size:16px;font-weight:700;}
#muted {color:#738378;font-size:12px;}
#tiny {color:#78897f;font-size:11px;}
#pill {color:#346b56;background:#e1ece0;border:1px solid #cbdcc8;border-radius:12px;padding:5px 10px;font-size:11px;font-weight:600;}
#demoPill {color:#82691b;background:#f4e7bc;border-radius:10px;padding:6px 10px;font-size:11px;}
QPushButton {background:white;border:1px solid #d4dfd3;border-radius:8px;padding:11px 15px;font-weight:600;}
QPushButton:hover {background:#eaf0e6;border-color:#b8cdb9;}
QPushButton:pressed {background:#dce8d7;}
QPushButton:disabled {color:#9eada2;background:#e9eee5;border-color:#dfe5dc;}
QPushButton#primary {background:#c8e7a4;color:#173c27;border:1px solid #bbd997;}
QPushButton#primary:hover {background:#d7efb7;}
QPushButton#primary:disabled {background:#dce7d1;color:#8c9b81;}
QPushButton#action {background:#244f3d;color:white;border-color:#244f3d;}
QPushButton#action:hover {background:#31664d;}
QPushButton#action:disabled {background:#dce7d1;color:#8c9b81;border-color:#dce7d1;}
QPushButton#sideLink {background:transparent;color:#aec2b4;border-color:#385146;padding:9px;font-size:12px;}
QPushButton#sideLink:hover {background:#294338;color:#e8f0e8;}
QPushButton#link {background:transparent;border:none;color:#527865;padding:6px;font-size:12px;}
QPushButton#filter {background:transparent;border:none;border-radius:6px;padding:9px 13px;color:#6a7d70;font-weight:500;}
QPushButton#filter:checked {background:white;color:#244e37;font-weight:700;}
QPushButton#details {background:transparent;border:0;text-align:left;padding:6px 0;color:#38664d;font-size:12px;}
#filters {background:#e5ebe1;border-radius:9px;padding:3px;}
#card {background:white;border:1px solid #dce5d9;border-radius:12px;}
#warningCard {background:#fffdf7;border:1px solid #e9dfbf;border-radius:12px;}
#infoCard {background:white;border:1px solid #dce5d9;border-radius:12px;}
#summary {background:#e7efdf;border:1px solid #d1dfc8;border-radius:12px;}
#notice {background:#edf0e8;border:1px solid #dce3d5;border-radius:8px;}
#fact {color:#4b765b;background:#edf4e9;border-radius:5px;padding:4px 7px;font-size:10px;font-weight:700;letter-spacing:1px;}
#hypothesis {color:#977e38;background:#f7edcc;border-radius:5px;padding:4px 7px;font-size:10px;font-weight:700;letter-spacing:1px;}
QListWidget {background:transparent;border:0;outline:none;padding:0;}
QListWidget::item {background:transparent;color:#a8bfb0;border:1px solid transparent;border-radius:8px;padding:13px 10px;margin:3px 0;font-size:12px;}
QListWidget::item:hover {background:#223c32;}
QListWidget::item:selected {background:#304d3d;border:1px solid #537258;color:#eef5e9;}
QLineEdit {background:white;border:1px solid #ccd9c8;border-radius:7px;padding:10px;color:#244234;selection-background-color:#c8e7a4;}
QLineEdit:focus {border-color:#698963;}
QPlainTextEdit {background:#fbfcf8;border:1px solid #d4dfcf;border-radius:8px;padding:10px;selection-background-color:#c8e7a4;}
QCheckBox {color:#667c6c;spacing:8px;font-size:12px;}
QCheckBox::indicator {width:16px;height:16px;border:1px solid #becdb5;border-radius:4px;background:white;}
QCheckBox::indicator:checked {background:#496e47;border-color:#496e47;}
QScrollArea {background:transparent;border:0;}
#canvas {background:transparent;}
QScrollBar:vertical {background:transparent;width:7px;margin:3px;}
QScrollBar::handle:vertical {background:#bdcdb8;min-height:35px;border-radius:3px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
QProgressBar {border:0;background:#e3ebdd;border-radius:2px;max-height:4px;}
QProgressBar::chunk {background:#6d9357;}
QDialog {background:#f3f5f1;}
QToolTip {color:#243f30;background:#f9fbf5;border:1px solid #d3dfcd;padding:5px;}
"""


def label(text: str, name: str = "", wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(wrap)
    if wrap:
        policy = widget.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        widget.setSizePolicy(policy)
    return widget


def button(text: str, name: str = "", callback=None) -> QPushButton:
    widget = QPushButton(text)
    if name:
        widget.setObjectName(name)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    if callback:
        widget.clicked.connect(callback)
    return widget


def frame(name: str, margins: int = 20) -> tuple[QFrame, QVBoxLayout]:
    widget = QFrame()
    widget.setObjectName(name)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(margins, margins, margins, margins)
    layout.setSpacing(10)
    return widget, layout


def timestamp(value: str) -> str:
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y Â· %H:%M")
    except ValueError:
        return value


class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class Task(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = Signals()

    def run(self):
        try:
            self.signals.done.emit(self.function())
        except Exception as exc:
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}")


class Timeline(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(100)
        self.setMaximumHeight(130)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, right, middle = 28, self.width() - 28, 48
        painter.setPen(QPen(QColor("#d3dfcb"), 2))
        painter.drawLine(left, middle, right, middle)
        painter.setPen(QPen(QColor("#b2c89f"), 1))
        for i in range(21):
            x = int(left + (right - left) * i / 20)
            painter.drawLine(x, middle - 4, x, middle + 4)
        for x, text, fill in (
            (left + 35, "Ð’Ð¡Ð Ð ÐÐ‘ÐžÐ¢ÐÐ›Ðž", "#719553"),
            (right - 35, "Ð¡Ð•Ð™Ð§ÐÐ¡", "#214e37"),
        ):
            painter.setBrush(QColor(fill))
            painter.setPen(QPen(QColor("#f3f5f1"), 5))
            painter.drawEllipse(x - 8, middle - 8, 16, 16)
            painter.setPen(QColor("#6a806d"))
            painter.setFont(QFont("DejaVu Sans", 8))
            painter.drawText(x - 65, middle + 20, 130, 22, Qt.AlignmentFlag.AlignCenter, text)


class ReportDialog(QDialog):
    def __init__(self, analysis: Analysis, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BEFORE Â· ÐžÑ‚Ñ‡Ñ‘Ñ‚")
        self.resize(780, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(label("ÐŸÑ€Ð¾Ð²ÐµÑ€ÑŒ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚ Ð¿ÐµÑ€ÐµÐ´ Ð¾Ñ‚Ð¿Ñ€Ð°Ð²ÐºÐ¾Ð¹", "cardTitle"))
        layout.addWidget(
            label(
                "Ð˜Ð¼ÐµÐ½Ð° Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»ÐµÐ¹ Ð² Ð´Ð¾Ð¼Ð°ÑˆÐ½Ð¸Ñ… Ð¿ÑƒÑ‚ÑÑ… ÑÐºÑ€Ñ‹Ñ‚Ñ‹. ÐÐ´Ñ€ÐµÑÐ° ÑÐµÑ€Ð²ÐµÑ€Ð¾Ð², Ð´Ð¾Ð¼ÐµÐ½Ñ‹ Ð¸ Ð½Ð°Ð·Ð²Ð°Ð½Ð¸Ñ Ð¿Ñ€Ð¾Ð³Ñ€Ð°Ð¼Ð¼ Ð¼Ð¾Ð³ÑƒÑ‚ Ð¾ÑÑ‚Ð°Ñ‚ÑŒÑÑ â€” Ñ‚ÐµÐºÑÑ‚ Ð¼Ð¾Ð¶Ð½Ð¾ Ð¾Ñ‚Ñ€ÐµÐ´Ð°ÐºÑ‚Ð¸Ñ€Ð¾Ð²Ð°Ñ‚ÑŒ.",
                "muted",
                True,
            )
        )
        self.editor = QPlainTextEdit(markdown(analysis))
        self.editor.setObjectName("reportEditor")
        layout.addWidget(self.editor, 1)
        row = QHBoxLayout()
        self.status = label("", "muted")
        row.addWidget(self.status, 1)
        row.addWidget(button("ÐšÐ¾Ð¿Ð¸Ñ€Ð¾Ð²Ð°Ñ‚ÑŒ", callback=self.copy))
        row.addWidget(button("Ð¡Ð¾Ñ…Ñ€Ð°Ð½Ð¸Ñ‚ÑŒ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚", "action", self.save))
        layout.addLayout(row)

    def copy(self):
        QApplication.clipboard().setText(self.editor.toPlainText())
        self.status.setText("Ð¢ÐµÐºÑÑ‚ ÑÐºÐ¾Ð¿Ð¸Ñ€Ð¾Ð²Ð°Ð½")

    def save(self):
        path, selected = QFileDialog.getSaveFileName(
            self, "Ð¡Ð¾Ñ…Ñ€Ð°Ð½Ð¸Ñ‚ÑŒ Ð¾Ñ‚Ñ‡Ñ‘Ñ‚", "before-report.html", "HTML (*.html);;Markdown (*.md)"
        )
        if not path:
            return
        output = Path(path)
        if not output.suffix:
            output = output.with_suffix(".md" if selected.startswith("Markdown") else ".html")
        try:
            text = self.editor.toPlainText()
            atomic_write(
                output, html_report(text) if output.suffix.lower() in (".html", ".htm") else text
            )
            self.status.setText("ÐžÑ‚Ñ‡Ñ‘Ñ‚ ÑÐ¾Ñ…Ñ€Ð°Ð½Ñ‘Ð½")
        except OSError as exc:
            QMessageBox.warning(self, "ÐÐµ ÑƒÐ´Ð°Ð»Ð¾ÑÑŒ ÑÐ¾Ñ…Ñ€Ð°Ð½Ð¸Ñ‚ÑŒ", str(exc))


class Window(QMainWindow):
    def __init__(self, store: Store | None = None):
        super().__init__()
        self.store = store or Store()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self._task = None
        self.busy = False
        self.baseline: Snapshot | None = None
        self.analysis: Analysis | None = None
        self.demo = False
        self.symptom = "all"
        self.setWindowTitle("BEFORE Â· Ð§Ñ‚Ð¾ Ð¸Ð·Ð¼ÐµÐ½Ð¸Ð»Ð¾ÑÑŒ?")
        self.setMinimumSize(960, 680)
        self.resize(1190, 810)
        icon = Path(__file__).parent / "assets/icon.png"
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)
        self._build_sidebar(root_layout)
        self._build_main(root_layout)
        self.refresh_history()
        self.render_empty()

    def _build_sidebar(self, root):
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(248)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(22, 30, 22, 20)
        layout.setSpacing(13)
        layout.addWidget(label("â—´ BEFORE", "brand"))
        layout.addWidget(label("Ð’Ð•Ð ÐÐ˜Ð¡Ð¬ Ðš Ð¤ÐÐšÐ¢ÐÐœ", "sideCaption"))
        layout.addSpacing(26)
        row = QHBoxLayout()
        row.addWidget(label("Ð Ð°Ð±Ð¾Ñ‡Ð¸Ðµ ÑÐ¾ÑÑ‚Ð¾ÑÐ½Ð¸Ñ", "sideTitle"), 1)
        self.history_count = label("00", "sideCaption")
        row.addWidget(self.history_count)
        layout.addLayout(row)
        self.history = QListWidget()
        self.history.setObjectName("history")
        self.history.setSpacing(1)
        self.history.itemSelectionChanged.connect(self.select_baseline)
        self.history.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history.customContextMenuRequested.connect(self.history_menu)
        self.history.setToolTip(
            "Ð’Ñ‹Ð±ÐµÑ€Ð¸ ÑÐ¾ÑÑ‚Ð¾ÑÐ½Ð¸Ðµ, Ñ ÐºÐ¾Ñ‚Ð¾Ñ€Ñ‹Ð¼ ÑÑ€Ð°Ð²Ð½Ð¸Ñ‚ÑŒ Ñ‚ÐµÐºÑƒÑ‰Ð¸Ðµ Ð½Ð°ÑÑ‚Ñ€Ð¾Ð¹ÐºÐ¸. ÐŸÑ€Ð°Ð²Ñ‹Ð¹ ÐºÐ»Ð¸Ðº: ÑÐºÑÐ¿Ð¾Ñ€Ñ‚ Ð¸Ð»Ð¸ ÑƒÐ´Ð°Ð»ÐµÐ½Ð¸Ðµ."
        )
        layout.addWidget(self.history, 1)
        self.capture_button = button("ï¼‹  Ð¡Ð¾Ñ…Ñ€Ð°Ð½Ð¸Ñ‚ÑŒ ÑÐ¾ÑÑ‚Ð¾ÑÐ½Ð¸Ðµ", "primary", self.save_snapshot)
        self.capture_button.setObjectName("primary")
        layout.addWidget(self.capture_button)
        self.import_button = button("Ð˜Ð¼Ð¿Ð¾Ñ€Ñ‚ ÑÐ½Ð¸Ð¼ÐºÐ°â€¦", "sideLink", self.import_snapshot)
        layout.addWidget(self.import_button)
        layout.addSpacing(10)
        layout.addWidget(label("Ð›Ð¾ÐºÐ°Ð»ÑŒÐ½Ñ‹Ðµ Ð´Ð°Ð½Ð½Ñ‹Ðµ.\nÐŸÐ¾Ð´ Ñ‚Ð²Ð¾Ð¸Ð¼ ÐºÐ¾Ð½Ñ‚Ñ€Ð¾Ð»ÐµÐ¼.", "sideCaption"))
        about = button(f"Ðž Ð¿Ñ€Ð¾Ð³Ñ€Ð°Ð¼Ð¼Ðµ Â· {__version__}", "sideLink", self.about)
        layout.addWidget(about)
        root.addWidget(side)

    def _build_main(self, root):
        main = QWidget()
        main.setObjectName("main")
        layout = QVBoxLayout(main)
        layout.setContentsMargins(32, 28, 30, 20)
        layout.setSpacing(15)
        top = QHBoxLayout()
        top.addWidget(label("Ð’Ð§Ð•Ð Ð Ð ÐÐ‘ÐžÐ¢ÐÐ›Ðž", "eyebrow"), 1)
        self.mode_pill = label("Ð¢Ð¾Ð»ÑŒÐºÐ¾ Ñ‡Ñ‚ÐµÐ½Ð¸Ðµ", "pill")
        top.addWidget(self.mode_pill)
        layout.addLayout(top)
        header = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(7)
        title.addWidget(label("Ð§Ñ‚Ð¾ Ð¸Ð·Ð¼ÐµÐ½Ð¸Ð»Ð¾ÑÑŒ?", "heading"))
        self.subtitle = label(
            "Ð¡Ð¾Ñ…Ñ€Ð°Ð½Ð¸ Ñ€Ð°Ð±Ð¾Ñ‡ÑƒÑŽ Ñ‚Ð¾Ñ‡ÐºÑƒ. Ð¡Ñ€Ð°Ð²Ð½Ð¸, ÐºÐ¾Ð³Ð´Ð° Ñ‡Ñ‚Ð¾-Ñ‚Ð¾ Ð¿Ð¾Ð¹Ð´Ñ‘Ñ‚ Ð½Ðµ Ñ‚Ð°Ðº.", "subheading", True
        )
        title.addWidget(self.subtitle)
        header.addLayout(title, 1)
        self.compare_button = button("Ð¡Ñ€Ð°Ð²Ð½Ð¸Ñ‚ÑŒ ÑÐµÐ¹Ñ‡Ð°Ñ  â†—", "action", self.run_diagnosis)
        self.compare_button.setToolTip(
            "ÐŸÑ€Ð¾Ñ‡Ð¸Ñ‚Ð°Ñ‚ÑŒ Ñ‚ÐµÐºÑƒÑ‰Ð¸Ðµ Ð½Ð°ÑÑ‚Ñ€Ð¾Ð¹ÐºÐ¸ Ð¸ ÑÑ€Ð°Ð²Ð½Ð¸Ñ‚ÑŒ Ñ Ð²Ñ‹Ð±Ñ€Ð°Ð½Ð½Ñ‹Ð¼ ÑÐ¾ÑÑ‚Ð¾ÑÐ½Ð¸ÐµÐ¼."
        )
        header.addWidget(self.compare_button)
        layout.addLayout(header)
        self.demo_bar = QWidget()
        demo_row = QHBoxLayout(self.demo_bar)
        demo_row.setContentsMargins(0, 0, 0, 0)
        demo_row.addWidget(
            label("ÐŸÐ Ð˜ÐœÐ•Ð  Â· Ð²Ñ‹Ð¼Ñ‹ÑˆÐ»ÐµÐ½Ð½Ñ‹Ðµ Ð´Ð°Ð½Ð½Ñ‹Ðµ, Ð¿Ñ€Ð¾Ð²ÐµÑ€ÐºÐ° ÐŸÐš Ð½Ðµ Ð²Ñ‹Ð¿Ð¾Ð»Ð½ÑÐ»Ð°ÑÑŒ", "demoPill"), 1
        )
        demo_row.addWidget(button("Ðš Ð¼Ð¾ÐµÐ¼Ñƒ ÐºÐ¾Ð¼Ð¿ÑŒÑŽÑ‚ÐµÑ€Ñƒ", "link", self.leave_demo))
        self.demo_bar.hide()
        layout.addWidget(self.demo_bar)
        self.filter_container = QWidget()
        filter_row = QHBoxLayout(self.filter_container)
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_frame = QFrame()
        filter_frame.setObjectName("filters")
        filters = QHBoxLayout(filter_frame)
        filters.setContentsMargins(3, 3, 3, 3)
        filters.setSpacing(2)
        self.filter_group = QButtonGroup(self)
        for i, (text, mode) in enumerate(
            (("Ð’ÑÐµ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ", "all"), ("Ð˜Ð½Ñ‚ÐµÑ€Ð½ÐµÑ‚", "internet"), ("ÐšÐ¾Ð¼Ð°Ð½Ð´Ð°", "command"))
        ):
            item = button(text, "filter")
            item.setCheckable(True)
            item.setChecked(i == 0)
            item.clicked.connect(lambda checked=False, m=mode: self.change_symptom(m))
            self.filter_group.addButton(item)
            filters.addWidget(item)
        filter_row.addWidget(filter_frame)
        filter_row.addStretch()
        self.report_button = button("ÐžÑ‚Ñ‡Ñ‘Ñ‚â€¦", callback=self.open_report)
        self.report_button.setEnabled(False)
        filter_row.addWidget(self.report_button)
        layout.addWidget(self.filter_container)
        self.command_row = QWidget()
        commands = QHBoxLayout(self.command_row)
        commands.setContentsMargins(0, 0, 0, 0)
        self.command_edit = QLineEdit()
        self.command_edit.setObjectName("commandInput")
        self.command_edit.setPlaceholderText("Ð˜Ð¼Ñ ÐºÐ¾Ð¼Ð°Ð½Ð´Ñ‹, Ð½Ð°Ð¿Ñ€Ð¸Ð¼ÐµÑ€ python Ð¸Ð»Ð¸ ffmpeg")
        self.command_edit.setMaxLength(100)
        self.command_edit.returnPressed.connect(self.run_diagnosis)
        commands.addWidget(self.command_edit, 1)
        commands.addWidget(label("Ð‘ÐµÐ· Ð·Ð°Ð¿ÑƒÑÐºÐ° ÐºÐ¾Ð¼Ð°Ð½Ð´Ñ‹", "muted"))
        self.command_row.hide()
        layout.addWidget(self.command_row)
        self.network_row = QWidget()
        network = QHBoxLayout(self.network_row)
        network.setContentsMargins(0, 0, 0, 0)
        self.network_check = QCheckBox("ÐŸÑ€Ð¾Ð²ÐµÑ€Ð¸Ñ‚ÑŒ Ð¿Ñ€ÑÐ¼Ð¾Ð¹ Ð¼Ð°Ñ€ÑˆÑ€ÑƒÑ‚ Ð¸ Ð¿Ñ€Ð¾ÐºÑÐ¸ Ðº ÑÐ°Ð¹Ñ‚Ñƒ")
        self.network_check.setToolTip(
            "ÐžÑ‚Ð¿Ñ€Ð°Ð²Ð¸Ñ‚ÑŒ Ð¾Ð±Ñ‹Ñ‡Ð½Ñ‹Ðµ HTTPS HEAD-Ð·Ð°Ð¿Ñ€Ð¾ÑÑ‹. ÐŸÑ€ÑÐ¼Ð¾Ð¹ Ð·Ð°Ð¿Ñ€Ð¾Ñ Ð¾Ð±Ñ…Ð¾Ð´Ð¸Ñ‚ ÑÐ²Ð½Ñ‹Ð¹ Ð¿Ñ€Ð¾ÐºÑÐ¸; Ð¾Ñ‚Ñ‡Ñ‘Ñ‚ Ð¸ Ð½Ð°ÑÑ‚Ñ€Ð¾Ð¹ÐºÐ¸ Ð½Ð¸ÐºÑƒÐ´Ð° Ð½Ðµ Ð¾Ñ‚Ð¿Ñ€Ð°Ð²Ð»ÑÑŽÑ‚ÑÑ."
        )
        self.network_check.toggled.connect(lambda checked: self.host_edit.setEnabled(checked))
        network.addWidget(self.network_check, 1)
        self.host_edit = QLineEdit("example.com")
        self.host_edit.setObjectName("hostInput")
        self.host_edit.setFixedWidth(170)
        self.host_edit.setEnabled(False)
        network.addWidget(self.host_edit)
        self.network_row.hide()
        layout.addWidget(self.network_row)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self.scroll, 1)
        footer = QHBoxLayout()
        self.status = label("Ð“Ð¾Ñ‚Ð¾Ð²Ð¾ Ðº Ð¿ÐµÑ€Ð²Ð¾Ð¹ Ñ€Ð°Ð±Ð¾Ñ‡ÐµÐ¹ Ñ‚Ð¾Ñ‡ÐºÐµ", "tiny", True)
        footer.addWidget(self.status, 1)
        footer.addWidget(label("Ð¡Ð½Ð°Ñ‡Ð°Ð»Ð° Ð´Ð¾ÐºÐ°Ð·Ð°Ñ‚ÐµÐ»ÑŒÑÑ‚Ð²Ð°.", "tiny"))
        layout.addLayout(footer)
        root.addWidget(main, 1)

    def content(self) -> QVBoxLayout:
        old = self.scroll.takeWidget()
        if old:
            old.deleteLater()
        widget = QWidget()
        widget.setObjectName("canvas")
        layout = QVBoxLayout(widget)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        layout.setContentsMargins(0, 0, 5, 3)
        layout.setSpacing(13)
        self.scroll.setWidget(widget)
        return layout

    def refresh_history(self, select_id: str | None = None):
        selected = select_id or (self.baseline.id if self.baseline else None)
        self.history.blockSignals(True)
        self.history.clear()
        snapshots = self.store.list()
        self.history_count.setText(f"{len(snapshots):02}")
        for snapshot in snapshots:
            text = f"{snapshot.label}\n{timestamp(snapshot.captured_at)}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, snapshot.id)
            item.setToolTip(
                f"{snapshot.label}\n{snapshot.platform}\n{timestamp(snapshot.captured_at)}"
            )
            item.setSizeHint(QSize(200, 67))
            self.history.addItem(item)
            if snapshot.id == selected:
                self.history.setCurrentItem(item)
        self.history.blockSignals(False)
        if select_id:
            self.baseline = self.store.get(select_id)
        elif self.history.currentItem() is None:
            self.baseline = None
        self.update_subtitle()

    def update_subtitle(self):
        if self.baseline:
            self.subtitle.setText(
                f"Ð Ð°Ð±Ð¾Ñ‡Ð°Ñ Ñ‚Ð¾Ñ‡ÐºÐ°: {self.baseline.label} Â· {timestamp(self.baseline.captured_at)}"
            )
        else:
            self.subtitle.setText("Ð¡Ð¾Ñ…Ñ€Ð°Ð½Ð¸ Ñ€Ð°Ð±Ð¾Ñ‡ÑƒÑŽ Ñ‚Ð¾Ñ‡ÐºÑƒ. Ð¡Ñ€Ð°Ð²Ð½Ð¸, ÐºÐ¾Ð³Ð´Ð° Ñ‡Ñ‚Ð¾-Ñ‚Ð¾ Ð¿Ð¾Ð¹Ð´Ñ‘Ñ‚ Ð½Ðµ Ñ‚Ð°Ðº.")

    def render_empty(self):
        self.analysis = None
        self.report_button.setEnabled(False)
        layout = self.content()
        layout.addStretch(1)
   -v÷]í¢G§²ÚîÆ­yÛÀÜ®ãÎY'”)÷»ëÎ~Gˆ-~ú	O?ÀÜ±¡®€L¥Rzlùì†Ï:{cŸzÿ¦’@Þçî;ÿ™^ýâW™KÿíÀàÆ>~O~mþÎKmÙ¡ª«†7]ÝÃoö!4oÝILO­zx:hšÁ2nkºñìúj™Õ<Ô(*DöSÆ}ß$2ºûúðùžLuJ6%”/q×.ó¸Ü®¦®?ß¤SÐ7mÚ¢¦&Ç§6÷sÚdÇ¬î¦¶?Ü§³IÔ¿$áÏØûÙÌ^I+”” Ñ6C<XdÝ„ß{äF)í>U•Jëwÿ¶?Ëë«´ÐÛ\2màý â8’f2K,VãŽYbíéïÿ÷†)¯?—	-™Ñ\|«ü§õ¦Þ…ÏŸwÎ¥½!Ù~Ôxÿ›=˜/qç.Ž±vövëèâÛ”38m\r^{{`vÜók]ÞA#Ð´Ÿ€àH„ßwÕE8if¶Wþ1P‰T¼jºE;–ç»ÜÏ¯²&‘O—õøÝ€°[š¼÷¨Un¥­"¢Müc‚- êWŒ­é}J¦pÞrÒ_ö»®5>½½"Áýü\?{üÓ¥P{t!eÁT.™¥Ì›<sÔÞò=Q_‰û^ “÷Üó,-_GbQPŸüÃ	Ä’%Stì=Ç^¶>I'œÅëG°Œu¼!%ŽKþî*m¿ðø.}dÅ³¨}8T´I+
DAÿü>\H(e §.;÷ö{É}ú'}m1µw~I6+Ä“&h¢­{o*÷ÿÐâF#DöÓÐ¶á{eØðgÉ²ùÇ¼û”/ýZëéá‚0~©` 1VWž«¯?1gŽö”u”™ÛóËxýâV|óÐ‰77´f´òÅù—Dûµ­>E1{Kß¾¼õ­¡*É›•Ù»ûQÿÊÿþö!à‰¢viUd'£ßÙ>pò*®¸ÿ?/ª[§ëíg›Õ­ßÇƒõ<L;¦èd¨WoØó‰ýy›*¦µó²+ßCF{ÀÑ±lI>Ä·%}æ;{äØ–¥½0ØjÝ¨ôGsã§Í¥¡!‹m9fºÿ­ègýòû#_½æ	òù" Ò‘LÇñÅu šóî~Á»´¸K$"Û·CBaƒß9ó?ö`}ñì†j˜F6	¯ñB
ƒ¬jeÒg¾g0]4žW+Ü‡¬>%ãî{~¦Y1Pb»­wï›Ì™ïÈ¼Æ,ZÕÕÅûù~.ãåOÿ&jWm¡¡)èn@p(1T`â8X?Î¥>}}iµwûß_Wçª&”ó×K«UÕ}‹t1cÃ»ûöúŸD65ó±—««OEèö¤¨AÖ¾‹®Ž^62ÏOFD·¯Ò_H”X.ÍÕÌo÷ZÏŽG|BV3!«¯ˆóïÑ­ ¥¥ª¹)_5‹±T&üUÓçW@£·È¬ý?Ã´ùêwÞi3SKEáìc
B”Æ¢hr î|ý¼éNš7Ùhï/#ñçŽŒ±ñ˜/þá8eüT†–¯ü5TŒvŸüÕÏ*»ÕÝ,mä?³¿ˆœ>õ ò…qýÂ (AÖ¿“Ý]5Ÿ*¦·vm•ê.P»EbcÿëG¿fÏ­CÝxú‹j¤(Ã»´4ºéÐYÚ¦®®ß#I:ú7¯ßÃÒ”’W®¼ @T¼h›!˜*óï²&qû%ök®¼%ã¢îþ`ÀL¹A T" ÿo¶	/8p§=Ö_H–F2Ë³U4±fÒyÊªI)GD‚‚|ÞdâæÞùüjeÐ}ëö—“Çýz0«Ñ\F(X4Na,=sÀ¹«¨I—¸õ?ý–½¸ªwù(SŠˆÄ“'hã¿ï¦a¯³a}+'Ž>ö2¯qù¥`@Ñ…¼É•¨-uÅ£Ôëï½í·jÂ]V½´–™)øT•ˆ "¾ÓÎ
/<p&U—»¬H$oóë%—’É÷l6APWç,†À²˜k:xÎeŠ‡ßºýÖÝÜí,Zµ^žü‹AR áïv›<c¢ZÉ)ÿö–@¼òÞhöìíSV|‹AR ã»ÿÒgAéd³œ:[ñ¤…Áç~­APlT ‹Rä]±Æaï_ºýÚíÛ5;Z»e²›qýÂ¤à@ÐÂ,Y9¹‹3a›2‹W­åþ»¬H+¤±fÒ ß¨QMÄ‚ Ñµ›6{bžüÞ²‹¬j¦¸s.Zñ$‘k{6	F5Rpâº.›®qÛ$á–±ÊXJ‹DÁlÚÖÅ·¬ŠFB+üVžˆ #„·®¢<Í¥(.™f{í¾ÓZ³i{ZÖ…	G5R`•jpòÚfFªÁ2Ÿ\z @nËçÎ®m*ïS¦½AR` !±-Ë+àE‹…zß»ë&þI³mêÀ’’küP(©0 qƒŠQE—;òÀ“Xµ´pò@‰Q›¶	FµRPãH”pÄ`ýÅ‘§u_¿-ýÕu·¨uaYäV)ª™ˆ "tkwtêèo«öøü„9¶Í‡u¸15Nžý	FŠ³/š’Mª¢¶7Ýë†ÿêLÛ¼òDÙSò½BR `¿×Î!GÔ’Iø'¿ÄWÔ„PÛbÞÞï÷áÿÃ~­	D%R0à5 Lš5O-/ˆfmn^Üµ Mâ¥	DÄ€N&èwï„AƒX””8V(@Ä‚èº†Ã¤·aÙç,ýs§Iø¢¡W>Dp©ƒPCÛ|½ÓbùÖþ¨P¢:ˆ‹Zìô×Ô%iÝ‰mÙe^™¦¯Û|ÈA
ƒ¬jê¸‡@*šR¸Kµˆ*ðŒ$ÈÛÞêº-‡¡ÑÕ›fÖ¬tŽ’¸>]»·CF{±ihË¶êA!ÁS—šDÄ€bZ¶\ÿLÑÑvwû"—jÒ9§“™l¼{H­Nýÿß>¹‹ß9S³„ˆ "¼ƒæ‘jJ”4û”uûá½ù}
¥jÒ1»ƒ½ºåá"ô”¥tJ$Â¾¿{[7í)ì~»õP¬T„ ;—Cqqðd†o§t‚ü%£ØÒÑž'ä!×Ë±{÷vx‡@Š–-fÑ(—)ìl°© ¡ä¸|3aÆ
m#È…¢0{MSÊr;üõxIÁ¢58"ÞRSþaSPÕ~~€ùø
TD­ç>åL£‘5•B(Ž  BRCx•OÕM\KºÓˆ¢P AT6Š` ¡‰p^2C{tuÏxKRƒ™S% WŒ½v×ÌC¯{a4ÐX;¶#‹¶¦qlòõùö%†q8¨#…ž?òFÏ1LÒ’Q£jGk¾ëû½¡â)Jé §WwüLÄ
¦	²ÙcX™þ+C Æ7STœ£“7çJè’HÆX¿w÷Üó&wüÐ-È£’)1!3JÓ“„„	I(KÄ"ê†§Ä6!" /»{U9]žZëé½ïîö*È"F!ù\ð½Ûà†”’f3ËP½|–l¥Ã}òCÆMÛ~Îî»/ºvbÙ–üžAöÅjàDB¦¸rj„¥=‚B  ÃE×Ä[^ÔßbØ±v7
n¨B‘Ò¦¶/Ï	Î­féŸ0â¥Ml"2Ù·o>hWm§o\å° \”p&¤Õº!&Q¹¤e£¿Áœ’ME8ê¦[6ud0ŽàÌuIloØvX±k>‹~üã…TÐX™dMŽãçl©¤æáRâu„wµeÙ°ÿ!GÖôûGôB‚¸ùzYáP®8ŒFh‚f1Ú@º{/wm5.+ª„ˆ-R_ýõN0aV½8L|^“¬Ëq9ï&‹¨ò¥ ;lÚÞT×k-ÕuÑQ-÷e·)ÕLÄznk$S,É‰¼®C/¢NoB5t¨Sˆ o¼·bçõ ¦X½¼ƒ"¢YêU5X¢:‰ˆ\×Û·¦c<‡ Éµihm¥¡)‰g–4Q\¢ªf(Düb¢¶¶-Pª?E-ß{<wSWdöèGnÈ	t>CÒ’ÀÓJ¤óïné*M‰ïþ÷†#'”¼UD¢ªf(DÂ›ï™ÉÙ»e~iclìAuã^e/x®¡APÌT” à¹lÛ¸¯­oó$âNšÑA|ÚP^A& |³wrUY^ƒ Èu:«’Ç6aT@¢ƒˆ„@íØr“õBš°Á)$ÐY›ë1Çc¨™„ ©8òzíM³{Q[©¿wÝê5¸Í=B®˜R(HT”Áá÷WêÖíéôW¡ô|P-xyQ-õfR)ª—ˆÜ	ynÚe
ºr‚—fpÒŠYfÌH±a©J¸‹ÁR€ i‹Î˜Ûkhë-hh¦*\åÎœˆÒ…ë„Rœ‚ÓÊì/¨Wn%êÿ½?Læs&±Ý=ƒŠZ)©N8‹Rpââ»/ªWo(y}§l9Ô4'yÏ¹“É—ÐP SU!*P»Eb W.ÝË¡‚ê³­4LP,X~é ëÔ5$Ô• E ©Hò]íÞÞÍ›UÚŠÅÁg^æó'SMÍ¯ØÊfÈR”ˆÕvyí™d¯A#”Ž_7!WQPÒ‰¥`Áv#
±zÖuõìì"]Än¦x\ÃŽ³Å2hò*( 	(.\?AøÃ7H”n%íülzR`ó¼ðN·5XR(TÃ¤óÿ°©³-¯!ÕtŽl¥ÃúœÃ×SG© E ©h‘Ò$”Šòù˜.]¸šz2[´‘®‰qû4s2ˆ¨5X>(X 4#2‹7Îýv›Õùpááy ™w‚Ï9ƒ*ÓG‘Í” 	.þ+ÿ§Ý¾ÁçŽûJUƒ½)$ð{†šoŸ†£†*GÄy&{»+Æ]xi˜ÉCLÐÊd	Ï™9—;qO%)¡éWñhR+HU>êPºÅâ|þæ1õï*ìKÑÆ“-4ß<ŒZ<UÖ€ˆRâVïÙÓÃÒ—NDÊôù]“ªÓEqç¶æ’éÈaWñ¨R)Þ‘ªyÈ¥wŠ&ùìjšG$Zã«ëÎ`Ò–ðfÌSm4L#ÕdzN¨FŽöe^	
´çSTŸãsœ½U5	V
˜$(-‹	^ævÝAVþE¸¿‚%—³iÆÁ°½^÷ÏxîT®¼î>»8rè(¨Y7O!–.pé´ÒNžÛAø¢¹®«zŒWÕÑÝììéã’¾Vt,¿"-óéÌ\É¯ÙÊ¦èä¨Aüqµvp½÷”¨{ã¹}ÏÆžI+•Å±ö˜–«ºß€âJjhc?ýØV­{m(‰E¸£‚47LÒ4ïºú3êhj ‹5µÝöPÅŽoDÓ^ýØ·ÿóU® œŠ’éÈ•½‚£§AIÔ{­\¢`óò÷žFËñcx|tÙ»!º÷ÌŒSTŠF)ÜÒèéÍq÷õç2í¦¸r»®I+–ç£JdóãBœåŸ¹RèéÎâ»ÞðV«ó&—Òò•,ÚËÂdWSW-;«ä?Fñ-™ÃÕ:–­Mt5X
êºE'–dÕìˆÝ÷¹J¦ñÜ,€ê»GfF•Õ0ÜõàŽßsù…±nK,TlISµ?´TçÄ=yƒ¿¹ØŠECgëº'¿ì/™tÊÈbù#½cE}ÑtŽl´Á™°Ïßqüvã+Þ#Á4ÜÒ(-ò» Ö}ð|?û¾aÛèbèêÌ „	ßÕnÔ	Áá±`}ýÀ†F!EÙCó‰x±ç›3Æ‘Jçx[e4LR,ZÖÕÆùÓ=WSV]ÈßÁ£|£«0Ë·ÐÄóâÿ‡i>ú=ò¹"…€«}OU>Ë#««Œóß±*yíÙ–}¾o²A!ç¿<Éå¨¯f2èda9¢kØu†½÷®Npùõ²¼øwß[7nÛ“ÿsù†ûû€60æä',);Jßª}ˆ¥vˆF¼þâBõìë+hƒŒVNcSSçþúrkhâ
¥€`‚Tºó¶Ýþc¤ÏGVg·Õž¤j¸-ttç9÷¼Ð{ãy}G~CÚÄ–«ª}ƒ]Ô%³_$ß¹wCž¬}þC¦·sß€7MD”	2˜%ÁvÊäŠß}ôd~ù°ÚtwfËÌÑ 	p¥çÚ§\áÐWZ£å(˜A>¿!©©Œ³ûèy÷à•«¯(< NP«?§OË~ýìŠC6©Á€£Ãwù²Û#µ~ê3å_6†ÎÜý?ó'ˆ4óó÷ž%/¼šµPÏê:’Ø»8ŒýòGýq5¶±<‰‚R¸>|ú[ìzòEŽk!˜+©Û€‹¬j™¦¬éãÈUqÛ”åÒÑŸé“ñJéˆ‡i(z‰…£u…@"0Ÿ«¦ëõ}gùõu÷( œ
¦¸ržxÚ¿ûàÍ1ï_&ÒÞVw 'ÿª/óÌî©ÛïïŽfÞúÊÚöuõø˜ªU öÆûhcýó§Ÿv@]ß?<$’IGûÖ=Ã{î›GVg®ù‰H0òë‡5Àpöš&¼ýà¼ëÎPúóæ65&ûîµçå=÷Ü(®e $Q˜ šŽ±bú¿wß­Kƒ}y/^öŠI`‹÷ýÄÎ¾y]\8¦”h¬Úàêwµf›<sÝûÒÞqëjcK‚Zúz;·öÿâ~]çòÇSSØ´½S¤È¥Ôq%uvs}îe}ú&›˜i²í¼~ú˜$s,†\×æÿðáãœ¯@Ö5rÚ
\Ô¿f\¥Ãt7¿ŽoäSÅâ‘~ÔbÛµC~c“V_“ùî|h,?Âî¸q/ÓNOÀrü‹³ÍÝö3å_?¦\ï¦ëzUuöqÖ¿¿‹¯Üóë]ÝK~A(ÜÁg”‡®‘Lç¨nKqëaß$3J¦ñ_{oItüfñÛÕÛºë¶Ÿ‘Í1=Ss~M . Cxzs:í+ë£òÍ%ß—ìÔÚô@Ž|¿Êtû½ûäªÅbaÀQ ^Ì¿¢ê!Itç8éì‰ßpö}ÄMQÈ±õ¿…Ôq$ðE‡÷iwq×®ÎÉ_)TnX áHûÇµ=Ç¹îŸGF{»^ÖyÐ‘ œh/Îí_Ëôÿ/{twSW÷ü{€ºwÁõÐé<ÐkŠèo{>ÔÞð=_#Ÿ1ø&Îü.ÊÌ÷6œÿÄôëkOŠG-Ë€ 8^WˆGûÖ=Ã1O£³¡î¿­é¹ýµvröìïãÄ=yƒ‡L®B¹.ˆÒ¥"EÖ5‹FŠ@Üåï8Sûë¿™Çš³Æ‘NçJZû~³ã}'žç¯YfýØ_ÆÉù@B6˜&(-62¿qüôÏ8k|ôÖ˜üâ8pÆ#ˆ±wÈ˜=ÿ½åZöÚUàñá¨‚u€.¿ºMås4Þw=~z$˜e³ÿïÑöÞÿõBjí½þ3]]·½Ì• Öˆ€j™…dÙI)ºïÍqÛTæÐ+Ðîo¾è¹JëSS#5ybâ)ÿàHíÜp’F0H8nÌ!ó>,‘®‰qÇ¶åqÛ”æ0aU<ë•?«¥|öµíNy}~Öví½þ3Ù¥×È~J@Ò#ÉæOnýàe]qì»¶È!ü-ò“TSSbÞ¾M|þÆQœX±Ÿ¾x;Š& œº-n”äÿ½§ãŸ<î.¼æ^§MO,U,–ûöüùÕ±%ŽKT®ÝËœ¶>I'W1ü2P püÅ`¡cqó¬•qçuäSÉšýDFÅõìéãë%”óÎ¯—³oM¡°B6-¶ºÈ©«HÕ6 Ba-zŠ˜Û½à_Î¼æ^§MhÆ,ÛæðäÁVP¸áIIloŽW½Ë¿ýîq0©<ÐY[ü2Pð5";Ø2]}ÌºÝÿÄÈ)-®8 ü³ ¤/úÒzž}sßÝ‹nI`³svYi¤Üõ?íó{Tº¶Œnç£Jeñƒxe2pð+.Êô51‰€ÛßâþŽ’ÿò~^ôŠ} £Cßó'ÇÁn<å¼)ãÊTÐÐ›&“é\¯BNyB.%–.³óÍZyéˆ¦¾¿{¥
Þ—£Ô´rù„a;à†HýZõcÒÛÇSS`òÖV,üòOÝû€ÐjjKtŸù;Ìq$KÀÒûîµçòÇ„Ñ4£üPÐ	wÞëý:dÂîøÒ}fÌŸCVdnBò<¼ê¸F.yvã-­å—DÚ³m4êU\Ô‹DB†Cxv«â‰À‹¥§Â»¯‹bI‹G
ÈrŠÄCŒš3“w¾gçÏ9ƒKPY†òº!”äxÃ—ßÎß··m}w-ýq6µ]ÌÇrÊâ„‚_¢éû½4ë¦Ì]Ë×ÕÌ¤Z´-k×îÅs„BÅbaE‹¯˜ÙX»
¨Wmcßé;klÎao@&5Ñ­øxÏ¼{×¾û…7,EãüKw¿>Äu3/Êò~þ¸»:&ŽaçX:pÖ9M<m5´2Í¡L¢cw-XÉEI(\†‚Ø»;ˆþ³ŒmÕiêcW]^PR½:™Mç›÷1º÷ŒŒÐÛVC¨jpÙƒ|¯@ÑHˆH5…d8ÞŸbêæ4Ý{'kTïbû´ w¶g¹–¹­¢ë[´—Òóóyï±åˆê8°fïØr‘LJ™""ëèâ¶ŒlçµtÏëÒÅ2kK"YéŠÄÂ[•C"lâ8rÑGn8¶'!7Ã!¿Ë£½çzDªä¸,””Š\¿CVeóGóôýs*ç¼öU²Ú”7{8å|2Bë†"‡¢ao:81ïÝÒÉÕÌmíØu‹oXÑÕ›fÞÜOmË ³6óÖÄ³œwüþ…Ü-tˆd”h/GaQNHÄœßDêšD&MDêêG˜“Åà¤–™¥ŽiÛÝìr³çéJè"‚Øû;š7ïãØ?ÃÈ]Ml]!U™t¹(ê |JãK—^{}÷™S[&“Ï€ºc gÝ®i ÝÓ„w@F–Ë™‹DšO*O,Wfö®öîµÛè÷tŸÏE ¤dýÄ’ÕÕÇ2‰7Î!hhnM„K$"ë™·ZÕ·?ÖÜ¶$Ž”\x3È€Q|Ä !cÃâ¯ó£ï>O«(¦^ü|  úEÝ×š`â–þï•‹:uìªÛ¶C.d³ç“DÜø&³¬jh˜"1qpŠâÜ^8Åw¼RÜ·ÀaCéÏÿÔÈèðqH+¤IDÚ³5ÿû[ý„v%’QA!_|>P 0ê¹G"obÛ‘]?Ÿo9ŸKYJ¤óØBºˆùXKÁáeÇ>˜‚¿PIØaTèJ„%«¯ŠÐ}+Îÿþöaó±—Êä‹&icƒ*œ” ¼6’ëÈÐØ–eÿÔpºï¨rji­"ŸÈâ9Sî&ßEfA1Å¶úÎJ÷Ñ=³jÂjèâj›Õ§®ÏŠ´ aƒñ`ïVUŸ*¦µsö&åóÂÍ#Y&,â8sÃ®Á«ßñÊ*RK–½»‹œýw¬½¼€h5ç–ñôsv˜àÙ( …LÔ(æM‹E›ªÓEqû4pøã<N	qÙÀ)ˆªDŒ.€ŠãI—d¬mçñž-gÛ)p'&j¡ËÜ$”"~3/13M›ªÑXºÿ™sšùÿj‚WX*¹ÒGºD—B­{o[Âõ­ C+t}Pp›B‚\¯‹cÈµ4ÅI+Êç¶pd8qG`P4N4k³gWI”š 5îEH«þ âsdY­Il]Ÿ¸;Ž
/9“ë1Ä’ME3ÍÃ¥°Ö!<
™Â§WdÐ´Ù·c..ýo/>µ›?¹Û<N!äôC+Á<q(~ÁµnK4P"7<êÉä˜p9…lÚŠŽ~aŠnƒ Š• ‘á‹€âHöïkKpR£d”2¹­½¦~té´ÑÏ™;•wM=‡’GSSÁwÞ!Élãr4Ý’k‚
-žá»§õá—(…Ñu@¡c³aêÕ¿±‹&ˆ6±f×ô··4ªäÞÐ `›Ðrƒ„TTå‡8þ%¦ž=‡Ús%2ks!E{7®ëb–8óÚ8Á¿Ô:ý¹ÿÂ1MÐm§=©w\"Õ
9[kaï¡iµoßÏž–mfÍÈmlÚÞE;—Fk:¨T”CýëCÜ13ML×Ô'8î&¦ž5›F2lÂ
[X««Ž
œ‚Ù^É­jØÜz­S+¯WÛÖ¸Öâž#ãìE„u7Îè0¦%<™vµ|ŸnÜuƒ¯˜Ûyrþ´oÝÇ¡€k-ÈÁ	ëÞ@8¼²¢8EŸVJ†;¼fâ¸ß—XÑ´³/¸ùDnnJÒÐÛ@êš'DœÜÅû ‹D@ž=µ¢
êèã† Ý×cBöd¿ÒïHÍºT»·´dÁí\îó'8tf÷Ì@îÜ~‘µ|Ÿïnë!–,â;Ñ˜M0ŽV¢MùâŒ‚ æóOw¯3ÎiÙs¥ëœ$hjLÒ9¸‘Féu¡¥¶‚–ÔmÛxHjâ¹^2M;—fÊ¦´ÒÛm‡ÚãJ–¬®§i{7§¼h†lÏÂê6˜êF‹¼ ¡Â;»3Î7BÚöùÿ-ÊAH‰+]¯îG÷c{¼x24AÑÜX{÷ýG{daôS÷Ý9Ë²÷cwÌ";³»¯u¬{ûëÂæ(SVJ «—"²õ¾Ó)àU‹éLV(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Á( R(Œ„ Ãü}ÃŠ¾+X¬<   %9¹	‚