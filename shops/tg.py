# -*- coding: utf-8 -*-
"""Карточка заказа магазина в Telegram: подтверждение прямо в группе.

Заказ приходил в группу текстом, и чтобы его подтвердить, менеджер шёл в
кабинет. Теперь под сообщением кнопки: подтвердить, выполнен, отменить.
Подтверждение делает ровно то же, что и кнопка в кабинете, — списывает товар
со склада и, если к филиалу подключена касса, отправляет чек на печать.

Заказ уходит сразу в несколько чатов (группа, личка менеджера), поэтому
номера сообщений храним по чатам и переписываем каждую копию.
"""
import logging
from decimal import Decimal

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from integrations import tgbot

from . import stock as shop_stock

log = logging.getLogger(__name__)

bot_token = tgbot.bot_token
verify_init_data = tgbot.verify_init_data
actor_name = tgbot.actor_name

SALT = "shops.order"

STATUS_LABEL = {
    "new":       "🆕 Новый",
    "confirmed": "✅ Подтверждён",
    "done":      "🏁 Выполнен",
    "canceled":  "❌ Отменён",
}

ACTIONS = {
    "confirm": ("confirmed", "Заказ подтверждён"),
    "done":    ("done",      "Заказ отмечен выполненным"),
    "cancel":  ("canceled",  "Заказ отменён"),
    "reopen":  ("new",       "Заказ снова в новых"),
}


def _call(method, **payload):
    return tgbot.call(method, **payload)


def sign_order(order):
    return tgbot.sign(order.id, SALT)


def unsign_order(token):
    return tgbot.unsign(token, SALT)


def card_url(order):
    base = getattr(settings, "SITE_URL", "").rstrip("/")
    return base + reverse("shops_tg:card", args=[sign_order(order)])


# ── текст ────────────────────────────────────────────────────────────────────

def _money(value):
    return f"{int(Decimal(str(value or 0)))} сом"


def _qty(value):
    d = Decimal(str(value or 0))
    return str(int(d)) if d == d.to_integral_value() else f"{d.normalize()}"


def items_of(order):
    """Состав заказа: [(название, количество, сумма, [строки состава])]."""
    rows = []
    for it in order.items.select_related("product").all():
        name = getattr(it.product, "name_ru", None) or str(it.product)
        rows.append((name, _qty(it.qty), it.line_total, []))
    for coi in order.constructor_items.all():
        extra = []
        for sel in (coi.ingredients_snapshot or []):
            names = ", ".join(i.get("name", "") for i in sel.get("ings", []) if i.get("name"))
            if sel.get("gname") and names:
                extra.append(f"{sel['gname']}: {names}")
        rows.append((f"🧩 {coi.constructor_name_snapshot or 'Собери сам'}",
                     _qty(coi.qty), coi.line_total, extra))
    return rows


def message_text(order, footer=""):
    branch = order.branch
    is_delivery = order.mode == "delivery"
    head = "🚚 Доставка" if is_delivery else "🏪 В магазине"

    lines = [
        f"🧾 <b>Заказ №{order.id}</b> · {STATUS_LABEL.get(order.status, order.status)}",
        f"{head} · {getattr(branch, 'name_ru', str(branch))}",
        "",
    ]
    if order.name:
        lines.append(f"👤 {order.name}")
    if order.phone and order.phone != "-":
        lines.append(f"📞 {order.phone}")
    if order.address:
        lines.append(f"{'📍' if is_delivery else '📝'} {order.address}")
    if order.comment:
        lines.append(f"💬 {order.comment}")

    rows = items_of(order)
    if rows:
        lines += ["", "📋 Состав:"]
        for name, qty, total, extra in rows:
            lines.append(f"  • {name} × {qty} — {_money(total)}")
            lines += [f"      {e}" for e in extra]

    lines.append("")
    if order.delivery_fee and Decimal(str(order.delivery_fee)) > 0:
        lines.append(f"🛒 Товары: {_money(order.subtotal)}")
        lines.append(f"🚚 Доставка: {_money(order.delivery_fee)}")
    lines.append(f"💰 Итого: {_money(order.total)} · {order.get_payment_method_display()}")
    lines.append(f"⏰ {timezone.localtime(order.created_at).strftime('%d.%m.%Y %H:%M')}")
    if footer:
        lines += ["", f"<i>{footer}</i>"]
    return "\n".join(lines)


