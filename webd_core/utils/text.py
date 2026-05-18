import re


def normalize_text_field(value) -> str:
    """
    Убирает переводы строк и legacy-последовательности \\r, \\n из текстовых полей.
    """
    if value is None:
        return ''
    s = str(value)
    for src in ('\\r\\n', '\\r', '\\n', '\\t', '\r\n', '\r', '\n', '\t'):
        s = s.replace(src, ' ')
    return re.sub(r'\s+', ' ', s).strip()
