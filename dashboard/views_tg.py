# -*- coding: utf-8 -*-
"""Пробное сообщение в Telegram из настроек кабинета.

Владелец вписывает номер чата и сразу жмёт «Проверить»: если сообщение
пришло — номер верный. Без этого ошибку в номере замечали только тогда,
когда терялся первый заказ.
"""
import time

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from integrations import tgbot


# Простая защита от повторных нажатий: не чаще раза в три секунды
# на пользователя. Храним в памяти процесса — этого достаточно.
_last_call = {}


@login_required
@require_POST
def tg_test(request):
    chat_id = (request.POST.get("chat_id") or "").strip()
    thread = (request.POST.get("thread_id") or "").strip()
    if not chat_id:
        return JsonResponse({"ok": False, "error": "Не указан Chat ID"})

    now = time.time()
    if now - _last_call.get(request.user.id, 0) < 3:
        return JsonResponse({"ok": False, "error": "Подождите пару секунд"})
    _last_call[request.user.id] = now

    if not tgbot.bot_token():
        return JsonResponse({"ok": False,
                             "error": "Бот не настроен — напишите в поддержку"})

    # Сначала смотрим, виден ли чат боту: так ошибка понятнее, чем
    # «chat not found» в ответ на отправку.
    chat = tgbot.call("getChat", _timeout=20, _tries=2, chat_id=chat_id)
    if not chat:
        err = tgbot.last_error or ""
        if "not found" in err.lower():
            err = ("Чат не найден. Проверьте номер и то, что бот "
                   "добавлен в эту группу.")
        elif "kicked" in err.lower() or "blocked" in err.lower():
            err = "Бота удалили из этого чата — добавьте заново."
        return JsonResponse({"ok": False, "error": err or "Чат недоступен"})

    payload = {"chat_id": chat_id,
               "text": "🔧 Проверка связи: уведомления будут приходить сюда."}
    if thread:
        try:
            payload["message_thread_id"] = int(thread)
        except ValueError:
            return JsonResponse({"ok": False, "error": "Topic ID — только цифры"})

    res = tgbot.call("sendMessage", _timeout=20, _tries=2, **payload)
    if not res:
        err = tgbot.last_error or "Не вышло отправить"
        if "thread not found" in err.lower():
            err = "Тема с таким Topic ID не найдена — проверьте номер темы."
        elif "not enough rights" in err.lower():
            err = "У бота нет права писать в этот чат — сделайте его администратором."
        return JsonResponse({"ok": False, "error": err})

    title = (chat.get("title") or chat.get("username")
             or chat.get("first_name") or "")
    return JsonResponse({"ok": True, "title": title})
