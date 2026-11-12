"""Export only the evidence the user previews, with escaping and path redaction."""

from __future__ import annotations

import html
import re
from pathlib import Path

from . import __version__
from .engine import SECTION_NAMES
from .models import Analysis


def redact(text: str) -> str:
    text = re.sub(r"(?i)(https?|socks5?h?)://[^\s/@]+@", r"\1://[credentials removed]@", text)
    text = re.sub(r"(?i)[a-z]:[\\/]Users[\\/][^\\/\s<>\"']+", "%USERPROFILE%", text)
    text = re.sub(r"/(?:home|Users)/[^/\s<>\"']+", "~", text)
    local_home = str(Path.home())
    if len(local_home) > 1:
        text = text.replace(local_home, "~")
    return text


def markdown(analysis: Analysis, private: bool = True) -> str:
    lines = [
        f"# BEFORE · отчёт {__version__}",
        "",
        f"Система: {analysis.current.platform}",
        f"Проверка: {analysis.current.captured_at}",
    ]
    if analysis.baseline:
        lines.append(f"Рабочий снимок: {analysis.baseline.label} ({analysis.baseline.captured_at})")
    if analysis.command:
        lines.append(f"Команда: {analysis.command}")
    lines.extend(["", "## Результаты", ""])
    if not analysis.findings:
        lines.append(
            "В проверенных данных нет подходящего объяснения проблемы. Это не подтверждает исправность компьютера."
        )
    for finding in analysis.findings:
        certainty = "Факт" if finding.certainty == "fact" else "Гипотеза"
        lines.extend(
            [
                f"### {finding.title}",
                "",
                f"{certainty} · {finding.rule}",
                "",
                finding.explanation,
                "",
            ]
        )
        lines.extend(f"- {x}" for x in finding.evidence)
        lines.extend(["", "Что проверить:"])
        lines.extend(f"- {x}" for x in finding.steps)
        lines.append("")
    lines.extend(["", f"## Изменения ({len(analysis.changes)})", ""])
    if not analysis.baseline:
        lines.append("Рабочий снимок не выбран.")
    elif not analysis.changes:
        lines.append("Различий в сопоставимых данных не найдено.")
    for change in analysis.changes:
        lines.extend(
            [
                f"### {SECTION_NAMES[change.section]} · {change.subject}",
                f"Было: {change.before}",
                f"Стало: {change.after}",
                "",
            ]
        )
    lines.extend(["", "## Границы проверки", ""])
    lines.extend(f"- {x}" for x in analysis.limitations)
    lines.extend(
        [
            "",
            "BEFORE не устанавливает причинность по совпадению во времени. BEFORE не изменял настройки системы.",
            "",
        ]
    )
    result = "\n".join(lines)
    return redact(result) if private else result


def html_report(markdown_text: str) -> str:
    """A standalone report. All preview text is escaped; no executable markup."""
    blocks = []
    for line in markdown_text.splitlines():
        safe = html.escape(line)
        if line.startswith("### "):
            blocks.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            blocks.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            blocks.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("- "):
            blocks.append(f"<p class='bullet'>• {html.escape(line[2:])}</p>")
        elif line:
            blocks.append(f"<p>{safe}</p>")
    return (
        """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>BEFORE · Диагностический отчёт</title><style>
*{box-sizing:border-box}body{margin:0;background:#f2f4f1;color:#213330;font:15px/1.7 system-ui,sans-serif}
main{max-width:850px;padding:44px;margin:36px auto;background:white;border:1px solid #dde4dc;border-radius:18px}
h1{font-size:34px;letter-spacing:-1px}h2{margin-top:38px;padding-top:22px;border-top:1px solid #e1e7e0}
h3{font-size:18px;margin:26px 0 9px;color:#136d59}p{margin:8px 0;overflow-wrap:anywhere;white-space:pre-wrap}
.bullet{padding-left:14px} @media print{body{background:white}main{border:0;margin:0;padding:0}}
</style></head><body><main>"""
        + "\n".join(blocks)
        + "</main></body></html>"
    )
