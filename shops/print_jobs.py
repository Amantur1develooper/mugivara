"""Формирование текста чека и постановка задания на печать для кассы магазина."""
from decimal import Decimal
from django.utils import timezone

W = 32  # ширина чека в символах (58мм ≈ 32 символа, 80мм ≈ 42)
B  = "\x02"  # bold on
b  = "\x03"  # bold off
SEP = "=" * W
sep = "-" * W


def _center(text, width=W):
    return text.center(width)


def _row(label, value, width=W):
    space = width - len(label) - len(value)
    return label + " " * max(1, space) + value


def _qty(value):
    """3 знака после запятой, но без лишних нулей: 2.000 → 2, 1.500 → 1.5."""
    d = Decimal(value)
    s = f"{d:.3f}".rstrip("0").rstrip(".")
    return s or "0"


def _order_receipt(order):
    created = timezone.localtime(order.created_at)
    branch = order.branch
    store = branch.store

    lines = [
        SEP,
        B + _center(store.name_ru) + b,
        _center(branch.name_ru),
    ]
    if branch.address:
        lines.append(_center(branch.address))
    lines += [
        SEP,
        B + _center(f"ЧЕК #{order.id}") + b,
        _row("Дата:", created.strftime("%d.%m.%Y %H:%M")),
        _row("Оплата:", order.get_payment_method_display()),
    ]
    if order.name:
        lines.append(f"Покупатель: {order.name}")
    if order.comment:
        lines.append(f"Примечание: {order.comment}")
    lines.append(sep)

    for oi in order.items.select_related("product").all():
        lines.append(oi.product.name_ru)
        lines.append(_row(f"{int(oi.price)} x {_qty(oi.qty)}", f"{int(oi.line_total)} сом"))

    for coi in order.constructor_items.all():
        lines.append(f"🧩 {coi.constructor_name_snapshot or 'Собери сам'}"[:W])
        for sel in (coi.ingredients_snapshot or []):
            names = ", ".join(
                f"{ing.get('name','')}" + (f" x{ing['qty']}" if ing.get("qty", 1) > 1 else "")
                for ing in sel.get("ings", [])
            )
            if names:
                lines.append(f"  {sel.get('gname','')}: {names}"[:W])
        lines.append(_row(f"{int(coi.unit_price)} x {_qty(coi.qty)}", f"{int(coi.line_total)} сом"))

    if order.delivery_fee:
        lines.append(sep)
        lines.append(_row("Доставка:", f"{int(order.delivery_fee)} сом"))

    lines += [
        SEP,
        B + _row("ИТОГО:", f"{int(order.total)} сом") + b,
        SEP,
        _center("Спасибо за покупку!"),
        _center("Приходите к нам снова"),
        SEP,
        "",
    ]
    return "\n".join(lines)


def create_order_print_job(order):
    """Создаёт задание печати чека, если для филиала включена печать."""
    from .models import ShopPrintConfig, ShopPrintJob
    try:
        cfg = ShopPrintConfig.objects.get(branch=order.branch, enabled=True)
    except ShopPrintConfig.DoesNotExist:
        return None
    content = _order_receipt(order)
    return ShopPrintJob.objects.create(branch=order.branch, order=order, content=content)
