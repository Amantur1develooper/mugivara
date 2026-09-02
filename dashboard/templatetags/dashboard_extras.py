from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Look up a dict value by key in a template: {{ mydict|get_item:key }}"""
    return dictionary.get(key)


@register.filter
def money(value):
    """Целое число с разделением разрядов пробелом: 1234567 → '1 234 567'."""
    try:
        n = round(float(value))
    except (TypeError, ValueError):
        return value
    return f"{n:,}".replace(",", " ")
