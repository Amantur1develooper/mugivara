"""Уведомления отеля в Telegram-группу филиала."""
from django.conf import settings


def get_bot_token():
    return (getattr(settings, "TG_BOT_TOKEN", "") or getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


def notify_branch(branch, msg):
    """Отправить сообщение в TG-группу филиала. Тихо игнорирует ошибки и отсутствие настроек."""
    token = get_bot_token()
    if not token or not getattr(branch, "tg_chat_id", ""):
        return
    try:
        from integrations.telegram import send_message
        send_message(token, branch.tg_chat_id, msg, message_thread_id=branch.tg_thread_id)
    except Exception:
        pass


def notify_booking_event(booking, event):
    """event: 'checkin' | 'checkout'. Формирует и шлёт сообщение о заезде/выезде."""
    from django.utils import timezone

    branch = booking.branch
    room = booking.room.name_ru if booking.room else "—"
    when = timezone.localtime(
        booking.actual_checkin_at if event == "checkin" else booking.actual_checkout_at
    )

    if event == "checkin":
        head = "🔑 Заселение"
        line_when = f"Заехал(а): {when:%d.%m.%Y %H:%M}"
        if booking.checkout_date:
            line_when += f"\nВыезд по плану: {booking.checkout_date:%d.%m.%Y}"
    else:
        head = "🏁 Выезд"
        line_when = f"Выехал(а): {when:%d.%m.%Y %H:%M}"

    msg = f"{head}\n\n"
    msg += f"{branch.hotel.name_ru} — {branch.name_ru}\n"
    msg += f"Номер: {room}\n"
    msg += f"Гость: {booking.customer_name}\n"
    if booking.customer_phone:
        msg += f"Тел: {booking.customer_phone}\n"
    if booking.guests:
        msg += f"Гостей: {booking.guests}\n"
    msg += line_when + "\n"
    if booking.total:
        msg += f"Сумма: {int(booking.total):,} сом\n".replace(",", " ")

    notify_branch(branch, msg)
