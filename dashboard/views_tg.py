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
    # Точный адрес чата, если Telegram его знает: у публичной группы это
    # @имя, у закрытой — ссылка-приглашение (её видно, только если бот
    # администратор). Иначе на странице останется адрес вида t.me/c/…,
    # который собирается из номера и открывается у участников группы.
    username = chat.get("username") or ""
    link = f"https://t.me/{username}" if username else ""
    invite = chat.get("invite_link") or ""
    return JsonResponse({"ok": True, "title": title, "link": link,
                         "invite": invite})


@login_required
@require_POST
def tg_invite(request):
    """Ссылка-приглашение в чат, чтобы в группу можно было вступить.

    Адрес вида t.me/c/… открывается только у тех, кто в группе уже есть.
    Чтобы позвать нового человека, нужна именно ссылка-приглашение.

    Берём её по возрастанию вмешательства: имя публичной группы, затем
    готовая основная ссылка, и только если их нет — создаём новую. Создаём
    через createChatInviteLink, а не exportChatInviteLink: последний
    отзывает прежнюю основную ссылку, и у всех, кому её уже разослали,
    она перестала бы работать.
    """
    chat_id = (request.POST.get("chat_id") or "").strip()
    if not chat_id:
        return JsonResponse({"ok": False, "error": "Не указан Chat ID"})

    now = time.time()
    if now - _last_call.get(request.user.id, 0) < 3:
        return JsonResponse({"ok": False, "error": "Подождите пару секунд"})
    _last_call[request.user.id] = now

    if not tgbot.bot_token():
        return JsonResponse({"ok": False,
                             "error": "Бот не настроен — напишите в поддержку"})

    chat = tgbot.call("getChat", _timeout=20, _tries=2, chat_id=chat_id)
    if not chat:
        err = tgbot.last_error or ""
        if "not found" in err.lower():
            err = "Чат не найден. Проверьте номер и то, что бот добавлен в группу."
        return JsonResponse({"ok": False, "error": err or "Чат недоступен"})

    title = (chat.get("title") or chat.get("username")
             or chat.get("first_name") or "")

    if chat.get("username"):
        return JsonResponse({"ok": True, "link": f"https://t.me/{chat['username']}",
                             "title": title, "kind": "public"})

    if chat.get("invite_link"):
        return JsonResponse({"ok": True, "link": chat["invite_link"],
                             "title": title, "kind": "existing"})

    made = tgbot.call("createChatInviteLink", _timeout=20, _tries=2,
                      chat_id=chat_id, name="Webordo")
    if not made or not made.get("invite_link"):
        err = (tgbot.last_error or "").lower()
        if "not enough rights" in err or "administrator" in err:
            msg = ("У бота нет права приглашать. Сделайте его администратором "
                   "группы с правом «Пригласительные ссылки» и нажмите ещё раз.")
        elif "private chat" in err or "chat_id" in err:
            msg = "Это личный чат, а не группа — приглашать в него некуда."
        else:
            msg = tgbot.last_error or "Telegram не дал ссылку"
        return JsonResponse({"ok": False, "error": msg})

    return JsonResponse({"ok": True, "link": made["invite_link"],
                         "title": title, "kind": "new"})
