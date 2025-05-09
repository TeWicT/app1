from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Возвращает dictionary[key] или None, если ключ отсутствует."""
    try:
        return dictionary.get(key)
    except Exception:
        return None
