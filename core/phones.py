# -*- coding: utf-8 -*-
"""Приведение телефона к международному виду.

Ссылка WhatsApp — это wa.me/<цифры в международном формате>. Если владелец
вписал номер по-местному, «0700 12-34-56», ссылка ведёт в никуда: WhatsApp
не знает, из какой страны этот ноль. Поэтому номер нормализуем при
сохранении и ещё раз — когда строим ссылку, чтобы вылечить и то, что уже
лежит в базе.
"""
import re

DEFAULT_COUNTRY = "996"          # Кыргызстан
NATIONAL_LEN = 9                 # 700123456 — девять цифр после кода страны
MIN_DIGITS, MAX_DIGITS = 10, 15  # границы E.164


def digits_only(raw):
    return re.sub(r"\D", "", raw or "")


def normalize(raw, country=DEFAULT_COUNTRY):
    """«0700 12-34-56» → «+996700123456».

    Возвращает (номер, ошибка). Пустая строка — не ошибка: номер
    необязательный, просто его нет.
    """
    raw = (raw or "").strip()
    if not raw:
        return "", None

    plus = raw.lstrip().startswith("+")
    num = digits_only(raw)
    if not num:
        return "", "Телефон должен состоять из цифр"

    if not plus:
        if num.startswith("00"):             # 00996… — международный набор
            num = num[2:]
        elif num.startswith("0") and len(num) == NATIONAL_LEN + 1:
            num = country + num[1:]          # 0700123456 — местный набор
        elif len(num) == NATIONAL_LEN:
            num = country + num              # 700123456 — без кода страны
    if len(num) < MIN_DIGITS:
        return "", ("Похоже на неполный номер. Введите с кодом страны, "
                    f"например +{country}700123456")
    if len(num) > MAX_DIGITS:
        return "", "Слишком длинный номер — проверьте, не задвоился ли код страны"
    return "+" + num, None


def wa_digits(raw, country=DEFAULT_COUNTRY):
    """Цифры для ссылки wa.me — с кодом страны, даже если в базе местный номер."""
    normalized, err = normalize(raw, country)
    return "" if err else normalized.lstrip("+")
