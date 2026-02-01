# reservations/tasks.py
from celery import shared_task
from django.urls import reverse
from django.conf import settings
from django.utils import timezone

from integrations.telegram import send_message
# from integrations.models import BranchTelegramLink
from .models import Booking

@shared_task
def notify_new_booking(booking_id: int):
    b = (Booking.objects
         .select_related("branch", "place", "place__floor")
         .get(id=booking_id))

    links = (BranchTelegramLink.objects
             .select_related("recipient")
             .filter(branch=b.branch, notify_bookings=True, recipient__is_active=True))

    # ссылка на страницу брони/плана (если хочешь)
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    hall_url = ""
    if site:
        hall_url = site + reverse("public_site:hall_plan", args=[b.branch_id])

    created = timezone.localtime(b.created_at).strftime("%d.%m %H:%M")

    text = (
        f"📌 <b>Новая бронь</b>\n"
        f"🏢 <b>{b.branch.name_ru}</b>\n"
        f"📍 {b.branch.address}\n\n"
        f"🪑 <b>{b.place.title}</b> ({'Кабинка' if b.place.type=='cabin' else 'Стол'})\n"
        f"👥 Гостей: <b>{b.guests_count}</b>\n"
        f"👤 Имя: {b.customer_name or '—'}\n"
        f"📞 Тел: {b.customer_phone or '—'}\n"
        f"💬 Коммент: {b.comment or '—'}\n"
        f"🕒 Создано: {created}\n"
    )
    if hall_url:
        text += f"\n🗺 План зала: {hall_url}\n"

    for link in links:
        send_message(
            chat_id=link.recipient.chat_id,
            text=text,
            thread_id=link.recipient.thread_id,
        )
