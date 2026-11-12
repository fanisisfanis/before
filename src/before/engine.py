"""Deterministic comparison and evidence rules. No remote model or guessed score."""

from __future__ import annotations

import ntpath
from datetime import datetime

from .models import Analysis, Change, Finding, Snapshot

SECTION_NAMES = {
    "proxy": "Прокси",
    "path": "PATH",
    "commands": "Команды",
    "hosts": "hosts",
    "services": "Службы",
}


def _show(value) -> str:
    if value is None:
        return "не найдено"
    if isinstance(value, bool):
        return "включено" if value else "выключено"
    return str(value) or "—"


def _path_key(value: str, platform: str) -> str:
    return ntpath.normcase(ntpath.normpath(value)) if platform == "Windows" and value else value


def compare(baseline: Snapshot, current: Snapshot) -> list[Change]:
    changes = []
    for section in SECTION_NAMES:
        old, new = baseline.sections[section], current.sections[section]
        if old.status != "ok" or new.status != "ok":
            continue
        if section == "path":
            before = [x["value"] for x in old.data.get("entries", [])]
            after = [x["value"] for x in new.data.get("entries", [])]
            keys_before = {_path_key(x, baseline.platform) for x in before}
            keys_after = {_path_key(x, current.platform) for x in after}
            for value in dict.fromkeys(before):
                if _path_key(value, baseline.platform) not in keys_after:
                    changes.append(
                        Change(section, value or "Текущий каталог", "в PATH", "удалён из PATH")
                    )
            for value in dict.fromkeys(after):
                if _path_key(value, current.platform) not in keys_before:
                    changes.append(
                        Change(
                            section, value or "Текущий каталог", "не было в PATH", "добавлен в PATH"
                        )
                    )
            if keys_before == keys_after and before != after:
                changes.append(
                    Change(
                        section, "Порядок / повторения PATH", " → ".join(before), " → ".join(after)
                    )
                )
            old_state = {
                _path_key(x["value"], baseline.platform): x.get("exists")
                for x in old.data.get("entries", [])
            }
            for entry in new.data.get("entries", []):
                key = _path_key(entry["value"], current.platform)
                if key in old_state and old_state[key] is True and entry.get("exists") is False:
                    changes.append(
                        Change(section, entry["value"], "каталог существовал", "каталог не найден")
                    )
        elif section == "proxy":
            for source in ("environment", "windows"):
                old_values, new_values = old.data.get(source) or {}, new.data.get(source) or {}
                if (old.data.get(source) is None) != (new.data.get(source) is None):
                    # A collector becoming available is a coverage change, not
                    # proof that every setting was created at that moment.
                    continue
                for key in sorted(set(old_values) | set(new_values)):
                    if old_values.get(key) != new_values.get(key):
                        changes.append(
                            Change(
                                section,
                                f"{source}.{key}",
                                _show(old_values.get(key)),
                                _show(new_values.get(key)),
                            )
                        )
        elif section == "hosts":
            for name in sorted(set(old.data.get("entries", {})) | set(new.data.get("entries", {}))):
                left, right = (
                    old.data.get("entries", {}).get(name),
                    new.data.get("entries", {}).get(name),
                )
                if left != right:
                    changes.append(Change(section, name, _show(left), _show(right)))
        elif section == "services":
            for name in sorted(set(old.data) & set(new.data)):
                for field in ("state", "start"):
                    if old.data[name].get(field) != new.data[name].get(field):
                        changes.append(
                            Change(
                                section,
                                f"{name}.{field}",
                                _show(old.data[name].get(field)),
                                _show(new.data[name].get(field)),
                            )
                        )
        else:
            # Do not claim a regression for a custom command the old snapshot
            # never inspected.
            for name in sorted(set(old.data) & set(new.data)):
                if old.data[name] != new.data[name]:
                    changes.append(
                        Change(section, name, _show(old.data[name]), _show(new.data[name]))
                    )
    return changes


