# -*- coding: utf-8 -*-
"""Карточка записи в Telegram: сообщение с кнопками вместо простого текста.

Раньше бот присылал в чат барбершопа текст, и чтобы подтвердить запись,
администратор шёл на сайт. Теперь к сообщению прикреплены кнопки: статус
меняется прямо в чате, а само сообщение переписывается — в истории остаётся
одна карточка записи, а не лента уведомлений.

Кнопка «Карточка записи» открывает мини-приложение Telegram: ту же запись
с кнопками и телефоном клиента, не выходя из мессенджера.
"""
import logging

import requests
from django.conf import settings
from django.core import signing
from django.urls import reverse
from django.utils import timezone

log = logging.getLogger(__name__)

API = "https://api.telegram.org/bot{token}/{method}"
TIMEOUT = 8
SALT = "barbershop.appointment"
TOKEN_MAX_AGE = 60 * 60 * 24 * 120      # ссылка из чата живёт четыре месяца

STATUS_LABEL = {
    "new":       "🆕 Новая",
    "confirmed": "✅ Подтверждена",
    "done":      "🏁 Выполнена",
    "cancelled": "❌ Отменена",
    "no_show":   "🚫 Клиент не пришёл",
}

# что делает каждая кнопка: действие → (новый статус, ответ во всплывашке)
ACTIONS = {
    "confirm": ("confirmed", "Запись подтверждена"),
    "done":    ("done",      "Отмечено: услуга оказана"),
    "cancel":  ("cancelled", "Запись отменена"),
    "no_show": ("no_show",   "Отмечено: клиент не пришёл"),
}

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг",
            "пятница", "суббота", "воскресенье"]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
          "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def bot_token():
    return (getattr(settings, "TG_BOT_TOKEN", "") or
            getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


def _call(method, **payload):
    """Зовёт метод Bot API. Молча переживает отказ: запись важнее уведомления."""
    token = bot_token()
    if not token:
        return None
    try:
        r = requests.post(API.format(token=token, method=method),
                          json=payload, timeout=TIMEOUT)
        data = r.json()
        if not data.get("ok"):
            log.warning("telegram %s: %s", method, data.get("description"))
            return None
        return data.get("result")
    except Exception as e:
        log.warning("telegram %s упал: %s", method, e)
        return None


# ── ссылка на мини-приложение ────────────────────────────────────────────────

def sign_appointment(appt):
    return signing.dumps(appt.id, salt=SALT)


def unsign_appointment(token):
    """id записи из подписанной ссылки или None, если ссылка чужая/протухла."""
    try:
        return signing.loads(token, salt=SALT, max_age=TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None


def card_url(appt):
    base = getattr(settings, "SITE_URL", "").rstrip("/")
    return base + reverse("barbershop_tg:card", args=[sign_appointment(appt)])


# ── текст и кнопки ───────────────────────────────────────────────────────────

def _when(appt):
    """«Сегодня, 14 ноября (пятница), 15:30 — 16:10»."""
    today = timezone.localdate()
    delta = (appt.appt_date - today).days
    if delta == 0:
        day = "Сегодня"
    elif delta == 1:
        day = "Завтра"
    elif delta == -1:
        day = "Вчера"
    else:
        day = f"{appt.appt_date.day} {MONTHS[appt.appt_date.month - 1]}"
    weekday = WEEKDAYS[appt.appt_date.weekday()]
    start = appt.appt_time.strftime("%H:%M")
    end_min = appt.appt_time.hour * 60 + appt.appt_time.minute + (appt.duration_min or 30)
    end = f"{end_min // 60 % 24:02d}:{end_min % 60:02d}"
    date_part = f"{appt.appt_date.day} {MONTHS[appt.appt_date.month - 1]}"
    if delta in (-1, 0, 1):
        return f"{day}, {date_part} ({weekday}), {start} — {end}"
    return f"{date_part} ({weekday}), {start} — {end}"


def services_of(appt):
    """Состав записи: [(название, цена или None)].

    Берём снимок, сделанный при брони. У записей, заведённых до того, как
    снимок появился, его нет — тогда достаём цены из прайса по названиям.
    """
    snap = appt.services_snapshot or []
    if snap:
        return [(row.get("name", ""), row.get("price")) for row in snap if row.get("name")]

    names = [s.strip() for s in (appt.service_name or "").split("+") if s.strip()]
    if not names:
        return []
    from .models import Service
    prices = dict(
        Service.objects.filter(barbershop_id=appt.barbershop_id, name__in=names)
        .values_list("name", "price")
    )
    return [(n, int(prices[n]) if n in prices else None) for n in names]


def services_lines(appt, bullet="  • "):
    out = []
    for name, price in services_of(appt):
        out.append(f"{bullet}{name} — {int(price)} сом" if price is not None
                   else f"{bullet}{name}")
    return out


def message_text(appt, footer=""):
    services = services_lines(appt)
    lines = [
        f"✂️ <b>Запись №{appt.id}</b> · {STATUS_LABEL.get(appt.status, appt.status)}",
        "",
        f"📅 {_when(appt)}",
        f"💈 Мастер: {appt.barber_name or '—'}",
        "",
        f"👤 {appt.customer_name}",
    ]
    if appt.customer_phone:
        lines.append(f"📞 {appt.customer_phone}")
    if services:
        lines.append("")
        lines.append("📋 " + ("Услуги:" if len(services) > 1 else "Услуга:"))
        lines += services
    lines.append("")
    lines.append(f"💰 {int(appt.price_snapshot)} сом · {appt.duration_min} мин")
    if appt.comment:
        lines.append(f"💬 {appt.comment}")
    if footer:
        lines += ["", f"<i>{footer}</i>"]
    return "\n".join(lines)


def _open_button(appt):
    """Кнопка мини-приложения. Telegram принимает только https, иначе — ссылкой."""
    url = card_url(appt)
    if url.startswith("https://"):
        return {"text": "📋 Карточка записи", "web_app": {"url": url}}
    return {"text": "📋 Карточка записи", "url": url}


def keyboard(appt):
    rows = []
    if appt.status == "new":
        rows.append([{"text": "✅ Подтвердить", "callback_data": f"bs:confirm:{appt.id}"},
                     {"text": "❌ Отменить",    "callback_data": f"bs:cancel:{appt.id}"}])
    elif appt.status == "confirmed":
        rows.append([{"text": "🏁 Выполнена",     "callback_data": f"bs:done:{appt.id}"},
                     {"text": "🚫 Не пришёл",     "callback_data": f"bs:no_show:{appt.id}"}])
        rows.append([{"text": "❌ Отменить",      "callback_data": f"bs:cancel:{appt.id}"}])
    else:
        rows.append([{"text": "↩️ Вернуть в новые", "callback_data": f"bs:reopen:{appt.id}"}])
    rows.append([_open_button(appt)])
    return {"inline_keyboard": rows}


# ── отправка и обновление ────────────────────────────────────────────────────

def send_appointment(appt):
    """Шлёт карточку записи в чат барбершопа и запоминает номер сообщения."""
    shop = appt.barbershop
    if not shop.tg_chat_id:
        return None
    payload = {
        "chat_id": shop.tg_chat_id,
        "text": message_text(appt),
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": keyboard(appt),
    }
    if shop.tg_thread_id:
        payload["message_thread_id"] = int(shop.tg_thread_id)
    res = _call("sendMessage", **payload)
    if not res and shop.tg_thread_id:
        payload.pop("message_thread_id")      # темы в чате могли выключить
        res = _call("sendMessage", **payload)
    if res and res.get("message_id"):
        appt.tg_message_id = res["message_id"]
        appt.save(update_fields=["tg_message_id"])
    return res


def refresh_appointment(appt, footer=""):
    """Переписывает карточку в чате после смены статуса."""
    shop = appt.barbershop
    if not (shop.tg_chat_id and appt.tg_message_id):
        return None
    return _call("editMessageText",
                 chat_id=shop.tg_chat_id,
                 message_id=appt.tg_message_id,
                 text=message_text(appt, footer),
                 parse_mode="HTML",
                 disable_web_page_preview=True,
                 reply_markup=keyboard(appt))


def apply_action(appt, action, actor=""):
    """Меняет статус записи по нажатой кнопке. Возвращает текст для всплывашки."""
    if action == "reopen":
        new_status, toast = "new", "Запись снова в новых"
    elif action in ACTIONS:
        new_status, toast = ACTIONS[action]
    else:
        return None
    if appt.status == new_status:
        return f"Уже отмечено: {STATUS_LABEL[new_status]}"

    appt.status = new_status
    stamp = timezone.localtime().strftime("%d.%m %H:%M")
    mark = f"{STATUS_LABEL[new_status]} — {actor or 'Telegram'}, {stamp}"
    appt.notes = (appt.notes + "\n" + mark).strip() if appt.notes else mark
    appt.save(update_fields=["status", "notes", "updated_at"])
    refresh_appointment(appt, footer=mark)
    return toast


# ── проверка мини-приложения ─────────────────────────────────────────────────

def verify_init_data(init_data, max_age=60 * 60 * 24):
    """Проверяет подпись initData мини-приложения Telegram.

    Ссылка на карточку лежит в закрытом чате барбершопа, но если она утечёт,
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
