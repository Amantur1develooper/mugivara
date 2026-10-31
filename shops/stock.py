# -*- coding: utf-8 -*-
"""Списание товаров со склада филиала по заказу.

Заказ на доставку не трогает остатки, пока его не подтвердили: до звонка
менеджера он может отмениться, а товар всё это время числился бы проданным
и пропадал из витрины. Поэтому в момент оформления мы только запоминаем,
что надо будет списать (order.stock_plan), а применяем это при подтверждении.

Продажа в магазине — другое дело: товар уже отдали покупателю, списываем сразу.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from .models import StoreOrder, StoreStock


def build_plan(product_qty: dict) -> dict:
    """{product_id: Decimal} → {«id»: «количество»} для хранения в JSON."""
    return {str(pid): str(Decimal(str(qty))) for pid, qty in product_qty.items() if qty}


def _apply(order, sign: int):
    """sign=-1 — списать, sign=+1 — вернуть. Возвращает список нехваток."""
    plan = order.stock_plan or {}
    if not plan:
        return []

    shortages = []
    with transaction.atomic():
        stocks = {
            s.product_id: s
            for s in StoreStock.objects
            .select_for_update()
            .filter(branch_id=order.branch_id, product_id__in=[int(k) for k in plan])
        }
        for pid_str, qty_str in plan.items():
            pid, qty = int(pid_str), Decimal(qty_str)
            st = stocks.get(pid)
            if st is None:
                # товар мог быть снят с филиала уже после оформления
                shortages.append((pid, qty, None))
                continue
            if sign < 0 and st.qty < qty:
                # не блокируем подтверждение: заказ уже принят, человек ждёт.
                # Списываем сколько есть и сообщаем менеджеру о нехватке.
                shortages.append((pid, qty, st.qty))
            StoreStock.objects.filter(pk=st.pk).update(qty=F("qty") + sign * qty)
    return shortages


def write_off(order) -> list:
    """Списывает заказ со склада. Повторный вызов ничего не делает."""
    if order.stock_written_off:
        return []
    shortages = _apply(order, -1)
    StoreOrder.objects.filter(pk=order.pk).update(stock_written_off=True)
    order.stock_written_off = True
    return shortages


def restore(order) -> None:
    """Возвращает товар на склад — при отмене уже списанного заказа."""
    if not order.stock_written_off:
        return
    _apply(order, +1)
    StoreOrder.objects.filter(pk=order.pk).update(stock_written_off=False)
    order.stock_written_off = False


def shortage_text(order, shortages) -> str:
    """Человеческое перечисление того, чего не хватило на складе."""
    if not shortages:
        return ""
    from .models import StoreProduct
    names = dict(
        StoreProduct.objects.filter(id__in=[s[0] for s in shortages])
        .values_list("id", "name_ru")
    )
    parts = []
    for pid, need, have in shortages:
        name = names.get(pid, f"товар #{pid}")
        parts.append(f"{name} (нужно {need:g}, было {have if have is not None else 0:g})")
    return "Остатка не хватило: " + "; ".join(parts) + ". Остаток ушёл в минус."
