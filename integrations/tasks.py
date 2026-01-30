# from celery import shared_task
# from django.conf import settings
# from django.utils import timezone
from celery import shared_task
# from orders.models import Order
# from integrations.models import TelegramRecipient
# from integrations.telegram import send_message

# def _order_text(order: Order, title: str) -> str:
#     lines = []
#     lines.append(f"<b>{title}</b>")
#     lines.append(f"Филиал: <b>{order.branch.name}</b>")
#     lines.append(f"Тип: <b>{order.type}</b>")
#     lines.append(f"Статус: <b>{order.status}</b>")
#     lines.append(f"Оплата: <b>{order.payment_method}</b> / <b>{order.payment_status}</b>")
#     if order.customer_name or order.customer_phone:
#         lines.append(f"Клиент: <b>{order.customer_name}</b> {order.customer_phone}")
#     if order.delivery_address:
#         lines.append(f"Адрес: <b>{order.delivery_address}</b>")
#     if order.comment:
#         lines.append(f"Комментарий: {order.comment}")

#     # позиции
#     lines.append("")
#     lines.append("<b>Состав:</b>")
#     for it in order.items.select_related("item").all():
#         lines.append(f"• {it.item.name} × {it.qty} = {it.line_total}")

#     lines.append("")
#     lines.append(f"<b>Итого:</b> {order.total_amount}")
#     lines.append(f"<i>{timezone.localtime(order.created_at).strftime('%d.%m.%Y %H:%M')}</i>")
#     return "\n".join(lines)

# @shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
# def notify_new_order(self, order_id: int):
#     token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
#     if not token:
#         return "No TELEGRAM_BOT_TOKEN"

#     order = Order.objects.select_related("branch").prefetch_related("items__item").get(id=order_id)

#     recipients = TelegramRecipient.objects.filter(branch=order.branch, is_active=True)
#     if not recipients.exists():
#         return "No recipients"

#     text = _order_text(order, "🧾 Новый заказ")

#     sent = 0
#     for r in recipients:
#         try:
#             send_message(token, r.chat_id, text, message_thread_id=r.message_thread_id)
#             sent += 1
#         except Exception:
#             # не падаем на одном чате, продолжаем
#             continue
#     return f"sent={sent}"

# @shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
# def notify_order_status(self, order_id: int, old_status: str, new_status: str):
#     token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
#     if not token:
#         return "No TELEGRAM_BOT_TOKEN"

#     order = Order.objects.select_related("branch").prefetch_related("items__item").get(id=order_id)
#     recipients = TelegramRecipient.objects.filter(branch=order.branch, is_active=True)
#     if not recipients.exists():
#         return "No recipients"

#     text = _order_text(order, f"🔄 Статус заказа изменён: {old_status} → {new_status}")

#     sent = 0
#     for r in recipients:
#         try:
#             send_message(token, r.chat_id, text, message_thread_id=r.message_thread_id)
#             sent += 1
#         except Exception:
#             continue
#     return f"sent={sent}"
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from integrations.models import TelegramRecipient
from integrations.telegram import send_message

# ⚠️ проверь путь к модели Order в твоём проекте:
from orders.models import Order  # если у тебя другое приложение — замени

def _order_text(order: Order, title: str) -> str:
    lines = []
    lines.append(f"{title}")
    lines.append(f"Заказ: #{order.id}")
    lines.append(f"Филиал: {order.branch.name_ru}")
    lines.append(f"Тип: {order.type}")
    lines.append(f"Статус: {order.status}")

    # если поля есть — выведем
    pm = getattr(order, "payment_method", None)
    ps = getattr(order, "payment_status", None)
    if pm or ps:
        lines.append(f"Оплата: {pm} / {ps}")

    customer_phone = getattr(order, "customer_phone", "")
    if customer_phone:
        lines.append(f"Телефон: {customer_phone}")

    delivery_address = getattr(order, "delivery_address", "")
    if delivery_address:
        lines.append(f"Адрес: {delivery_address}")

    comment = getattr(order, "comment", "")
    if comment:
        lines.append(f"Комментарий: {comment}")

    # позиции
    lines.append("")
    lines.append("<b>Состав:</b>")
    # ожидаем related_name="items" и item FK внутри OrderItem
    for it in order.items.select_related("item").all():
        name = getattr(it.item, "name_ru", str(it.item))
        qty = getattr(it, "qty", 1)
        line_total = getattr(it, "line_total", None)
        if line_total is None:
            # если нет line_total — хотя бы qty
            lines.append(f"• {name} × {qty}")
        else:
            lines.append(f"• {name} × {qty} = {line_total}")

    total_amount = getattr(order, "total_amount", None)
    if total_amount is not None:
        lines.append("")
        lines.append(f"<b>Итого:</b> {total_amount}")

    lines.append(f"<i>{timezone.localtime(order.created_at).strftime('%d.%m.%Y %H:%M')}</i>")
    return "\n".join(lines)


@shared_task
def notify_new_order(order_id: int):
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    if not token:
        return "No TELEGRAM_BOT_TOKEN"

    order = (
        Order.objects.select_related("branch")
        .prefetch_related("items__item")
        .get(id=order_id)
    )

    recipients = TelegramRecipient.objects.filter(
        branch=order.branch, is_active=True, notify_new_orders=True
    )
    if not recipients.exists():
        return "No recipients"

    text = _order_text(order, "🧾 Новый заказ")

    sent = 0
    for r in recipients:
        try:
            send_message(token, r.chat_id, text, parse_mode=None, message_thread_id=r.message_thread_id)

            # send_message(token, r.chat_id, text, message_thread_id=r.message_thread_id)
            sent += 1
        except Exception as e:
            print("TG ERROR:", r.chat_id, e)
            # continue
    return f"sent={sent}"

@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def notify_order_status(self, order_id: int, old_status: str, new_status: str):


    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    if not token:
        return "No TELEGRAM_BOT_TOKEN"

    order = (
        Order.objects.select_related("branch")
        .prefetch_related("items__item")
        .get(id=order_id)
    )

    recipients = TelegramRecipient.objects.filter(
        branch=order.branch, is_active=True, notify_status_changes=True
    )
    if not recipients.exists():
        return "No recipients"

    text = _order_text(order, f"🔄 Статус изменён: {old_status} → {new_status}")

    sent = 0
    for r in recipients:
        try:
            send_message(token, r.chat_id, text, message_thread_id=r.message_thread_id)
            sent += 1
        except Exception:
            continue
    return f"sent={sent}"
