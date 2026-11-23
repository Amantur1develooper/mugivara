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

# Какому разделу принадлежит страница: подсветить пункт меню надо и в
# левом меню кабинета, и в ленте на телефоне. Выводить это блоками
# шаблона нельзя — блок можно вставить только один раз, — поэтому
# определяем по имени адреса.
_SECTIONS = {
    "home": "home",
    "checkin": "checkin", "checkin_pass": "checkin",
    "members": "members", "member_detail": "members", "member_save": "members",
    "member_new": "members", "membership_sell": "members",
    "membership_action": "members", "members_export": "members",
    "debt_settle": "members",
    "groups": "groups", "group_detail": "groups", "group_new": "groups",
    "group_save": "groups", "group_roster": "groups", "group_slot": "groups",
    "debts": "debts", "debts_settle_member": "debts",
    "classes": "classes", "class_save": "classes", "class_day": "classes",
    "class_book": "classes", "class_mark": "classes", "class_mark_all": "classes",
    "class_cancel": "classes", "class_booking_status": "classes",
    "board": "board", "booking_save": "board", "booking_status": "board",
    "leads": "leads", "lead_detail": "leads", "lead_save": "leads",
    "lead_new": "leads", "lead_to_member": "leads", "leads_export": "leads",
    "reports": "reports", "reports_export": "reports",
    "expenses": "expenses", "expense_add": "expenses",
    "setup": "setup", "staff_add": "setup", "staff_edit": "setup",
    "staff_password": "setup",
}


@register.filter
def fit_section(url_name):
    return _SECTIONS.get(url_name or "", "")

@register.filter
def weekday_py(w):
    """date:'w' считает с воскресенья (вс=0), а модель — с понедельника.
    Без перевода тренировка вставала не в тот день."""
    try:
        return (int(w) + 6) % 7
    except (TypeError, ValueError):
        return 0

# Обрезка названия по две буквы давала «Су» вместо «Сб» и «Пя» вместо
# «Пт»: по-русски сокращения не совпадают с первыми буквами.
_WD_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


@register.filter
def wd_short(weekday):
    try:
        return _WD_SHORT[int(weekday)]
    except (TypeError, ValueError, IndexError):
        return ""

# Цвета направлений: группы различают по секции, а не вчитываясь в
# название. Палитра фиксированная — так один и тот же бокс всегда
# одного цвета, а не меняет оттенок при добавлении новой секции.
_HUES = [
    ("#dc2626", "rgba(220,38,38,.10)"),    # красный
    ("#2563eb", "rgba(37,99,235,.10)"),    # синий
    ("#059669", "rgba(5,150,105,.10)"),    # зелёный
    ("#d97706", "rgba(217,119,6,.10)"),    # охра
    ("#7c3aed", "rgba(124,58,237,.10)"),   # фиолетовый
    ("#0891b2", "rgba(8,145,178,.10)"),    # бирюзовый
    ("#db2777", "rgba(219,39,119,.10)"),   # малиновый
    ("#65a30d", "rgba(101,163,13,.10)"),   # оливковый
]


@register.filter
def hue(obj, part="line"):
    """Цвет направления: hue:'line' — линия, hue:'bg' — подложка."""
    key = getattr(obj, "id", None) or 0
    line, bg = _HUES[int(key) % len(_HUES)]
    return bg if part == "bg" else line

