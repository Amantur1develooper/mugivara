from celery import shared_task
from django.conf import settings

from reservations.models import Booking
from integrations.models import BranchTelegramLink
from integrations.telegram import send_message


@shared_task
def notify_new_booking(booking_id: int):
    booking = (
        Booking.objects
        .select_related("branch", "place", "place__floor")
        .get(id=booking_id)
    )

    links = (
        BranchTelegramLink.objects
        .filter(branch=booking.branch, notify_bookings=True, recipient__is_active=True)
        .select_related("recipient")
    )

    if not links.exists():
        return  # некому отправлять

    floor_name = getattr(getattr(booking.place, "floor", None), "name_ru", "")
    text = (
        "🪑 *Новая бронь*\n"
        f"Филиал: *{booking.branch.name_ru}*\n"
        f"Место: *{booking.place.title}*\n"
        f"Этаж: {floor_name}\n"
        f"Гостей: *{booking.guests_count}*\n"
        f"Имя: {booking.customer_name or '—'}\n"
        f"Тел: {booking.customer_phone or '—'}\n"
        f"Комментарий: {booking.comment or '—'}\n"
        f"ID: #{booking.id}"
    )

    for link in links:
        r = link.recipient
        send_message(
            settings.TELEGRAM_BOT_TOKEN,
            str(r.chat_id),
            text,
            parse_mode="Markdown",
            message_thread_id=r.message_thread_id or None,
        )
