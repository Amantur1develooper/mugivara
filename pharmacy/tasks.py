from celery import shared_task
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from integrations.telegram import send_message
from integrations.models import BranchTelegramLink
from pharmacy.models import PharmacyOrder, PharmacyOrderItem


@shared_task
def notify_new_pharmacy_order(order_id: int):
    order = (PharmacyOrder.objects
             .select_related("branch", "branch__pharmacy")
             .get(id=order_id))

    items = (PharmacyOrderItem.objects
             .select_related("drug")
             .filter(order=order)
             .order_by("id"))

    lines = []
    for i, it in enumerate(items, 1):
        lines.append(f"{i}) {it.drug.name_ru} × {it.qty} = {it.line_total} сом")

    created = timezone.localtime(order.created_at).strftime("%d.%m %H:%M")

    # ссылка на админку/страницу успеха (по желанию)
    site = getattr(settings, "SITE_URL", "").rstrip("/")
    success_url = ""
    if site:
        try:
            success_url = site + reverse("pharmacy:checkout_success", args=[order.branch_id, order.id])
        except Exception:
            success_url = ""

    text = (
        f"💊 <b>Новый заказ в аптеке</b>\n"
        f"🏥 <b>{order.branch.pharmacy.name_ru}</b>\n"
        f"📍 Филиал: <b>{order.branch.name_ru}</b>\n"
        f"📌 {order.branch.address}\n\n"
        f"👤 Клиент: {order.customer_name or '—'}\n"
        f"📞 Тел: {order.customer_phone or '—'}\n"
        f"🏠 Адрес: {order.delivery_address or '—'}\n"
        f"💬 Комментарий: {order.comment or '—'}\n"
        f"🕒 {created}\n\n"
        + "\n".join(lines) +
        f"\n\n💰 Итого: <b>{order.total_amount}</b> сом"
    )
    if success_url:
        text += f"\n\n🔗 {success_url}"

    links = (BranchTelegramLink.objects
             .select_related("recipient")
             .filter(branch=order.branch, notify_orders=True, recipient__is_active=True))

    for link in links:
        send_message(
            chat_id=link.recipient.chat_id,
            text=text,
            thread_id=link.recipient.thread_id,
        )