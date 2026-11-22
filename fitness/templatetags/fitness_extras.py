# -*- coding: utf-8 -*-
"""Мелкие фильтры для страниц клуба."""
from django import template

register = template.Library()


@register.filter
def get(value, key):
    """Достаёт из словаря по ключу: шахматка хранит записи как
    {тренер: {час: [записи]}}, а шаблоны так индексировать не умеют."""
    if not value:
        return None
    try:
        return value.get(key)
    except AttributeError:
        return None


@register.filter
def money(value):
    """1500 → «1 500»: в отчётах длинные суммы иначе не читаются."""
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return value
