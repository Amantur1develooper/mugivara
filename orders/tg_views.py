# -*- coding: utf-8 -*-
"""Кнопки под заказом ресторана в Telegram."""
import logging

from integrations import tgbot

from . import tg
from .models import Order

log = logging.getLogger(__name__)


def _order(ident):
    return (Order.objects
            .filter(id=ident)
            .select_related("branch", "branch__restaurant", "table_place")
            .prefetch_related("items__item", "constructor_items")
            .first())


def handle_callback(cq):
    """Нажали кнопку под заказом кафе."""
    parts = (cq.get("data") or "").split(":")
    if len(parts) != 3:
        return
    _, action, raw_id = parts

    order = _order(raw_id)
    if not order:
        tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
                   text="Заказ не найден", show_alert=True)
        return

    # Кнопку могли переслать в другой чат — статус меняем только из чатов,
    # которым этот заказ и отправляли.
    chat_id = str((cq.get("message") or {}).get("chat", {}).get("id", ""))
    allowed = set(tg.recipients(order.branch)) | set(order.tg_messages or {})
    if chat_id and chat_id not in allowed:
        tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
                   text="Этот заказ не из вашего чата", show_alert=True)
        return

    toast = tg.apply_action(order, action, actor=tgbot.actor_name(cq.get("from")))
    tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
               text=toast or "Не понял кнопку")