def analyze(
    current: Snapshot,
    baseline: Snapshot | None = None,
    symptom: str = "all",
    command: str = "",
    probes: dict | None = None,
) -> Analysis:
    if symptom not in ("all", "internet", "command"):
        raise ValueError("Неизвестный тип проблемы.")
    probes = probes or {}
    changes = compare(baseline, current) if baseline else []
    findings: list[Finding] = []
    limitations = []
    related = (
        baseline is not None
        and baseline.machine_id == current.machine_id
        and baseline.platform == current.platform
    )
    if baseline and not related:
        limitations.append(
            "Снимки относятся к разным установкам BEFORE или ОС. Различия показаны; связь с поломкой не устанавливается."
        )
    if not baseline:
        limitations.append(
            "Рабочий снимок не выбран. Доступны проверки текущего состояния; историю изменений восстановить нельзя."
        )
    for name, observation in current.sections.items():
        if observation.status != "ok":
            limitations.append(
                f"{SECTION_NAMES[name]}: {observation.note or 'нет доступа к данным'}. Сравнение недоступно."
            )
        elif baseline and baseline.sections[name].status != "ok":
            limitations.append(
                f"{SECTION_NAMES[name]}: в рабочем снимке нет данных; изменения неизвестны."
            )
    limitations.extend(
        filter(
            None,
            (
                current.sections["proxy"].note,
                current.sections["path"].note,
                current.sections["commands"].note,
                current.sections["services"].note,
            ),
        )
    )
    if (
        related
        and baseline
        and datetime.fromisoformat(baseline.captured_at)
        > datetime.fromisoformat(current.captured_at)
    ):
        limitations.append(
            "Выбранный рабочий снимок новее текущего. Порядок событий не подтверждён."
        )
    if symptom in ("all", "internet"):
        _proxy_findings(current, baseline if related else None, probes, findings)
        network = probes.get("network", {})
        if network.get("status") == "unavailable":
            limitations.append(network.get("note", "Сетевая проверка недоступна."))
        if network.get("route_note"):
            limitations.append(network["route_note"])
        if network.get("dns") == "failed":
            findings.append(
                Finding(
                    "dns_failed",
                    "warning",
                    "fact",
                    "Имя сайта не разрешилось",
                    "Системный DNS не вернул адрес проверяемого сайта в этой проверке.",
                    (f"Сайт: {network['host']}", "Результат системного getaddrinfo: ошибка."),
                    (
                        "Проверьте правильность имени сайта.",
                        "Сравните с другим сайтом и другой сетью; это ещё не доказывает неисправность DNS-сервера.",
                    ),
                )
            )
        direct, proxied = network.get("direct", {}), network.get("proxy", {})
        if direct.get("status") == "reachable" and proxied.get("status") == "failed":
            findings.append(
                Finding(
                    "proxy_route_failed",
                    "warning",
                    "fact",
                    "Прямой маршрут отвечает, прокси — нет",
                    "Два HTTPS-запроса к одному сайту дали разные результаты. Причина отказа прокси требует отдельной проверки.",
                    (
                        f"Сайт: {network['host']}",
                        f"Прямой запрос: HTTP {direct.get('http_status')}",
                        f"Через прокси: {proxied.get('error', 'ошибка')}",
                    ),
                    (
                        "Откройте приложение прокси/VPN и проверьте его состояние.",
                        "Проверьте настройки прокси в приложении, где возникла проблема.",
                    ),
                )
            )
        elif direct.get("status") == "reachable":
            findings.append(
                Finding(
                    "direct_route_ok",
                    "info",
                    "fact",
                    "Проверяемый сайт отвечает",
                    "Прямой HTTPS-запрос получил HTTP-ответ. Это не проверка всех сайтов, авторизации или качества соединения.",
                    (f"{network['host']}: HTTP {direct.get('http_status')}",),
                    (
                        "Если проблема сохраняется, проверьте конкретное приложение и его собственный прокси.",
                    ),
                )
            )
        elif direct.get("status") == "failed":
            findings.append(
                Finding(
                    "direct_route_failed",
                    "warning",
                    "fact",
                    "Прямой запрос не прошёл",
                    "Один HTTPS-запрос завершился ошибкой. Сайт, сертификаты или правила сети могут быть причиной.",
                    (f"{network['host']}: {direct.get('error', 'ошибка')}",),
                    (
                        "Повторите проверку с другим сайтом.",
                        "Сравните результат в браузере; не сбрасывайте сеть по одному измерению.",
                    ),
                )
            )
        target = network.get("host", "")
        hosts = current.sections["hosts"].data.get("entries", {})
        if target and target in hosts:
            findings.append(
                Finding(
                    "target_in_hosts",
                    "warning",
                    "hypothesis",
                    "Для сайта есть запись в hosts",
                    "Локальный hosts может изменить адрес, к которому обращается приложение. Запись может быть намеренной.",
                    (f"{target} → {hosts[target]}",),
                    ("Проверьте, нужна ли эта запись. BEFORE не изменяет hosts.",),
                )
            )
        if related and baseline:
            for name, state in current.sections["services"].data.items():
                previous = baseline.sections["services"].data.get(name)
                if (
                    previous
                    and state.get("start") in ("disabled", "masked")
                    and previous.get("start") not in ("disabled", "masked")
                ):
                    findings.append(
                        Finding(
                            "service_disabled",
                            "warning",
                            "hypothesis",
                            f"Отключена служба {name}",
                            "Режим запуска изменился. Влияние на вашу проблему зависит от того, используется ли эта служба.",
                            (f"Раньше: {previous.get('start')}; сейчас: {state.get('start')}",),
                            ("Проверьте назначение службы и причину её отключения.",),
                        )
                    )
    if symptom in ("all", "command"):
        _path_findings(current, baseline if related else None, command, findings)
    # Changes always remain available, even when symptom filtering selects only
    # relevant hypotheses. Coverage notes prevent an empty diff promising health.
    return Analysis(
        current,
        baseline,
        symptom,
        command,
        changes,
        findings,
        list(dict.fromkeys(limitations)),
        probes,
    )


