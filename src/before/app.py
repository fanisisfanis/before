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
from .i18n import language, set_language, tr
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


class TranslatedLabel(QLabel):
    def setText(self, text: str) -> None:  # noqa: N802 - Qt API name
        super().setText(tr(text))


class TranslatedButton(QPushButton):
    def setText(self, text: str) -> None:  # noqa: N802 - Qt API name
        super().setText(tr(text))


def label(text: str, name: str = "", wrap: bool = False) -> QLabel:
    widget = TranslatedLabel(tr(text))
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
    widget = TranslatedButton(tr(text))
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
        return datetime.fromisoformat(value).astimezone().strftime("%d.%m.%Y · %H:%M")
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
            (left + 35, tr("ВСЁ РАБОТАЛО"), "#719553"),
            (right - 35, tr("СЕЙЧАС"), "#214e37"),
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
        self.setWindowTitle(tr("BEFORE · Отчёт"))
        self.resize(780, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        layout.addWidget(label("Проверь отчёт перед отправкой", "cardTitle"))
        layout.addWidget(
            label(
                "Имена пользователей в домашних путях скрыты. Адреса серверов, домены и названия программ могут остаться — текст можно отредактировать.",
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
        row.addWidget(button("Копировать", callback=self.copy))
        row.addWidget(button("Сохранить отчёт", "action", self.save))
        layout.addLayout(row)

    def copy(self):
        QApplication.clipboard().setText(self.editor.toPlainText())
        self.status.setText("Текст скопирован")

    def save(self):
        path, selected = QFileDialog.getSaveFileName(
            self, tr("Сохранить отчёт"), "before-report.html", "HTML (*.html);;Markdown (*.md)"
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
            self.status.setText("Отчёт сохранён")
        except OSError as exc:
            QMessageBox.warning(self, tr("Не удалось сохранить"), tr(str(exc)))


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
        self.setWindowTitle(tr("BEFORE · Что изменилось?"))
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
        layout.addWidget(label("◴ BEFORE", "brand"))
        caption_row = QHBoxLayout()
        caption_row.addWidget(label("ВЕРНИСЬ К ФАКТАМ", "sideCaption"), 1)
        language_button = button(
            "РУС" if language() == "en" else "EN", "sideLink", self.switch_language
        )
        language_button.setFixedWidth(52)
        caption_row.addWidget(language_button)
        layout.addLayout(caption_row)
        layout.addSpacing(26)
        row = QHBoxLayout()
        row.addWidget(label("Рабочие состояния", "sideTitle"), 1)
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
            tr(
                "Выбери состояние, с которым сравнить текущие настройки. Правый клик: экспорт или удаление."
            )
        )
        layout.addWidget(self.history, 1)
        self.capture_button = button("＋  Сохранить состояние", "primary", self.save_snapshot)
        self.capture_button.setObjectName("primary")
        layout.addWidget(self.capture_button)
        self.import_button = button("Импорт снимка…", "sideLink", self.import_snapshot)
        layout.addWidget(self.import_button)
        layout.addSpacing(10)
        layout.addWidget(label("Локальные данные.\nПод твоим контролем.", "sideCaption"))
        about = button(f"О программе · {__version__}", "sideLink", self.about)
        layout.addWidget(about)
        root.addWidget(side)

    def _build_main(self, root):
        main = QWidget()
        main.setObjectName("main")
        layout = QVBoxLayout(main)
        layout.setContentsMargins(32, 28, 30, 20)
        layout.setSpacing(15)
        top = QHBoxLayout()
        top.addWidget(label("ВЧЕРА РАБОТАЛО", "eyebrow"), 1)
        self.mode_pill = label("Только чтение", "pill")
        top.addWidget(self.mode_pill)
        layout.addLayout(top)
        header = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(7)
        title.addWidget(label("Что изменилось?", "heading"))
        self.subtitle = label(
            "Сохрани рабочую точку. Сравни, когда что-то пойдёт не так.", "subheading", True
        )
        title.addWidget(self.subtitle)
        header.addLayout(title, 1)
        self.compare_button = button("Сравнить сейчас  ↗", "action", self.run_diagnosis)
        self.compare_button.setToolTip(
            tr("Прочитать текущие настройки и сравнить с выбранным состоянием.")
        )
        header.addWidget(self.compare_button)
        layout.addLayout(header)
        self.demo_bar = QWidget()
        demo_row = QHBoxLayout(self.demo_bar)
        demo_row.setContentsMargins(0, 0, 0, 0)
        demo_row.addWidget(
            label("ПРИМЕР · вымышленные данные, проверка ПК не выполнялась", "demoPill"), 1
        )
        demo_row.addWidget(button("К моему компьютеру", "link", self.leave_demo))
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
            (("Все изменения", "all"), ("Интернет", "internet"), ("Команда", "command"))
        ):
            item = button(text, "filter")
            item.setCheckable(True)
            item.setChecked(i == 0)
            item.clicked.connect(lambda checked=False, m=mode: self.change_symptom(m))
            self.filter_group.addButton(item)
            filters.addWidget(item)
        filter_row.addWidget(filter_frame)
        filter_row.addStretch()
        self.report_button = button("Отчёт…", callback=self.open_report)
        self.report_button.setEnabled(False)
        filter_row.addWidget(self.report_button)
        layout.addWidget(self.filter_container)
        self.command_row = QWidget()
        commands = QHBoxLayout(self.command_row)
        commands.setContentsMargins(0, 0, 0, 0)
        self.command_edit = QLineEdit()
        self.command_edit.setObjectName("commandInput")
        self.command_edit.setPlaceholderText(tr("Имя команды, например python или ffmpeg"))
        self.command_edit.setMaxLength(100)
        self.command_edit.returnPressed.connect(self.run_diagnosis)
        commands.addWidget(self.command_edit, 1)
        commands.addWidget(label("Без запуска команды", "muted"))
        self.command_row.hide()
        layout.addWidget(self.command_row)
        self.network_row = QWidget()
        network = QHBoxLayout(self.network_row)
        network.setContentsMargins(0, 0, 0, 0)
        self.network_check = QCheckBox(tr("Проверить прямой маршрут и прокси к сайту"))
        self.network_check.setToolTip(
            tr(
                "Отправить обычные HTTPS HEAD-запросы. Прямой запрос обходит явный прокси; отчёт и настройки никуда не отправляются."
            )
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
        self.status = label("Готово к первой рабочей точке", "tiny", True)
        footer.addWidget(self.status, 1)
        footer.addWidget(label("Сначала доказательства.", "tiny"))
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
                f"Рабочая точка: {self.baseline.label} · {timestamp(self.baseline.captured_at)}"
            )
        else:
            self.subtitle.setText("Сохрани рабочую точку. Сравни, когда что-то пойдёт не так.")

    def render_empty(self):
        self.analysis = None
        self.report_button.setEnabled(False)
        layout = self.content()
        layout.addStretch(1)
        card, body = frame("card", 30)
        body.addWidget(label("ОДНА ТОЧКА ОТСЧЁТА", "eyebrow"))
        body.addSpacing(3)
        body.addWidget(label("Запомни момент,\nкогда всё работает.", "heroTitle", True))
        body.addWidget(
            label(
                "BEFORE сохранит важные настройки. Когда возникнет проблема, ты увидишь точные изменения и способы проверить причину.",
                "heroText",
                True,
            )
        )
        body.addWidget(Timeline())
        row = QHBoxLayout()
        row.addWidget(button("Сохранить рабочее состояние", "action", self.save_snapshot))
        row.addWidget(button("Проверить без снимка", callback=self.run_diagnosis))
        row.addStretch()
        body.addLayout(row)
        body.addWidget(
            label("Снимок: прокси · PATH · команды · hosts · выбранные службы", "tiny", True)
        )
        layout.addWidget(card)
        row = QHBoxLayout()
        row.addWidget(
            label(
                "Настройки читаются локально. Права администратора обычно не нужны.", "muted", True
            ),
            1,
        )
        row.addWidget(button("Посмотреть пример  ↗", "link", self.show_demo))
        layout.addLayout(row)
        layout.addStretch(2)

    def render_analysis(self):
        if self.analysis is None:
            self.render_empty()
            return
        result = self.analysis
        layout = self.content()
        self.report_button.setEnabled(True)
        summary, body = frame("summary", 20)
        count = len(result.changes)
        if not result.baseline:
            title = "Проверка текущего состояния"
            description = (
                "Рабочей точки пока нет. История изменений станет доступна после сохранения снимка."
            )
        elif count:
            title = f"Зафиксировано изменений: {count}"
            description = (
                "Сравни факты с симптомом. Совпадение по времени ещё не доказывает причину."
            )
        else:
            title = "В сопоставимых настройках изменений нет"
            description = (
                "Это граница этой проверки. Исправность приложений и оборудования не подтверждена."
            )
        row = QHBoxLayout()
        row.addWidget(label(title, "cardTitle", True), 1)
        row.addWidget(label("СНИМОК ↔ СЕЙЧАС" if result.baseline else "СЕЙЧАС", "eyebrow"))
        body.addLayout(row)
        body.addWidget(label(description, "muted", True))
        layout.addWidget(summary)
        if result.findings:
            layout.addWidget(label("ЧТО МОЖНО ПРОВЕРИТЬ", "eyebrow"))
            for finding in result.findings:
                layout.addWidget(self.finding_card(finding))
        else:
            card, body = frame("card")
            body.addWidget(label("Пока нет подходящего объяснения", "cardTitle"))
            body.addWidget(
                label(
                    "Проверь конкретную команду или подключение во вкладках выше. BEFORE показывает только то, что удалось установить.",
                    "muted",
                    True,
                )
            )
            layout.addWidget(card)
        layout.addWidget(self.changes_card(result))
        card, body = frame("notice", 16)
        toggle = button("▸  Границы этой проверки", "details")
        body.addWidget(toggle)
        text = label(tr("\n\n".join(result.limitations)), "muted", True)
        text.hide()
        body.addWidget(text)
        toggle.clicked.connect(lambda: self.toggle_detail(toggle, text, "Границы этой проверки"))
        layout.addWidget(card)
        layout.addStretch()
        self.scroll.verticalScrollBar().setValue(0)

    def finding_card(self, finding):
        card, body = frame("warningCard" if finding.severity == "warning" else "infoCard", 20)
        top = QHBoxLayout()
        top.addWidget(label(tr(finding.title), "cardTitle", True), 1)
        top.addWidget(
            label(
                "ФАКТ" if finding.certainty == "fact" else "ГИПОТЕЗА",
                "fact" if finding.certainty == "fact" else "hypothesis",
            )
        )
        body.addLayout(top)
        body.addWidget(label(tr(finding.explanation), "muted", True))
        details = QWidget()
        detail_layout = QVBoxLayout(details)
        detail_layout.setContentsMargins(0, 5, 0, 0)
        detail_layout.setSpacing(9)
        detail_layout.addWidget(label("ДОКАЗАТЕЛЬСТВА", "eyebrow"))
        for evidence in finding.evidence:
            item = label("•  " + tr(evidence), wrap=True)
            item.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            detail_layout.addWidget(item)
        detail_layout.addSpacing(4)
        detail_layout.addWidget(label("СЛЕДУЮЩИЙ ШАГ", "eyebrow"))
        for step in finding.steps:
            detail_layout.addWidget(label("→  " + tr(step), wrap=True))
        if finding.rule.startswith("proxy") or finding.rule == "local_proxy_unreachable":
            if sys.platform == "win32" and not self.demo:
                detail_layout.addWidget(
                    button(
                        "Открыть настройки прокси Windows",
                        callback=lambda: QDesktopServices.openUrl(
                            QUrl("ms-settings:network-proxy")
                        ),
                    )
                )
        details.setVisible(finding.severity == "warning")
        toggle = button(
            ("▾" if details.isVisible() else "▸") + "  Доказательства и следующий шаг", "details"
        )
        # isVisible() is false while an ancestor is not shown; use hidden state.
        toggle.setText(("▸" if details.isHidden() else "▾") + "  Доказательства и следующий шаг")
        toggle.clicked.connect(
            lambda: self.toggle_detail(toggle, details, "Доказательства и следующий шаг")
        )
        body.addWidget(toggle)
        body.addWidget(details)
        return card

    @staticmethod
    def toggle_detail(toggle, widget, text):
        widget.setVisible(widget.isHidden())
        toggle.setText(("▸" if widget.isHidden() else "▾") + "  " + text)

    def changes_card(self, analysis):
        card, body = frame("card", 20)
        toggle = button(f"▸  Все изменения · {len(analysis.changes)}", "details")
        body.addWidget(toggle)
        details = QWidget()
        changes_layout = QVBoxLayout(details)
        changes_layout.setContentsMargins(0, 5, 0, 0)
        changes_layout.setSpacing(14)
        if not analysis.changes:
            changes_layout.addWidget(
                label(
                    "Нет различий в доступных для сравнения данных."
                    if analysis.baseline
                    else "Сначала выбери рабочий снимок слева.",
                    "muted",
                    True,
                )
            )
        for change in analysis.changes:
            changes_layout.addWidget(
                label(
                    f"{tr(SECTION_NAMES[change.section])}  /  {tr(change.subject)}",
                    "cardTitle",
                    True,
                )
            )
            values = label(tr(f"Было: {change.before}\nСтало: {change.after}"), "muted", True)
            values.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            changes_layout.addWidget(values)
        details.hide()
        toggle.clicked.connect(
            lambda: self.toggle_detail(toggle, details, f"Все изменения · {len(analysis.changes)}")
        )
        body.addWidget(details)
        return card

    def change_symptom(self, value):
        self.symptom = value
        self.command_row.setVisible(value == "command")
        self.network_row.setVisible(value == "internet")
        if self.analysis:
            self.analysis = analyze(
                self.analysis.current,
                self.analysis.baseline,
                value,
                self.command_edit.text().strip() if value == "command" else "",
                self.analysis.probes,
            )
            self.render_analysis()
        if value == "command":
            self.command_edit.setFocus()

    def select_baseline(self):
        item = self.history.currentItem()
        if item is None:
            self.baseline = None
            return
        self.baseline = self.store.get(item.data(Qt.ItemDataRole.UserRole))
        self.demo = False
        self.demo_bar.hide()
        self.mode_pill.setText("Только чтение")
        self.update_subtitle()
        if self.analysis and self.analysis.current.machine_id != "demo":
            self.analysis = analyze(
                self.analysis.current,
                self.baseline,
                self.symptom,
                self.command_edit.text().strip() if self.symptom == "command" else "",
                self.analysis.probes,
            )
            self.render_analysis()
        else:
            self.analysis = None
            layout = self.content()
            layout.addStretch()
            card, body = frame("card", 30)
            body.addWidget(label("ТОЧКА ОТСЧЁТА ВЫБРАНА", "eyebrow"))
            body.addWidget(label(self.baseline.label, "heroTitle", True))
            body.addWidget(
                label(f"{self.baseline.platform} · {timestamp(self.baseline.captured_at)}", "muted")
            )
            body.addSpacing(10)
            body.addWidget(
                label(
                    "Сравни её с текущими настройками компьютера. Проверка покажет точные различия и подходящие объяснения.",
                    "heroText",
                    True,
                )
            )
            body.addWidget(button("Сравнить сейчас", "action", self.run_diagnosis))
            layout.addWidget(card)
            layout.addStretch(2)
            self.report_button.setEnabled(False)
        self.status.setText("Рабочая точка выбрана. Можно сравнивать.")

    def set_busy(self, busy: bool, message: str = ""):
        self.busy = busy
        self.progress.setVisible(busy)
        self.compare_button.setEnabled(not busy)
        self.capture_button.setEnabled(not busy)
        self.import_button.setEnabled(not busy)
        self.history.setEnabled(not busy)
        self.filter_container.setEnabled(not busy)
        self.command_row.setEnabled(not busy)
        self.network_row.setEnabled(not busy)
        # Also disable empty-state actions inside the content while a task runs.
        self.scroll.setEnabled(not busy)
        if message:
            self.status.setText(message)

    def switch_language(self):
        """Switch the whole window immediately; English remains the default next launch."""
        set_language("ru" if language() == "en" else "en")
        replacement = Window(self.store)
        replacement.show()
        QApplication.instance()._before_window = replacement
        self.close()

    def start_task(self, function, done, message):
        if self.busy:
            return
        self.set_busy(True, message)
        task = Task(function)
        self._task = task

        def finished(result):
            self.set_busy(False)
            done(result)

        def failed(error):
            self.set_busy(False, "Проверка не завершена. Подробности в сообщении.")
            QMessageBox.warning(self, tr("BEFORE · Не удалось выполнить"), tr(error))

        task.signals.done.connect(finished)
        task.signals.failed.connect(failed)
        self.pool.start(task)

    def save_snapshot(self):
        if self.busy:
            return
        name, ok = QInputDialog.getText(
            self,
            tr("Рабочее состояние"),
            tr("Сохраняй, когда нужные программы работают.\nНазвание:"),
            text=tr("Всё работает"),
        )
        if not ok or not name.strip():
            return
        custom = self.command_edit.text().strip() if self.symptom == "command" else ""
        if custom and not valid_command(custom):
            QMessageBox.information(
                self, tr("Имя команды"), tr("Введите имя команды без аргументов.")
            )
            return

        def work():
            snapshot = capture(self.store.machine_id, name, custom)
            self.store.save(snapshot)
            return snapshot

        def done(snapshot):
            self.leave_demo(render=False)
            self.analysis = None
            self.refresh_history(snapshot.id)
            self.select_baseline()
            self.status.setText(
                "Состояние сохранено локально. Вернись, когда понадобится сравнение."
            )

        self.start_task(work, done, "Сохраняю рабочую точку…")

    def run_diagnosis(self):
        if self.busy:
            return
        custom = self.command_edit.text().strip() if self.symptom == "command" else ""
        if self.symptom == "command" and not valid_command(custom):
            QMessageBox.information(
                self,
                tr("Имя команды"),
                tr("Введите имя команды, например python или ffmpeg, без аргументов."),
            )
            self.command_edit.setFocus()
            return
        target = None
        if self.symptom == "internet" and self.network_check.isChecked():
            try:
                target = validate_host(self.host_edit.text())
            except (ValueError, UnicodeError) as exc:
                QMessageBox.information(self, tr("Имя сайта"), tr(str(exc)))
                return
        selected = self.baseline
        mode = self.symptom

        def work():
            current = capture(self.store.machine_id, "Текущая проверка", custom)
            probes = {"local_proxy": local_proxy_checks(current)}
            if target:
                probes["network"] = network_checks(current, target)
            return analyze(current, selected, mode, custom, probes)

        def done(result):
            self.leave_demo(render=False)
            self.baseline = selected
            self.analysis = result
            self.update_subtitle()
            self.render_analysis()
            self.status.setText(
                f"Проверено: {timestamp(result.current.captured_at)} · BEFORE не изменял настройки системы"
            )

        self.start_task(work, done, "Проверяю настройки и собираю доказательства…")

    def show_demo(self):
        if self.busy:
            return
        old, current, probes = example()
        self.demo = True
        self.demo_bar.show()
        self.mode_pill.setText("Пример")
        self.subtitle.setText(
            "Два изменения: забытый локальный прокси и исчезнувший каталог Python."
        )
        self.analysis = analyze(
            current, old, self.symptom, "python" if self.symptom == "command" else "", probes
        )
        self.render_analysis()
        self.status.setText(
            "Демонстрация. Данные компьютера не читаются, сетевые запросы не выполняются."
        )

    def leave_demo(self, render=True):
        self.demo = False
        self.demo_bar.hide()
        self.mode_pill.setText("Только чтение")
        self.update_subtitle()
        if render:
            self.analysis = None
            if self.baseline:
                self.select_baseline()
            else:
                self.render_empty()
            self.status.setText("Готово к проверке компьютера")

    def import_snapshot(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Импорт снимка BEFORE"), "", "BEFORE snapshot (*.json)"
        )
        if not path:
            return
        try:
            snapshot = self.store.import_file(Path(path))
            self.refresh_history(snapshot.id)
            self.select_baseline()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, tr("Снимок не импортирован"), tr(str(exc)))

    def history_menu(self, point):
        item = self.history.itemAt(point)
        if item is None or self.busy:
            return
        snapshot_id = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        export_action = menu.addAction(tr("Экспортировать снимок…"))
        delete_action = menu.addAction(tr("Удалить снимок…"))
        selected = menu.exec(self.history.mapToGlobal(point))
        if selected == export_action:
            path, _ = QFileDialog.getSaveFileName(
                self, tr("Экспорт снимка"), "before-snapshot.json", "JSON (*.json)"
            )
            if path:
                try:
                    atomic_write(Path(path), self.store.get(snapshot_id).to_json())
                    self.status.setText(
                        "Снимок экспортирован. Он содержит локальные пути и настройки; для отправки лучше использовать отчёт."
                    )
                except (OSError, ValueError) as exc:
                    QMessageBox.warning(self, tr("Экспорт не выполнен"), tr(str(exc)))
        elif selected == delete_action:
            if (
                QMessageBox.question(
                    self,
                    tr("Удалить рабочую точку?"),
                    tr("Этот снимок будет удалён из локальной истории."),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            ):
                self.store.delete(snapshot_id)
                if self.baseline and self.baseline.id == snapshot_id:
                    self.baseline = None
                    self.analysis = None
                    self.render_empty()
                self.refresh_history()
                self.status.setText("Снимок удалён")

    def open_report(self):
        if self.analysis:
            ReportDialog(self.analysis, self).exec()

    def about(self):
        QMessageBox.information(
            self,
            f"BEFORE {__version__}",
            tr(
                "Сохрани рабочую точку. Сравни настройки, когда возникнет проблема. Проверь доказательства.\n\n"
                "Windows: WinINET, PATH из реестра, команды, hosts, Dhcp/Dnscache/BITS.\n"
                "Linux: прокси и PATH процесса, команды, hosts, NetworkManager/systemd-resolved.\n\n"
                "Снимки не обращаются в интернет. Проверка локального прокси касается только заданного loopback-порта. Внешние HTTPS-запросы включаются отдельно.\n\n"
                "Автоматическое исправление, драйверы, BSOD и аппаратные неисправности в эту версию не входят.\n\n"
                f"Локальные данные: {self.store.directory}\nMIT License · Без аккаунта и телеметрии."
            ),
        )


def main():
    if "--probe-worker" in sys.argv:
        from .probes import worker

        print(json.dumps(worker(json.load(sys.stdin))))
        return
    app = QApplication(sys.argv)
    app.setApplicationName("BEFORE")
    app.setOrganizationName("BEFORE")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setFont(QFont("DejaVu Sans" if sys.platform != "win32" else "Segoe UI", 10))
    try:
        window = Window()
    except (OSError, ValueError, sqlite3.Error) as exc:
        QMessageBox.critical(None, tr("BEFORE · Не удалось открыть историю"), tr(str(exc)))
        return
    window.show()
    if "--demo" in sys.argv:
        QTimer.singleShot(0, window.show_demo)
    if "--smoke" in sys.argv:
        QTimer.singleShot(800, app.quit)
    raise SystemExit(app.exec())
