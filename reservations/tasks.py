import logging
from celery import shared_task
from django.conf import settings
from reservations.models import Booking
from integrations.models import BranchTelegramLink
from integrations.telegram import send_message  # как у тебя называется

logger = logging.getLogger(__name__)

@shared_task
def notify_new_booking(booking_id: int):
    b = Booking.objects.select_related("branch", "place").get(id=booking_id)

    links = BranchTelegramLink.objects.filter(
        branch=b.branch,
        notify_bookings=True,
        recipient__is_active=True
    ).select_related("recipient")

    text = (
        f"✅ Новая бронь\n"
        f"Филиал: {b.branch}\n"
        f"Место: {b.place.title}\n"
        f"Гостей: {b.guests_count}\n"
        f"Имя: {b.customer_name or '-'}\n"
        f"Тел: {b.customer_phone or '-'}\n"
        f"Комментарий: {b.comment or '-'}"
    )

    logger.info("BOOKING notify: booking=%s links=%s", b.id, links.count())

    for link in links:
        r = link.recipient
        try:
            send_message(
                settings.TG_BOT_TOKEN,
                str(r.chat_id),
                text,
                message_thread_id=(r.message_thread_id or None)  # <-- ВАЖНО
            )
        except Exception:
            logger.exception("TG booking send failed: recipient_id=%s chat_id=%s", r.id, r.chat_id)
