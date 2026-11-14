# -*- coding: utf-8 -*-
"""Кнопки брони картинга из Telegram и страница мини-приложения."""
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from integrations import tgbot

from . import tg
from .models import SimRacingAppointment

log = logging.getLogger(__name__)

# кнопки мини-приложения по статусам: [действие, подпись, главная, во всю ширину]
CARD_BUTTONS = {
    "new":       [["confirm", "✅ Подтвердить", True], ["cancel", "❌ Отменить", False]],
    "confirmed": [["cancel", "❌ Отменить", False, True]],
    "canceled":  [["reopen", "↩️ Вернуть в новые", False, True]],
}


def handle_callback(cq):
    """Нажали кнопку под бронью картинга."""
    _, action, raw_id = (cq.get("data") or "").split(":")

    appt = (SimRacingAppointment.objects
            .filter(id=raw_id).select_related("venue", "session_type").first())
    if not appt:
        tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
                   text="Бронь не найдена", show_alert=True)
        return

    # кнопку могли переслать в другой чат — меняем статус только из чата площадки
    chat_id = str((cq.get("message") or {}).get("chat", {}).get("id", ""))
    if chat_id and str(appt.venue.tg_chat_id) != chat_id:
        tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
                   text="Эта бронь не из вашего чата", show_alert=True)
        return

    toast = tg.apply_action(appt, action, actor=tgbot.actor_name(cq.get("from")))
    tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
               text=toast or "Не понял кнопку")


# ── мини-приложение ──────────────────────────────────────────────────────────

def _appointment(token):
    appt_id = tg.unsign_appointment(token)
    if not appt_id:
        return None
    return (SimRacingAppointment.objects
            .filter(id=appt_id).select_related("venue", "session_type").first())


def card(request, token):
    appt = _appointment(token)
    if not appt:
        return render(request, "tg/card.html", {"expired": True}, status=404)

    rows = [("Когда", tg._when(appt)),
            ("Что", tg.ride_line(appt)),
            ("Клиент", appt.customer_name or "Гость")]
    if appt.customer_phone:
        rows.append(("Телефон", appt.customer_phone))
    if appt.discount_percent:
        rows.append(("Скидка", f"−{appt.discount_percent}%"))

    return render(request, "tg/card.html", {
        "title": f"Бронь №{appt.id}",
        "venue_name": appt.venue.name,
        "status": appt.status,
        "status_label": tg.STATUS_LABEL.get(appt.status, appt.status),
        "rows": rows,
        "items": [],
        "total": appt.total_price,
        "total_note": f"{appt.duration_minutes} мин",
        "phone": appt.customer_phone,
        "action_url": reverse("simracing_tg:card_action", args=[token]),
        "buttons_json": json.dumps(CARD_BUTTONS, ensure_ascii=False),
    })


@csrf_exempt
@require_POST
def card_action(request, token):
    appt = _appointment(token)
    if not appt:
        return JsonResponse({"ok": False, "error": "Ссылка устарела"}, status=404)

    user = tgbot.verify_init_data(request.POST.get("init_data", ""))
    if user is None:
        if not settings.DEBUG:
            return JsonResponse(
                {"ok": False, "error": "Откройте карточку кнопкой в Telegram"}, status=403)
        user = {}

    toast = tg.apply_action(appt, request.POST.get("action", ""),
                            actor=tgbot.actor_name(user))
    if toast is None:
        return JsonResponse({"ok": False, "error": "Неизвестное действие"}, status=400)
    return JsonResponse({"ok": True, "toast": toast, "status": appt.status,
                         "status_label": tg.STATUS_LABEL.get(appt.status, appt.status)})
