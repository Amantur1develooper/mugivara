# -*- coding: utf-8 -*-
"""Два чата клуба: заявки и жизнь зала.

Заявку надо обработать — ей нужны кнопки и ответственный. Приход клиента,
продажа абонемента, расход — это лента событий, её читают, но не трогают.
Вперемешку в одной группе это невозможно: заявки теряются среди «Иванов
прошёл в зал». Поэтому чатов два, и шлём мы в них разное.
"""
import logging
from datetime import timedelta

from django.utils import timezone

from integrations import tgbot

log = logging.getLogger(__name__)

PREFIX = "ft"

LEAD_ACTIONS = {
    "take":   ("working", "Взяли в работу"),
    "booked": ("booked", "Записан"),
    "came":   ("came", "Отмечено: пришёл"),
    "sold":   ("sold", "Купил — красиво"),
    "lost":   ("lost", "Отказ"),
}

LEAD_BUTTONS = {
    "new":     [[("take", "📞 Взять в работу")], [("booked", "📅 Записан"), ("lost", "✖️ Отказ")]],
    "working": [[("booked", "📅 Записан"), ("came", "🚪 Пришёл")], [("lost", "✖️ Отказ")]],
    "booked":  [[("came", "🚪 Пришёл"), ("lost", "✖️ Не пришёл")]],
    "came":    [[("sold", "💰 Купил"), ("lost", "✖️ Не купил")]],
    "sold":    [],
    "lost":    [[("take", "↩️ Вернуть в работу")]],
}


def _money(value):
    try:
        return f"{int(value):,}".replace(",", " ") + " сом"
    except Exception:
        return f"{value} сом"


# ── куда слать ───────────────────────────────────────────────────────────────

def leads_chat(club):
    """Чат заявок. Если он не задан — валим в чат зала, лишь бы дошло."""
    chat = (club.tg_leads_chat_id or "").strip() or (club.tg_gym_chat_id or "").strip()
    thread = club.tg_leads_thread_id if (club.tg_leads_chat_id or "").strip() else club.tg_gym_thread_id
    return chat, thread


def gym_chat(club):
    chat = (club.tg_gym_chat_id or "").strip() or (club.tg_leads_chat_id or "").strip()
    thread = club.tg_gym_thread_id if (club.tg_gym_chat_id or "").strip() else club.tg_leads_thread_id
    return chat, thread


# ── заявки ───────────────────────────────────────────────────────────────────

def lead_text(lead, footer=""):
    lines = [f"🔥 ЗАЯВКА — {lead.get_status_display().upper()}",
             f"🏋️ {lead.club.name}"]
    if lead.name:
        lines.append(f"👤 {lead.name}")
    lines.append(f"📞 {lead.phone}")
    if lead.section_id:
        lines.append(f"🎯 Секция: {lead.section.name}")
    if lead.trainer_id:
        lines.append(f"🧑‍🏫 Тренер: {lead.trainer.name}")
    lines.append(f"🔗 Источник: {lead.get_source_display()}")
    if lead.comment:
        lines.append(f"💬 {lead.comment}")
    if lead.next_contact_at:
        lines.append(f"⏰ Связаться: {timezone.localtime(lead.next_contact_at):%d.%m %H:%M}")
    lines.append(f"🕒 {timezone.localtime(lead.created_at):%d.%m %H:%M}")
    text = "\n".join(lines)
    return f"{text}\n\n{footer}" if footer else text


def lead_keyboard(lead):
    rows = []
    for row in LEAD_BUTTONS.get(lead.status, []):
        rows.append([{"text": label, "callback_data": f"{PREFIX}:lead:{action}:{lead.id}"}
                     for action, label in row])
    return {"inline_keyboard": rows} if rows else None


def send_lead(lead, only_missing=False):
    chat, thread = leads_chat(lead.club)
    if not chat:
        return 0, 0
    ids = dict(lead.tg_messages or {})
    if only_missing and str(chat) in ids:
        return 0, 0
    mid = tgbot.send_card(chat, thread, lead_text(lead), lead_keyboard(lead))
    if not mid:
        return 0, 1
    ids[str(chat)] = mid
    lead.tg_messages = ids
    lead.save(update_fields=["tg_messages"])
    return 1, 0


