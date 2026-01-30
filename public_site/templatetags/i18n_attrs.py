from django import template
from django.utils.translation import get_language

register = template.Library()

@register.simple_tag
def t(obj, base_field: str):
    """
    Использование: {% t obj "name" %}
    Возьмёт name_ky/name_en/name_ru в зависимости от языка.
    RU — дефолт и fallback.
    """
    lang = (get_language() or "ru")[:2]
    for code in (lang, "ru"):
        field = f"{base_field}_{code}"
        if hasattr(obj, field):
            val = getattr(obj, field) or ""
            if val:
                return val

    # fallback если нет *_ru полей
    return getattr(obj, base_field, "") or ""
