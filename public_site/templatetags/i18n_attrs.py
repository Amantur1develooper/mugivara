from decimal import Decimal, InvalidOperation

from django import template
from django.utils.translation import get_language

register = template.Library()


def currency_word():
    """Слово валюты по текущему языку: en → som, иначе → сом."""
    return "som" if (get_language() or "ru")[:2] == "en" else "сом"


@register.simple_tag(name="cur")
def cur_tag():
    """{% cur %} → «сом» / «som»."""
    return currency_word()


@register.filter(name="som")
def som(value):
    """{{ price|som }} → «1 500 сом» / «1 500 som». Число округляется до целого."""
    try:
        n = Decimal(str(value))
        n = n.quantize(Decimal("1"))
        s = f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError, InvalidOperation):
        s = str(value)
    return f"{s} {currency_word()}"

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
