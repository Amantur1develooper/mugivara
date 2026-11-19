# -*- coding: utf-8 -*-
"""Смена статуса заказа ресторана — одно место на все кнопки.

Статус меняют из трёх мест: очередь онлайн-заказов на кассе, страница
заказов в кабинете и кнопки под сообщением в Telegram. Логика к статусу
прилагается немалая — печать на кухню, чек при закрытии, возврат остатков
при отмене, — и держать её в каждом месте отдельно значит однажды
разойтись. Поэтому все зовут эту функцию.
"""
import logging

from django.utils import timezone

log = logging.getLogger(__name__)

STATUS_LABEL = {
    "new": "🆕 Новый",
    "accepted": "✅ Принят",
    "cooking": "🍳 Готовится",
    "ready": "🏁 Готов",
    "closed": "💰 Закрыт",
    "cancelled": "❌ Отменён",
}


def printer_ready(branch):
    """Обслуживает ли филиал подключённая касса (принтер)."""
    try:
        from printing.jobs import _config_for
        return _config_for(branch) is not None
    except Exception:
        log.exception("не смог проверить печать филиала %s", branch)
        return False


def _print_kitchen(order):
    """Печать заказа на кухню. Возвращает заметку для карточки."""
    if not printer_ready(order.branch):
        return "печать не подключена"
    try:
        from printing.jobs import create_print_jobs
        create_print_jobs(order)
    except Exception:
        log.exception("не удалось напечатать заказ %s", order.id)
        return "в печать не ушло — посмотрите кассу"
    return "отправлено на печать"


def _print_receipt(order):
    if not printer_ready(order.branch):
        return "печать не подключена"
    try:
        from printing.jobs import create_receipt_job
        create_receipt_job(order)
    except Exception:
        log.exception("не удалось напечатать чек заказа %s", order.id)
        return "чек в печать не ушёл — посмотрите кассу"
    return "чек отправлен на печать"


def _restore_stock(order):
    """Возвращает остатки, если отменяют уже закрытый заказ."""
    from catalog.models import BranchItem

    for oi in order.items.select_related("item").all():
        bi = BranchItem.objects.filter(branch=order.branch, item=oi.item).first()
        if bi and bi.stock is not None:
            bi.stock += oi.qty
            bi.is_available = True
            bi.save(update_fields=["stock", "is_available"])


def apply_status(order, new_status, actor="", notify=True, payment_status=None,
                 print_docs=True):
    """Меняет статус заказа и делает всё, что к нему прилагается.

    Возвращает список заметок о том, что произошло: их показывают на кассе
    и дописывают в карточку заказа в Telegram.

    print_docs=False — когда печать берёт на себя тот, кто зовёт: при
    закрытии стола чек один на все заказы стола, и печатать его на каждый
    заказ отдельно значит выдать стопку лишних чеков.
    """
    from orders.models import Order
    from orders import tg as order_tg

    prev = order.status
    notes = []
    fields = []

    if new_status and new_status in Order.Status.values and new_status != prev:
        # Закрытый заказ отменяют редко, но тогда товар надо вернуть:
        # его уже списали при закрытии.
        if new_status == Order.Status.CANCELLED and prev == Order.Status.CLOSED:
            _restore_stock(order)
            notes.append("остатки возвращены")
        order.status = new_status
        fields.append("status")

    if payment_status and payment_status in Order.PaymentStatus.values:
        order.payment_status = payment_status
        fields.append("payment_status")
    elif new_status == Order.Status.CLOSED and "status" in fields:
        order.payment_status = Order.PaymentStatus.PAID
        fields.append("payment_status")

    if not fields:
        return []

    fields.append("updated_at")
    order.save(update_fields=fields)

    # Принимаем входящий заказ — печатаем на кухню. Заказ со стола по QR при
    # выключенном print_on_accept уже напечатан при создании, второй раз не
    # надо; доставка и самовывоз при создании не печатаются — печатаем тут.
    if print_docs and prev == Order.Status.NEW and order.status == Order.Status.ACCEPTED:
        already = bool(order.table_place_id) and not order.branch.print_on_accept
        notes.append("уже напечатано при создании" if already else _print_kitchen(order))

    if print_docs and order.status == Order.Status.CLOSED and prev != Order.Status.CLOSED:
        notes.append(_print_receipt(order))

    if notify:
        stamp = timezone.localtime().strftime("%d.%m %H:%M")
        mark = f"{STATUS_LABEL.get(order.status, order.status)} — {actor or 'кабинет'}, {stamp}"
        tail = " · ".join(n for n in notes if n)
        try:
            order_tg.refresh_order(order, footer=f"{mark}\n{tail}" if tail else mark)
        except Exception:
            log.exception("не смог обновить карточку заказа %s в Telegram", order.id)

    return notes