def refresh_lead(lead, footer=""):
    text = lead_text(lead, footer)
    for chat, mid in (lead.tg_messages or {}).items():
        tgbot.edit_card(chat, mid, text, lead_keyboard(lead))


def apply_lead_action(lead, action, actor=""):
    """Меняет статус заявки по кнопке. Возвращает текст всплывашки."""
    if action not in LEAD_ACTIONS:
        return None
    new_status, toast = LEAD_ACTIONS[action]
    if lead.status == new_status:
        return f"Уже: {lead.get_status_display()}"

    lead.status = new_status
    lead.save(update_fields=["status", "updated_at"])

    from .models import LeadNote
    LeadNote.objects.create(lead=lead, text=f"{toast} (из Telegram, {actor or 'без имени'})")

    stamp = timezone.localtime().strftime("%d.%m %H:%M")
    refresh_lead(lead, footer=f"{lead.get_status_display()} — {actor or 'Telegram'}, {stamp}")
    return toast


# ── события зала ─────────────────────────────────────────────────────────────

def notify_gym(club, text):
    """Простое сообщение в чат зала: событие, а не задача."""
    chat, thread = gym_chat(club)
    if not chat:
        return False
    return bool(tgbot.send_card(chat, thread, text, None))


def visit_text(visit):
    m = visit.member
    lines = ["🚪 ПРОХОД В ЗАЛ" if visit.success else "⛔️ НЕ ПРОПУСТИЛИ",
             f"👤 {m.full_name if m else 'неизвестный'}"]
    if visit.membership_id:
        ms = visit.membership
        left = "без ограничения" if not ms.plan.visits_number else f"{ms.remaining_visits}"
        lines.append(f"🎫 {ms.plan.name} · осталось: {left}")
        if ms.end_date:
            lines.append(f"📅 Действует до {ms.end_date:%d.%m.%Y}")
    if visit.trainer_id:
        lines.append(f"🧑‍🏫 С тренером: {visit.trainer.name}")
    if not visit.success and visit.reason:
        lines.append(f"⚠️ {visit.reason}")
    lines.append(f"🕒 {timezone.localtime(visit.visit_time):%d.%m %H:%M}")
    return "\n".join(lines)


def payment_text(payment):
    lines = ["💰 ОПЛАТА",
             f"🧾 {payment.get_kind_display()} — {_money(payment.amount)}",
             f"💳 {payment.get_payment_method_display() if hasattr(payment, 'get_payment_method_display') else payment.get_method_display()}"]
    if payment.member_id:
        lines.append(f"👤 {payment.member.full_name}")
    if payment.membership_id:
        ms = payment.membership
        lines.append(f"🎫 {ms.plan.name}")
        if ms.debt_amount:
            lines.append(f"⚠️ Остался долг: {_money(ms.debt_amount)}")
    if payment.note:
        lines.append(f"💬 {payment.note}")
    lines.append(f"🕒 {timezone.localtime(payment.created_at):%d.%m %H:%M}")
    return "\n".join(lines)


def expense_text(expense):
    return "\n".join([
        "📉 РАСХОД",
        f"🏷 {expense.get_category_display()} — {_money(expense.amount)}",
        f"💬 {expense.note or '—'}",
        f"📅 {expense.spent_on:%d.%m.%Y}",
    ])


def booking_text(booking, footer=""):
    lines = ["🧑‍🏫 ЗАПИСЬ К ТРЕНЕРУ",
             f"🏋️ {booking.club.name}",
             f"👤 {booking.who}",
             f"🧑‍🏫 {booking.trainer.name}",
             f"📅 {booking.date:%d.%m.%Y} в {booking.time_from:%H:%M}"]
    if booking.phone:
        lines.append(f"📞 {booking.phone}")
    if booking.comment:
        lines.append(f"💬 {booking.comment}")
    lines.append(f"📌 {booking.get_status_display()}")
    text = "\n".join(lines)
    return f"{text}\n\n{footer}" if footer else text


