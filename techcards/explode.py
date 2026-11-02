# -*- coding: utf-8 -*-
"""Разворачивание техкарты в список ингредиентов для списания со склада.

Строка техкарты — это либо ингредиент со склада, либо полуфабрикат
(другая техкарта). Полуфабрикат нужен, чтобы не переписывать состав заново:
составили карту «Фри» (картофель + кетчуп) — и в карте «Комбо №1» достаточно
выбрать «п/ф: Фри», вместо того чтобы снова перечислять картофель и кетчуп.

Склад при этом должен уменьшиться на реальные продукты, а не на «одну штуку
фри», поэтому перед списанием карту надо развернуть до самого низа.

Единицы: net_qty у строки-ингредиента — это количество на весь выход карты
(yield_qty порций). У строки-полуфабриката net_qty — это сколько ПОРЦИЙ
полуфабриката нужно, тоже на весь выход. Отсюда масштаб для вложенной карты
считается ровно так же, как для верхней: порции ÷ выход.
"""
from decimal import Decimal

MAX_DEPTH = 10   # «комбо из комбо из комбо» дальше этого — почти наверняка ошибка


def expand(tech_card, portions, _seen=None, _depth=0):
    """Сколько ингредиентов уйдёт со склада на `portions` порций блюда.

    Возвращает {ingredient_id: Decimal}. Полуфабрикаты раскрываются рекурсивно.
    """
    out = {}
    if portions <= 0 or tech_card is None:
        return out

    # защита от зацикливания: «А содержит Б, Б содержит А» повесило бы сервер
    seen = set(_seen or ())
    if tech_card.id in seen or _depth > MAX_DEPTH:
        return out
    seen.add(tech_card.id)

    yield_qty = tech_card.yield_qty or Decimal("1")
    if yield_qty <= 0:
        yield_qty = Decimal("1")
    scale = Decimal(str(portions)) / yield_qty

    lines = tech_card.ingredients.select_related("ingredient", "semi_finished").all()
    for line in lines:
        qty = (line.net_qty * scale)

        if line.ingredient_id:
            key = line.ingredient_id
            out[key] = out.get(key, Decimal("0")) + qty.quantize(Decimal("0.001"))
            continue

        if line.semi_finished_id:
            # net_qty здесь — количество порций полуфабриката
            nested = expand(line.semi_finished, qty, seen, _depth + 1)
            for ing_id, need in nested.items():
                out[ing_id] = out.get(ing_id, Decimal("0")) + need

    return out


def find_cycles(branch):
    """Техкарты филиала, которые ссылаются сами на себя через полуфабрикаты.

    Нужна для подсказки в кабинете: такую карту списать корректно нельзя.
    """
    from .models import TechCard

    cards = {
        c.id: c for c in TechCard.objects.filter(branch=branch, is_active=True)
        .prefetch_related("ingredients")
    }
    bad = []
    for cid, card in cards.items():
        stack, seen = [cid], set()
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            node = cards.get(cur)
            if node is None:
                continue
            for line in node.ingredients.all():
                sid = line.semi_finished_id
                if not sid:
                    continue
                if sid == cid:
                    bad.append(card)
                    stack = []
                    break
                stack.append(sid)
    return bad
