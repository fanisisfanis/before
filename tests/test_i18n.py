from before.i18n import language, set_language, tr


def test_english_is_complete_for_composed_diagnostic_text():
    previous = language()
    try:
        set_language("en")
        text = tr("Прокси: файл не найден в PATH\nБыло: включено\nСтало: выключено")
        assert text == "Proxy: file not found in PATH\nBefore: enabled\nNow: disabled"
    finally:
        set_language(previous)


def test_russian_remains_available_without_mutating_text():
    previous = language()
    try:
        set_language("ru")
        text = "Сохрани рабочую точку. Сравни, когда что-то пойдёт не так."
        assert tr(text) == text
    finally:
        set_language(previous)


def test_english_report_labels():
    previous = language()
    try:
        set_language("en")
        assert tr("## Результаты") == "## Results"
        assert tr("BEFORE · Диагностический отчёт") == "BEFORE · Diagnostic report"
    finally:
        set_language(previous)
