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


@register.simple_tag(takes_context=True)
def url_in_lang(context, lang_code):
    """Текущий адрес в другом языке.

    Переключатель языка отправлял в set_language текущий путь вместе со старым
    префиксом (/ky/...). Django менял язык, редиректил обратно на этот путь, а
    LocaleMiddleware по префиксу снова включал прежний язык — переключение
    «залипало». Отдаём адрес, уже переписанный под нужный язык.
    """
    from django.conf import settings
    from django.urls import translate_url
    request = context.get("request")
    if not request:
        return "/"
    path = request.get_full_path()
    try:
        translated = translate_url(path, lang_code)
    except Exception:
        translated = path
    if translated != path:
        return translated
    # translate_url не справился. Так бывает, когда маршрут объявлен и внутри
    # i18n_patterns, и вне его (страницы QR-столов): reverse даёт адрес без
    # префикса, и перевод возвращает исходный путь. Подменяем префикс сами.
    codes = {code for code, _ in settings.LANGUAGES}
    head, _, tail = path[1:].partition("/")
    if head in codes:
        return f"/{lang_code}/{tail}"
    return path
