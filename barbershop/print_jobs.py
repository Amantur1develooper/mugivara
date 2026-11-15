# -*- coding: utf-8 -*-
"""Чек барбершопа: текст и постановка задания на печать.

Печатает тот же агент, что обслуживает кассы магазинов, — он забирает
задания по токену заведения.
"""
from django.utils import timezone

W = 32          # ширина чека в символах (58 мм ≈ 32, 80 мм ≈ 42)
B = "\x02"      # жирный вкл
b = "\x03"      # жирный выкл
SEP = "=" * W
sep = "-" * W


def _center(text, width=W):
    return text.center(width)


def _row(label, value, width=W):
    space = width - len(label) - len(value)
    return label + " " * max(1, space) + value


def _receipt(appt):
    shop = appt.barbershop
    created = timezone.localtime(appt.created_at)

    lines = [SEP, B + _center(shop.name) + b]
    if shop.address:
        lines.append(_center(shop.address[:W]))
    if shop.phone:
        lines.append(_center(shop.phone))
    lines += [
        SEP,
        B + _center(f"ЧЕК #{appt.id}") + b,
        _row("Дата:", created.strftime("%d.%m.%Y %H:%M")),
    ]
    if appt.barber_name:
        lines.append(_row("Мастер:", appt.barber_name[:W - 8]))
    if appt.payment_method:
        lines.append(_row("Оплата:", appt.get_payment_method_display()))
    if appt.customer_name and appt.customer_name != "Клиент":
        lines.append(f"Клиент: {appt.customer_name}"[:W])
    lines.append(sep)

    for row in (appt.services_snapshot or []):
        name = str(row.get("name", ""))[:W]
        price = int(row.get("price") or 0)
        lines.append(name)
        lines.append(_row("", f"{price} сом"))
    if not appt.services_snapshot:
        lines.append(str(appt.service_name or "Услуга")[:W])

    lines += [
        SEP,
        B + _row("ИТОГО:", f"{int(appt.price_snapshot)} сом") + b,
        SEP,
        _center("Спасибо, что выбрали нас!"),
        _center("Ждём вас снова"),
        SEP,
        "",
    ]
    return "\n".join(lines)


def create_appt_print_job(appt):
    """Ставит чек в печать, если у барбершопа включён принтер."""
    from .models import BarbershopPrintConfig, BarbershopPrintJob
    cfg = BarbershopPrintConfig.objects.filter(barbershop=appt.barbershop,
                                               enabled=True).first()
    if not cfg:
        return None
    return BarbershopPrintJob.objects.create(
        barbershop=appt.barbershop, appointment=appt, content=_receipt(appt))
