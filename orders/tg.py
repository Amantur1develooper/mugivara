# -*- coding: utf-8 -*-
"""Карточка заказа ресторана в Telegram: текст, кнопки, обновление.

Заказ приходил в группу простым сообщением — чтобы его принять, надо было
открыть кабинет. Теперь под сообщением кнопки: принять, отметить готовым,
закрыть, отменить. Статус меняется там же, где его увидели.

Текст карточки берём из integrations.tasks — тот же, что приходил раньше,
чтобы сообщение не поменялось у тех, кто к нему привык.
"""
import logging

from integrations import tgbot

log = logging.getLogger(__name__)

PREFIX = "rs"

# действие → (новый статус, что показать нажавшему)
ACTIONS = {
    "accept": ("accepted", "Заказ принят"),
    "cooking": ("cooking", "Отмечено: готовится"),
    "ready": ("ready", "Отмечено: готов"),
    "close": ("closed", "Заказ закрыт"),
    "cancel": ("cancelled", "Заказ отменён"),
    "reopen": ("new", "Вернули в новые"),
}

# статус → ряды кнопок: [(действие, подпись)]
BUTTONS = {
    "new": [[("accept", "✅ Принять"), ("cancel", "❌ Отменить")]],
    "accepted": [[("cooking", "🍳 Готовится"), ("ready", "🏁 Готов")],
                 [("cancel", "❌ Отменить")]],
    "cooking": [[("ready", "🏁 Готов"), ("cancel", "❌ Отменить")]],
    "ready": [[("close", "💰 Закрыть"), ("cancel", "❌ Отменить")]],
    "closed": [[("reopen", "↩️ Вернуть в новые")]],
    "cancelled": [[("reopen", "↩️ Вернуть в новые")]],
}


def message_text(order, footer=""):
    """Тот же текст, что приходил раньше: со столика — короткий, остальные —
    полный. Менять привычное сообщение вместе с кнопками не стоит."""
    from integrations.tasks import _order_text, _table_order_text

    if getattr(order, "table_place_id", None):
        text = _table_order_text(order)
    else:
        text = _order_text(order)
    return f"{text}\n\n{footer}" if footer else text


def keyboard(order, chat_id=None):
    rows = []
    for row in BUTTONS.get(order.status, []):
        rows.append([{"text": label,
                      "callback_data": f"{PREFIX}:{action}:{order.id}"}
                     for action, label in row])
    return {"inline_keyboard": rows} if rows else None


# ── кому слать ───────────────────────────────────────────────────────────────

def recipients(branch):
    """Чаты филиала: {chat_id: thread_id}."""
    from integrations.models import TelegramRecipient

    chats = {}
    for r in TelegramRecipient.objects.filter(branch=branch, is_active=True,
                                              notify_new_orders=True):
        chats[str(r.chat_id)] = r.message_thread_id or None
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
    sent = errors = 0
    ids = dict(order.tg_messages or {})
    for chat_id, thread_id in chats.items():
        if only_missing and str(chat_id) in ids:
            continue
        message_id = tgbot.send_card(chat_id, thread_id, text,
                                     keyboard(order, chat_id))
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
    """Меняет статус заказа по нажатой кнопке. Возвращает текст всплывашки."""
    from .flow import STATUS_LABEL, apply_status

    if action not in ACTIONS:
        return None
    new_status, toast = ACTIONS[action]
    if order.status == new_status:
        return f"Уже отмечено: {STATUS_LABEL.get(new_status, new_status)}"

    notes = apply_status(order, new_status, actor=actor or "Telegram")
    # Про печать нажавшему говорим сразу: иначе непонятно, выехал чек или нет.
    printed = [n for n in notes if "печат" in n or "чек" in n]
    return f"{toast} · {printed[0]}" if printed else toast
