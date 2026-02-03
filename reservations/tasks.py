from celery import shared_task
from django.conf import settings
from django.utils import timezone

from reservations.models import Booking
from integrations.models import BranchTelegramLink  # как у тебя
from integrations.telegram import send_message      # твоя функция

@shared_task
def notify_new_booking(booking_id: int):
    booking = Booking.objects.select_related("branch", "place").get(id=booking_id)

    text = (
        f"📌 Новая бронь\n"
        f"Филиал: {booking.branch.name_ru}\n"
        f"Место: {booking.place.title}\n"
        f"Гостей: {booking.guests_count}\n"
        f"Имя: {booking.customer_name or '-'}\n"
        f"Тел: {booking.customer_phone or '-'}\n"
        f"Комментарий: {booking.comment or '-'}\n"
        f"Время: {timezone.localtime(booking.created_at).strftime('%d.%m %H:%M')}"
    )

    links = (BranchTelegramLink.objects
        .filter(branch=booking.branch, notify_bookings=True, recipient__is_active=True)
        .select_related("recipient")
    )

    bot_token = settings.TG_BOT_TOKEN

    sent = 0
    for link in links:
        r = link.recipient
        send_message(
            bot_token=bot_token,
            chat_id=str(r.chat_id),
            text=text,
            parse_mode=None,
            message_thread_id=getattr(r, "message_thread_id", None),
        )
        sent += 1

    return {"sent": sent}