def _proxy_findings(current, baseline, probes, findings):
    data = current.sections["proxy"].data
    windows = data.get("windows") or {}
    if windows.get("pac"):
        findings.append(
            Finding(
                "pac_present",
                "info",
                "fact",
                "Используется автоматическая настройка прокси",
                "Обнаружен PAC. Для него BEFORE показывает изменение настройки, но не исполняет скрипт и не определяет маршрут браузера.",
                ("AutoConfigURL задан.",),
                ("Проверьте PAC и настройки сети в браузере.",),
            )
        )
    for source, result in probes.get("local_proxy", {}).items():
        if result.get("reachable") is False:
            findings.append(
                Finding(
                    "local_proxy_unreachable",
                    "warning",
                    "fact",
                    "Локальный прокси не принимает соединение",
                    "В настройках указан локальный порт, но TCP-соединение к нему не установилось. Приложения, использующие этот прокси, могут терять доступ к сети.",
                    (
                        f"Источник: {source}",
                        f"Адрес: {result['host']}:{result['port']}",
                        "TCP-проверка выполнена сейчас; состояние может измениться.",
                    ),
                    (
                        "Откройте приложение VPN/прокси, которому принадлежит этот порт.",
                        "Проверьте, нужен ли этот прокси сейчас. Учтите собственные настройки браузера.",
                    ),
                )
            )
    if baseline:
        previous = baseline.sections["proxy"]
        if previous.status == "ok" and any(
            x.section == "proxy" for x in compare(baseline, current)
        ):
            findings.append(
                Finding(
                    "proxy_changed",
                    "info",
                    "hypothesis",
                    "Настройки прокси изменились",
                    "Зафиксировано различие с рабочим снимком. Оно может объяснять сетевую проблему, если приложение использует эти настройки.",
                    ("Смотрите точные старые и новые значения в списке изменений.",),
                    (
                        "Проверьте приложение прокси/VPN.",
                        "При необходимости запустите сравнение прямого запроса и запроса через прокси.",
                    ),
                )
            )


def _path_findings(current, baseline, command, findings):
    observation = current.sections["path"]
    if observation.status == "ok":
        missing = [
            x["value"] for x in observation.data.get("entries", []) if x.get("exists") is False
        ]
        if missing:
            findings.append(
                Finding(
                    "missing_path_directories",
                    "info",
                    "fact",
                    "В PATH есть отсутствующие каталоги",
                    "Проверка не нашла эти папки. Они могут быть остатками удалённых программ; это само по себе не означает поломку.",
                    tuple(missing[:15]),
                    (
                        "Если нужная команда находилась в такой папке, проверьте установку программы.",
                    ),
                )
            )
    names = [command] if command else []
    if baseline and not command:
        old, new = baseline.sections["commands"], current.sections["commands"]
        if old.status == new.status == "ok":
            names = [
                name
                for name in old.data
                if old.data[name] and name in new.data and not new.data[name]
            ]
    for name in names:
        commands = current.sections["commands"]
        if commands.status != "ok" or name not in commands.data:
            continue
        found = commands.data[name]
        old = baseline.sections["commands"].data.get(name) if baseline else None
        if found:
            findings.append(
                Finding(
                    "command_found",
                    "info",
                    "fact",
                    f"{name}: файл найден в PATH",
                    "Файл доступен в одном из проверенных каталогов. Его запуск и работоспособность зависимостей не проверялись.",
                    (found,),
                    ("Если запуск выдаёт ошибку, сохраните её текст для дальнейшей диагностики.",),
                )
            )
        else:
            evidence = ["Файл команды не найден в абсолютных каталогах проверенного PATH."]
            if old:
                evidence.append(f"В рабочем снимке был найден: {old}")
            findings.append(
                Finding(
                    "command_missing",
                    "warning",
                    "fact",
                    f"{name}: файл не найден в PATH",
                    "Это подтверждает результат поиска BEFORE. Команда всё ещё может существовать как alias, функция shell или через механизм запуска ОС.",
                    tuple(evidence),
                    (
                        "Посмотрите, не исчез ли каталог программы из PATH.",
                        "Проверьте, установлена ли программа. Не запускайте случайные команды исправления из интернета.",
                    ),
                )
            )
