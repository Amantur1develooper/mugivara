# -*- coding: utf-8 -*-
"""Карточка брони картинга в Telegram: сообщение с кнопками.

Устроена так же, как у барбершопа: бронь приходит в чат площадки карточкой,
статус меняется кнопками прямо в чате, само сообщение переписывается.
Общая механика — в integrations.tgbot, здесь только текст и кнопки картинга.
"""
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from integrations import tgbot

bot_token = tgbot.bot_token
verify_init_data = tgbot.verify_init_data
actor_name = tgbot.actor_name

SALT = "simracing.appointment"


def _call(method, **payload):
    return tgbot.call(method, **payload)


STATUS_LABEL = {
    "new":       "🆕 Новая",
    "confirmed": "✅ Подтверждена",
    "canceled":  "❌ Отменена",
}

# действие кнопки → (новый статус, ответ во всплывашке)
ACTIONS = {
    "confirm": ("confirmed", "Бронь подтверждена"),
    "cancel":  ("canceled",  "Бронь отменена"),
    "reopen":  ("new",       "Бронь снова в новых"),
}


def sign_appointment(appt):
    return tgbot.sign(appt.id, SALT)


def unsign_appointment(token):
    return tgbot.unsign(token, SALT)


def card_url(appt):
    base = getattr(settings, "SITE_URL", "").rstrip("/")
    return base + reverse("simracing_tg:card", args=[sign_appointment(appt)])


# ── текст и кнопки ───────────────────────────────────────────────────────────

def _when(appt):
    return tgbot.when(appt.appt_date, appt.appt_time, appt.duration_minutes,
                      timezone.localdate())


def ride_line(appt):
    """«Картинг · 2 машины × 10 мин» — что именно забронировали."""
    per = appt.session_type.duration_minutes if appt.session_type else appt.duration_minutes
    machines = appt.quantity or 1
    word = "машина" if machines == 1 else ("машины" if machines < 5 else "машин")
    if machines == 1:
        return f"{appt.type_title} · {per} мин"
    return f"{appt.type_title} · {machines} {word} × {per} мин (едут одновременно)"


def message_text(appt, footer=""):
    lines = [
        f"🏎 <b>Бронь №{appt.id}</b> · {STATUS_LABEL.get(appt.status, appt.status)}",
        "",
        f"📅 {_when(appt)}",
        f"🚗 {ride_line(appt)}",
        "",
        f"👤 {appt.customer_name or 'Гость'}",
    ]
    if appt.customer_phone:
        lines.append(f"📞 {appt.customer_phone}")
    lines.append("")
    if appt.discount_percent:
        lines.append(f"💸 Скидка −{appt.discount_percent}%")
    lines.append(f"💰 {int(appt.total_price)} сом")
    if appt.notes:
        lines.append(f"💬 {appt.notes.splitlines()[0]}")
    if footer:
        lines += ["", f"<i>{footer}</i>"]
    return "\n".join(lines)


def _open_button(appt):
    return tgbot.open_button(card_url(appt), "📋 Карточка брони",
                             tgbot.is_group(appt.venue.tg_chat_id))


def keyboard(appt):
    rows = []
    if appt.status == "new":
        rows.append([{"text": "✅ Подтвердить", "callback_data": f"sr:confirm:{appt.id}"},
                     {"text": "❌ Отменить",    "callback_data": f"sr:cancel:{appt.id}"}])
    elif appt.status == "confirmed":
        rows.append([{"text": "❌ Отменить", "callback_data": f"sr:cancel:{appt.id}"}])
    else:
        rows.append([{"text": "↩️ Вернуть в новые", "callback_data": f"sr:reopen:{appt.id}"}])
    rows.append([_open_button(appt)])
    return {"inline_keyboard": rows}


# ── отправка и обновление ────────────────────────────────────────────────────

def send_appointment(appt):
    venue = appt.venue
    message_id = tgbot.send_card(venue.tg_chat_id, venue.tg_thread_id,
                                 message_text(appt), keyboard(appt))
    if message_id:
        appt.tg_message_id = message_id
        appt.save(update_fields=["tg_message_id"])
    return message_id


def refresh_appointment(appt, footer=""):
    venue = appt.venue
    return tgbot.edit_card(venue.tg_chat_id, appt.tg_message_id,
                           message_text(appt, footer), keyboard(appt))


def apply_action(appt, action, actor=""):
    """Меняет статус брони по нажатой кнопке. Возвращает текст для всплывашки."""
    if action not in ACTIONS:
        return None
    new_status, toast = ACTIONS[action]
    if appt.status == new_status:
        return f"Уже отмечено: {STATUS_LABEL[new_status]}"

    appt.status = new_status
    stamp = timezone.localtime().strftime("%d.%m %H:%M")
    mark = f"{STATUS_LABEL[new_status]} — {actor or 'Telegram'}, {stamp}"
    appt.notes = (appt.notes + "\n" + mark).strip() if appt.notes else mark
    appt.save(update_fields=["status", "notes"])

    # Подтверждение в кабинете печатает талон — кнопка в чате должна делать
    # то же самое, иначе клиент останется без бумажки.
    if new_status == "confirmed":
        try:
            from .print_jobs import create_appt_print_job
            create_appt_print_job(appt)
        except Exception:
            pass

    refresh_appointment(appt, footer=mark)
    return toast
