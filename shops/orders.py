# -*- coding: utf-8 -*-
"""Смена статуса заказа магазина — одно место на все кнопки.

Статус меняют из трёх мест: список заказов в кабинете, очередь онлайн-заказов
на кассе и кнопки под сообщением в Telegram. Раньше у каждого была своя
логика, и они расходились: из кассы заказ подтверждался, но товар со склада
не списывался и чек не печатался. Теперь все зовут эту функцию.
"""
import logging

from django.utils import timezone

from . import stock as shop_stock

log = logging.getLogger(__name__)

STATUS_LABEL = {
    "new":       "🆕 Новый",
    "confirmed": "✅ Подтверждён",
    "done":      "🏁 Выполнен",
    "canceled":  "❌ Отменён",
}


def print_receipt(order):
    """Чек на кассу филиала, если она подключена. Возвращает строку для отчёта."""
    from .models import ShopPrintConfig
    from .print_jobs import create_order_print_job

    cfg = ShopPrintConfig.objects.filter(branch=order.branch, enabled=True).first()
    if not cfg:
        return "печать не подключена"
    try:
        if create_order_print_job(order) is None:
            return "печать не подключена"
    except Exception:
        log.exception("не удалось поставить чек заказа %s в печать", order.id)
        return "чек в печать не ушёл — посмотрите кассу"
    return "чек отправлен на печать" if cfg.is_agent_online() else "чек в очереди (касса офлайн)"


def apply_status(order, new_status, actor="", notify=True):
    """Меняет статус заказа и делает всё, что к нему прилагается.

    Возвращает список заметок о том, что произошло: их показывают менеджеру
    и дописывают в карточку заказа в Telegram.
    """
    from . import tg as shop_tg

    if new_status == order.status:
        return []

    order.status = new_status
    order.save(update_fields=["status"])

    notes = []
    if new_status in ("confirmed", "done"):
        # Склад двигается при подтверждении, а не при оформлении: до звонка
        # менеджера заказ может отмениться, и держать товар списанным нельзя.
        already = order.stock_written_off
        shortages = shop_stock.write_off(order)
        if not already:
            notes.append("списано со склада")
        if shortages:
            notes.append(shop_stock.shortage_text(order, shortages))
        notes.append(print_receipt(order))
    elif new_status == "canceled" and order.stock_written_off:
        shop_stock.restore(order)
        notes.append("товар возвращён на склад")

    if notify:
        stamp = timezone.localtime().strftime("%d.%m %H:%M")
        mark = f"{STATUS_LABEL.get(new_status, new_status)} — {actor or 'кабинет'}, {stamp}"
        tail = " · ".join(n for n in notes if n)
        shop_tg.refresh_order(order, footer=f"{mark}\n{tail}" if tail else mark)

    return notes
