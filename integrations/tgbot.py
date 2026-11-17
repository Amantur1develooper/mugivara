# -*- coding: utf-8 -*-
"""Общая часть телеграм-карточек: бот, подписи, проверка мини-приложения.

Карточку с кнопками шлют и барбершопы, и картинг — различается только текст
и набор кнопок. Всё, что одинаково, живёт здесь, чтобы не расходилось.
"""
import logging
import threading
import time

import requests
from django.conf import settings
from django.core import signing

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 8
TOKEN_MAX_AGE = 60 * 60 * 24 * 120      # ссылка из чата живёт четыре месяца


def bot_token():
    return (getattr(settings, "TG_BOT_TOKEN", "") or
            getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


# Последняя ошибка от Telegram — чтобы команда могла показать её человеку,
# а не гадать по логу. Обычные отправки её просто игнорируют.
last_error = ""


def call(method, _timeout=TIMEOUT, _tries=1, **payload):
    """Зовёт метод Bot API. Молча переживает отказ: запись важнее уведомления.

    _timeout и _tries нужны настроечным командам: api.telegram.org из
    Кыргызстана отвечает через раз, и setWebhook не укладывается в те
    восемь секунд, которых хватает обычному сообщению.
    """
    global last_error
    token = bot_token()
    if not token:
        last_error = "токен бота не задан (TELEGRAM_BOT_TOKEN в .env)"
        return None

    for attempt in range(1, max(1, _tries) + 1):
        try:
            r = requests.post(API.format(token=token, method=method),
                              json=payload, timeout=_timeout)
            data = r.json()
            if data.get("ok"):
                last_error = ""
                return data.get("result")
            last_error = data.get("description") or f"HTTP {r.status_code}"
            log.warning("telegram %s: %s", method, last_error)
            return None            # Telegram ответил и отказал — повтор не поможет
        except Exception as e:
            last_error = str(e)
            log.warning("telegram %s упал (попытка %s): %s", method, attempt, e)
            if attempt < _tries:
                time.sleep(2 * attempt)
    return None


def in_background(fn, *args, **kwargs):
    """Выполняет отправку в отдельном потоке.

    Telegram отвечает за доли секунды, но бывает и за несколько, а клиент всё
    это время смотрит на крутилку после нажатия «Записаться». Уведомление не
    должно держать ответ страницы.
    """
    def runner():
        try:
            fn(*args, **kwargs)
        except Exception:
            log.exception("фоновая отправка в Telegram упала")
        finally:
            # соединение с базой, открытое в этом потоке, закрываем за собой
            from django.db import connections
            connections.close_all()

    threading.Thread(target=runner, daemon=True).start()


# ── подписанные ссылки на карточку ───────────────────────────────────────────

def sign(obj_id, salt):
    return signing.dumps(obj_id, salt=salt)


def unsign(token, salt):
    """id из подписанной ссылки или None, если ссылка чужая либо протухла."""
    try:
        return signing.loads(token, salt=salt, max_age=TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None


# ── отправка карточки ────────────────────────────────────────────────────────

def send_card(chat_id, thread_id, text, keyboard):
    """Шлёт карточку в чат. Возвращает id сообщения или None."""
    if not chat_id:
        return None
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True, "reply_markup": keyboard}
    if thread_id:
        payload["message_thread_id"] = int(thread_id)

    res = call("sendMessage", **payload)
    if not res and thread_id:
        payload.pop("message_thread_id")      # темы в чате могли выключить
        res = call("sendMessage", **payload)
    if not res:
        # Одна негодная кнопка отменяет всё сообщение. Лучше прислать карточку
        # без ссылки, чем не прислать запись вовсе.
        payload["reply_markup"] = {"inline_keyboard": [
            row for row in keyboard.get("inline_keyboard", [])
            if not any("web_app" in b or "url" in b for b in row)
        ]}
        res = call("sendMessage", **payload)
    return (res or {}).get("message_id")


def edit_card(chat_id, message_id, text, keyboard):
    if not (chat_id and message_id):
        return None
    return call("editMessageText", chat_id=chat_id, message_id=message_id,
                text=text, parse_mode="HTML", disable_web_page_preview=True,
                reply_markup=keyboard)


def open_button(url, text, is_group):
    """Кнопка карточки записи.

    Мини-приложение Telegram разрешает открывать inline-кнопкой только в
    личной переписке с ботом: в группе такая кнопка валит всё сообщение
    с ошибкой BUTTON_TYPE_INVALID. Поэтому в группе — обычная ссылка.
    """
    if url.startswith("https://") and not is_group:
        return {"text": text, "web_app": {"url": url}}
    return {"text": text, "url": url}


def is_group(chat_id):
    """У групповых чатов номер отрицательный, у личных — нет."""
    return str(chat_id or "").startswith("-")


# ── мини-приложение ──────────────────────────────────────────────────────────

def verify_init_data(init_data, max_age=60 * 60 * 24):
    """Проверяет подпись initData мини-приложения Telegram.

    Ссылка на карточку лежит в закрытом чате заведения, но если она утечёт,
    по ней можно будет только смотреть: менять статус разрешаем лишь тому,
    кто открыл карточку внутри Telegram — его данные подписаны ботом.
    Возвращает словарь пользователя или None.
    """
    import hashlib
    import hmac
    import json as _json
    import time
    from urllib.parse import parse_qsl

    token = bot_token()
    if not (init_data and token):
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None
    got = pairs.pop("hash", "")
    if not got:
        return None

    check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    want = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, got):
        return None
    if max_age and abs(time.time() - int(pairs.get("auth_date", 0))) > max_age:
        return None
    try:
        return _json.loads(pairs.get("user", "{}")) or {}
    except ValueError:
        return {}


def actor_name(user):
    """Как подписать того, кто нажал кнопку: @ник или имя."""
    if not user:
        return ""
    if user.get("username"):
        return "@" + user["username"]
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)
    return name or f"id{user.get('id', '')}"


# ── общее для текста карточек ────────────────────────────────────────────────

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг",
            "пятница", "суббота", "воскресенье"]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def when(appt_date, appt_time, duration_min, today):
    """«Сегодня, 14 ноября (пятница), 15:30 — 16:10»."""
    delta = (appt_date - today).days
    day = {0: "Сегодня", 1: "Завтра", -1: "Вчера"}.get(delta, "")
    date_part = f"{appt_date.day} {MONTHS[appt_date.month - 1]}"
    weekday = WEEKDAYS[appt_date.weekday()]
    start = appt_time.strftime("%H:%M")
    end_min = appt_time.hour * 60 + appt_time.minute + (duration_min or 30)
    end = f"{end_min // 60 % 24:02d}:{end_min % 60:02d}"
    head = f"{day}, {date_part}" if day else date_part
    return f"{head} ({weekday}), {start} — {end}"
