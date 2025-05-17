import pdfkit
from django.conf import settings

def html_to_pdf(html: str) -> bytes:
    """
    Конвертирует HTML (UTF-8) в PDF через wkhtmltopdf.
    Возвращает сырые байты PDF.
    """
    config = pdfkit.configuration(wkhtmltopdf=settings.WKHTMLTOPDF_CMD)
    options = {
        'encoding': "UTF-8",
        'enable-local-file-access': None,  # чтобы видеть локальные статики
        # доп. опции: 'margin-top': '10mm', ...
    }
    return pdfkit.from_string(html, False, configuration=config, options=options)