# ── кнопки ───────────────────────────────────────────────────────────────────

def _open_button(order, chat_id):
    return tgbot.open_button(card_url(order), "📋 Карточка заказа",
                             tgbot.is_group(chat_id))


def keyboard(order, chat_id=None):
    rows = []
    # Продажу в магазине подтверждать не надо: товар уже отдали покупателю,
    # склад списан, чек пробит. Такой заказ приходит просто как уведомление.
    if order.mode != "in_store":
        if order.status == "new":
            rows.append([{"text": "✅ Подтвердить", "callback_data": f"sh:confirm:{order.id}"},
                         {"text": "❌ Отменить",    "callback_data": f"sh:cancel:{order.id}"}])
        elif order.status == "confirmed":
            rows.append([{"text": "🏁 Выполнен", "callback_data": f"sh:done:{order.id}"},
                         {"text": "❌ Отменить", "callback_data": f"sh:cancel:{order.id}"}])
        else:
            rows.append([{"text": "↩️ Вернуть в новые", "callback_data": f"sh:reopen:{order.id}"}])
    rows.append([_open_button(order, chat_id)])
    return {"inline_keyboard": rows}


# ── кому слать ───────────────────────────────────────────────────────────────

def recipients(branch):
    """Чаты филиала: {chat_id: thread_id}. Группа, личка менеджера и список
    получателей из раздела интеграций — объединяются, чтобы не задвоить."""
    from integrations.models import ShopTelegramRecipient

    chats = {}
    for r in ShopTelegramRecipient.objects.filter(branch=branch, is_active=True,
                                                  notify_new_orders=True):
        thread = getattr(r, "thread_id", None) or getattr(r, "message_thread_id", None)
        chats[str(r.chat_id)] = thread
    if getattr(branch, "tg_group_chat_id", None):
        chats.setdefault(str(branch.tg_group_chat_id), getattr(branch, "tg_thread_id", None))
    if getattr(branch, "tg_manager_chat_id", None):
        chats.setdefault(str(branch.tg_manager_chat_id), None)
    return chats


def send_order(order, only_missing=False):
    """Шлёт карточку заказа в чаты филиала. Возвращает (ушло, ошибок).

    only_missing — для повторной попытки: чаты, куда карточка уже ушла,
    пропускаем, иначе повтор задвоил бы заказ в группе.
    """
    chats = recipients(order.branch)
    if not chats:
        return 0, 0

    text = message_text(order)
    sent, errors, ids = 0, 0, dict(order.tg_messages or {})
    for chat_id, thread_id in chats.items():
        if only_missing and str(chat_id) in ids:
            continue
        message_id = tgbot.send_card(chat_id, thread_id, text, keyboard(order, chat_id))
        if message_id:
            ids[str(chat_id)] = message_id
            sent += 1
        else:
            errors += 1
    if ids != (order.tg_messages or {}):
        order.tg_messages = ids
        order.save(update_fields=["tg_messages"])
    return sent, errors


def refresh_order(order, footer=""):
    """Переписывает карточку заказа во всех чатах, куда она ушла."""
    text = message_text(order, footer)
    for chat_id, message_id in (order.tg_messages or {}).items():
        tgbot.edit_card(chat_id, message_id, text, keyboard(order, chat_id))


# ── действия ─────────────────────────────────────────────────────────────────

def apply_action(order, action, actor=""):
    """Меняет статус заказа по нажатой кнопке. Возвращает текст для всплывашки."""
    if action not in ACTIONS:
        return None
    new_status, toast = ACTIONS[action]
    if order.status == new_status:
        return f"Уже отмечено: {STATUS_LABEL[new_status]}"

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
        notes.append(_print_receipt(order))
    elif new_status == "canceled" and order.stock_written_off:
        shop_stock.restore(order)
        notes.append("товар возвращён на склад")

    stamp = timezone.localtime().strftime("%d.%m %H:%M")
    tail = " · ".join(n for n in notes if n)
    mark = f"{STATUS_LABEL[new_status]} — {actor or 'Telegram'}, {stamp}"
    if tail:
        mark += f"\n{tail}"
    refresh_order(order, footer=mark)
    return toast


def _print_receipt(order):
    """Чек на кассу филиала, если она подключена."""
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