BOOKING_BUTTONS = {
    "new":       [[("b_confirm", "✅ Подтвердить"), ("b_cancel", "✖️ Отменить")]],
    "confirmed": [[("b_came", "🚪 Пришёл"), ("b_noshow", "🚫 Не пришёл")]],
    "came":      [],
    "no_show":   [[("b_confirm", "↩️ Вернуть")]],
    "cancelled": [[("b_confirm", "↩️ Вернуть")]],
}

BOOKING_ACTIONS = {
    "b_confirm": ("confirmed", "Запись подтверждена"),
    "b_came":    ("came", "Отмечено: пришёл"),
    "b_noshow":  ("no_show", "Отмечено: не пришёл"),
    "b_cancel":  ("cancelled", "Запись отменена"),
}


def booking_keyboard(booking):
    rows = []
    for row in BOOKING_BUTTONS.get(booking.status, []):
        rows.append([{"text": label, "callback_data": f"{PREFIX}:book:{action}:{booking.id}"}
                     for action, label in row])
    return {"inline_keyboard": rows} if rows else None


def send_booking(booking):
    chat, thread = leads_chat(booking.club)
    if not chat:
        return 0, 0
    mid = tgbot.send_card(chat, thread, booking_text(booking), booking_keyboard(booking))
    if not mid:
        return 0, 1
    booking.tg_messages = {str(chat): mid}
    booking.save(update_fields=["tg_messages"])
    return 1, 0


def refresh_booking(booking, footer=""):
    text = booking_text(booking, footer)
    for chat, mid in (booking.tg_messages or {}).items():
        tgbot.edit_card(chat, mid, text, booking_keyboard(booking))


def apply_booking_action(booking, action, actor=""):
    if action not in BOOKING_ACTIONS:
        return None
    new_status, toast = BOOKING_ACTIONS[action]
    if booking.status == new_status:
        return f"Уже: {booking.get_status_display()}"
    booking.status = new_status
    booking.save(update_fields=["status", "updated_at"])
    stamp = timezone.localtime().strftime("%d.%m %H:%M")
    refresh_booking(booking, footer=f"{booking.get_status_display()} — {actor or 'Telegram'}, {stamp}")
    return toast

# ── Утренняя сводка ─────────────────────────────────────────────────────────

def _years(n):
    """«31 год», «22 года», «25 лет» — сообщение читают люди."""
    if n % 100 in (11, 12, 13, 14):
        return f"{n} лет"
    last = n % 10
    if last == 1:
        return f"{n} год"
    if last in (2, 3, 4):
        return f"{n} года"
    return f"{n} лет"


def digest_text(club, day, birthdays, expiring=(), lost=(), overdue=(), owed=()):
    """Короткая сводка на день: кого поздравить и кому позвонить.

    Поздравление — повод для разговора, который почти всегда заканчивается
    продлением. Но помнить о нём некому, поэтому напоминаем сами.
    """
    lines = [f"☀️ {club.name} — {day:%d.%m}"]

    if birthdays:
        lines.append("")
        lines.append("🎂 ДЕНЬ РОЖДЕНИЯ")
        for item in birthdays:
            m = item["member"]
            when = "сегодня" if item["when"] == day else f"{item['when']:%d.%m}"
            age = f", {_years(item['age'])}" if item.get("age") else ""
            phone = f" · {m.phone}" if m.phone else ""
            lines.append(f"• {m.full_name}{age} — {when}{phone}")

    if expiring:
        lines.append("")
        lines.append("⏳ АБОНЕМЕНТ КОНЧАЕТСЯ")
        for ms in expiring:
            left = (ms.end_date - day).days
            phone = f" · {ms.member.phone}" if ms.member.phone else ""
            lines.append(f"• {ms.member.full_name} — {left} дн."
                         f" (до {ms.end_date:%d.%m}){phone}")

    if lost:
        lines.append("")
        lines.append("😴 ДАВНО НЕ ПРИХОДИЛИ")
        for item in lost:
            m = item["member"]
            phone = f" · {m.phone}" if m.phone else ""
            days = f"{item['days']} дн." if item.get("days") else "ни разу"
            lines.append(f"• {m.full_name} — {days}{phone}")

    if owed:
        lines.append("")
        total = sum(item["count"] for item in owed)
        lines.append(f"🧾 ЗАНЯТИЯ В ДОЛГ — {total}")
        for item in owed:
            m = item["member"]
            phone = f" · {m.phone}" if m.phone else ""
            lines.append(f"• {m.full_name} — {item['count']}{phone}")

    if overdue:
        lines.append("")
        lines.append("⏰ ПРОСРОЧЕН ЗВОНОК ПО ЗАЯВКЕ")
        for lead in overdue:
            lines.append(f"• {lead.name or 'без имени'} · {lead.phone}"
                         f" — обещали {timezone.localtime(lead.next_contact_at):%d.%m %H:%M}")

    if len(lines) == 1:
        lines.append("")
        lines.append("Сегодня никого поздравлять и никому звонить не нужно.")
    return "\n".join(lines)

