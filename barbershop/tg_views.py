# -*- coding: utf-8 -*-
"""Обработчик кнопок из Telegram и страница мини-приложения с записью."""
import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import tg
from .models import Appointment

log = logging.getLogger(__name__)


def _secret_ok(request, secret):
    want = (getattr(settings, "TG_WEBHOOK_SECRET", "") or "").strip()
    if not want or secret != want:
        return False
    # Telegram присылает тот же секрет заголовком — вторая проверка на случай,
    # если адрес вебхука где-то засветился (логи прокси, история браузера).
    sent = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    return sent is None or sent == want


@csrf_exempt
def webhook(request, secret):
    """Приём обновлений от Telegram: нас интересуют нажатия кнопок."""
    if not _secret_ok(request, secret):
        return HttpResponseForbidden("нет доступа")
    if request.method != "POST":
        return HttpResponse("ok")

    try:
        update = json.loads(request.body.decode("utf-8") or "{}")
    except ValueError:
        return HttpResponse("ok")

    cq = update.get("callback_query")
    if cq:
        _handle_callback(cq)
    # Telegram повторяет доставку, пока не получит 200, поэтому отвечаем всегда.
    return HttpResponse("ok")


def _handle_callback(cq):
    data = (cq.get("data") or "").split(":")
    if len(data) != 3 or data[0] != "bs":
        return
    _, action, raw_id = data

    appt = Appointment.objects.filter(id=raw_id).select_related("barbershop").first()
    if not appt:
        tg._call("answerCallbackQuery", callback_query_id=cq["id"],
                 text="Запись не найдена", show_alert=True)
        return

    # кнопку могли переслать в другой чат — меняем статус только из чата салона
    chat_id = str((cq.get("message") or {}).get("chat", {}).get("id", ""))
    if chat_id and str(appt.barbershop.tg_chat_id) != chat_id:
        tg._call("answerCallbackQuery", callback_query_id=cq["id"],
                 text="Эта запись не из вашего чата", show_alert=True)
        return

    toast = tg.apply_action(appt, action, actor=tg.actor_name(cq.get("from")))
    tg._call("answerCallbackQuery", callback_query_id=cq["id"],
             text=toast or "Не понял кнопку")


# ── мини-приложение ──────────────────────────────────────────────────────────

def _appointment(token):
    appt_id = tg.unsign_appointment(token)
    if not appt_id:
        return None
    return Appointment.objects.filter(id=appt_id).select_related("barbershop", "barber").first()


def card(request, token):
    """Карточка записи внутри Telegram — без входа в кабинет."""
    appt = _appointment(token)
    if not appt:
        return render(request, "barbershop/tg_card.html",
                      {"expired": True}, status=404)
    return render(request, "barbershop/tg_card.html", {
        "appt": appt,
        "token": token,
        "when": tg._when(appt),
        "status_label": tg.STATUS_LABEL.get(appt.status, appt.status),
        "services": tg.services_of(appt),
    })


@csrf_exempt
@require_POST
def card_action(request, token):
    """Кнопка внутри мини-приложения: меняет статус и правит карточку в чате."""
    appt = _appointment(token)
    if not appt:
        return JsonResponse({"ok": False, "error": "Ссылка устарела"}, status=404)

    user = tg.verify_init_data(request.POST.get("init_data", ""))
    if user is None:
        if not settings.DEBUG:
            return JsonResponse(
                {"ok": False, "error": "Откройте карточку кнопкой в Telegram"}, status=403)
        user = {}

    toast = tg.apply_action(appt, request.POST.get("action", ""), actor=tg.actor_name(user))
    if toast is None:
        return JsonResponse({"ok": False, "error": "Неизвестное действие"}, status=400)
    return JsonResponse({"ok": True, "toast": toast, "status": appt.status,
                         "status_label": tg.STATUS_LABEL.get(appt.status, appt.status)})
