# -*- coding: utf-8 -*-
"""Кнопки клуба в Telegram: заявки и записи к тренеру."""
import logging

from integrations import tgbot

from . import tg
from .models import Lead, TrainerBooking

log = logging.getLogger(__name__)


def handle_callback(cq):
    """Нажали кнопку под заявкой или записью. Формат: ft:lead:take:12."""
    parts = (cq.get("data") or "").split(":")
    if len(parts) != 4:
        return
    _, what, action, raw_id = parts

    if what == "lead":
        obj = Lead.objects.filter(id=raw_id).select_related("club", "section", "trainer").first()
        chats = set((obj.tg_messages or {})) | {tg.leads_chat(obj.club)[0]} if obj else set()
        apply = tg.apply_lead_action
    elif what == "book":
        obj = (TrainerBooking.objects.filter(id=raw_id)
               .select_related("club", "trainer", "member").first())
        chats = set((obj.tg_messages or {})) | {tg.leads_chat(obj.club)[0]} if obj else set()
        apply = tg.apply_booking_action
    else:
        return

    if not obj:
        tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
                   text="Не нашёл — возможно, удалили", show_alert=True)
        return

    # Кнопку могли переслать в другой чат — меняем только из своих
    chat_id = str((cq.get("message") or {}).get("chat", {}).get("id", ""))
    if chat_id and chat_id not in {str(c) for c in chats if c}:
        tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
                   text="Это не из вашего чата", show_alert=True)
        return

    toast = apply(obj, action, actor=tgbot.actor_name(cq.get("from")))
    tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
               text=toast or "Не понял кнопку")