# ── Тренировки: напоминание и отмена ────────────────────────────────────────

WEEKDAYS_SHORT = ["понедельник", "вторник", "среду", "четверг",
                  "пятницу", "субботу", "воскресенье"]


def group_chat(group):
    """Куда писать группе: её собственный чат, иначе чат зала.

    У детских групп свой чат с родителями — напоминание о тренировке
    нужно им, а не общему чату зала. Чата нет — пишем в зал, лишь бы
    напоминание не пропало вовсе.
    """
    chat = (group.tg_chat_id or "").strip() if group else ""
    if chat:
        return chat, group.tg_thread_id
    return gym_chat(group.club) if group else (None, None)


def notify_group(group, text):
    chat, thread = group_chat(group)
    if not chat:
        return False
    return bool(tgbot.send_card(chat, thread, text, None))


def _when_word(day):
    """«сегодня», «завтра» или дата: так читают расписание вслух."""
    today = timezone.localdate()
    if day == today:
        return "сегодня"
    if day == today + timedelta(days=1):
        return "завтра"
    return f"в {WEEKDAYS_SHORT[day.weekday()]} {day:%d.%m}"


def class_reminder_text(slot, day):
    """Напоминание о тренировке."""
    title = slot.group.title if slot.group_id else slot.name
    lines = [f"🔔 ТРЕНИРОВКА {_when_word(day).upper()}",
             f"🥋 {title}",
             f"🕒 {day:%d.%m} в {slot.time_from:%H:%M}"
             f" · {slot.duration_min} мин"]
    if slot.trainer_id:
        lines.append(f"🧑‍🏫 {slot.trainer.name}")
    if slot.room:
        lines.append(f"📍 {slot.room}")
    if slot.group_id:
        lines.append(f"👥 в группе {slot.group.size} чел.")
    return "\n".join(lines)


def class_cancelled_text(slot, day, reason="", actor=""):
    """Сообщение об отмене одной тренировки."""
    title = slot.group.title if slot.group_id else slot.name
    lines = ["⛔️ ТРЕНИРОВКА ОТМЕНЕНА",
             f"🥋 {title}",
             f"🗓 {day:%d.%m} ({_when_word(day)}) в {slot.time_from:%H:%M}"]
    if reason:
        lines.append(f"💬 {reason}")
    if slot.trainer_id:
        lines.append(f"🧑‍🏫 {slot.trainer.name}")
    if actor:
        lines.append(f"✍️ отменил: {actor}")
    return "\n".join(lines)


def class_restored_text(slot, day):
    title = slot.group.title if slot.group_id else slot.name
    return ("✅ ТРЕНИРОВКА СОСТОИТСЯ\n"
            f"🥋 {title}\n"
            f"🗓 {day:%d.%m} ({_when_word(day)}) в {slot.time_from:%H:%M}")

