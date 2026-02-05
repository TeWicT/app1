def html_to_pdf(html: str) -> bytes:
    """
    Конвертирует HTML (UTF-8) в PDF через WeasyPrint.
    Возвращает сырые байты PDF.
    """
    # Ленивая загрузка, чтобы на Windows без системных библиотек WeasyPrint
    # не падал при импорте модуля целиком.
    try:
        from weasyprint import HTML  # type: ignore
    except Exception as exc:  # ImportError, OSError и т.п.
        raise RuntimeError(
            "WeasyPrint не может быть загружен. "
            "Для генерации PDF используйте Docker-окружение, "
            "где все зависимости установлены."
        ) from exc

    return HTML(string=html).write_pdf()
