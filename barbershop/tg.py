# -*- coding: utf-8 -*-
"""Карточка записи в Telegram: сообщение с кнопками вместо простого текста.

Раньше бот присылал в чат барбершопа текст, и чтобы подтвердить запись,
администратор шёл на сайт. Теперь к сообщению прикреплены кнопки: статус
меняется прямо в чате, а само сообщение переписывается — в истории остаётся
одна карточка записи, а не лента уведомлений.

Кнопка «Карточка записи» открывает мини-приложение Telegram: ту же запись
с кнопками и телефоном клиента, не выходя из мессенджера.
"""
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from integrations import tgbot

# Старые имена оставлены: на них завязаны вызовы в видах и тестах.
API = tgbot.API
bot_token = tgbot.bot_token
verify_init_data = tgbot.verify_init_data
actor_name = tgbot.actor_name

SALT = "barbershop.appointment"


def _call(method, **payload):
    return tgbot.call(method, **payload)


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

# ── ссылка на мини-приложение ────────────────────────────────────────────────

def sign_appointment(appt):
    return tgbot.sign(appt.id, SALT)


def unsign_appointment(token):
    return tgbot.unsign(token, SALT)


def card_url(appt):
    base = getattr(settings, "SITE_URL", "").rstrip("/")
    return base + reverse("barbershop_tg:card", args=[sign_appointment(appt)])


# ── текст и кнопки ───────────────────────────────────────────────────────────

def _when(appt):
    return tgbot.when(appt.appt_date, appt.appt_time, appt.duration_min,
                      timezone.localdate())


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
    return tgbot.open_button(card_url(appt), "📋 Карточка записи",
                             tgbot.is_group(appt.barbershop.tg_chat_id))


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
    message_id = tgbot.send_card(shop.tg_chat_id, shop.tg_thread_id,
                                 message_text(appt), keyboard(appt))
    if message_id:
        appt.tg_message_id = message_id
        appt.save(update_fields=["tg_message_id"])
    return message_id


def refresh_appointment(appt, footer=""):
    """Переписывает карточку в чате после смены статуса."""
    shop = appt.barbershop
    return tgbot.edit_card(shop.tg_chat_id, appt.tg_message_id,
                           message_text(appt, footer), keyboard(appt))


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
