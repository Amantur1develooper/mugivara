from celery import shared_task
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

from integrations.models import TelegramRecipient
from integrations.telegram import send_message
from orders.models import Order


def _tg_token() -> str:
    return (getattr(settings, "TG_BOT_TOKEN", "") or getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


def _money(v) -> str:
    if v is None:
        return ""
    # красиво: 980 вместо 980.00
    try:
        v = Decimal(str(v))
        if v == v.to_integral():
            return f"{int(v)} сом"
        return f"{v.normalize()} сом"
    except Exception:
        return f"{v} сом"


def _thread_id_for(r: TelegramRecipient):
    # thread_id только для супергрупп с темами (-100...)
    chat_id = str(getattr(r, "chat_id", "") or "")
    if not chat_id.startswith("-100"):
        return None
    return getattr(r, "message_thread_id", None) or None


def _order_header(order: Order) -> str:
    # если есть стол — это заказ в зале
    if getattr(order, "table_place_id", None):
        return "🪑 НОВЫЙ ЗАКАЗ В ЗАВЕДЕНИИ"

    if order.type == Order.Type.DELIVERY:
        return "🛵 ДОСТАВКА — НОВЫЙ ЗАКАЗ"
    if order.type == Order.Type.PICKUP:
        return "🥡 САМОВЫВОЗ — НОВЫЙ ЗАКАЗ"
    if order.type == Order.Type.DINE_IN:
        return "🪑 НОВЫЙ ЗАКАЗ В ЗАВЕДЕНИИ"

    return "🔔 НОВЫЙ ЗАКАЗ"


def _order_text(order: Order) -> str:
    lines = []
    lines.append(_order_header(order))
    lines.append(f"🧾 Заказ №{order.id}")
    lines.append(f"🏪 Филиал: {getattr(order.branch, 'name_ru', str(order.branch))}")

    # тип/статус по-русски
    if hasattr(order, "get_type_display"):
        lines.append(f"📌 Тип: {order.get_type_display()}")
    if hasattr(order, "get_status_display"):
        lines.append(f"🆕 Статус: {order.get_status_display()}")

    # стол
    if getattr(order, "table_place_id", None) and getattr(order, "table_place", None):
        lines.append(f"🪑 Стол: {order.table_place.title}")

    # оплата
    pm = order.get_payment_method_display() if hasattr(order, "get_payment_method_display") else ""
    ps = order.get_payment_status_display() if hasattr(order, "get_payment_status_display") else ""
    if pm or ps:
        if pm and ps:
            lines.append(f"💳 Оплата: {pm} / {ps}")
        elif pm:
            lines.append(f"💳 Оплата: {pm}")
        else:
            lines.append(f"💳 Статус оплаты: {ps}")

    # контакт/адрес
    if getattr(order, "customer_phone", ""):
        lines.append(f"📞 Телефон: {order.customer_phone}")

    if order.type == Order.Type.DELIVERY and getattr(order, "delivery_address", ""):
        lines.append(f"📍 Адрес: {order.delivery_address}")

    if getattr(order, "comment", ""):
        lines.append(f"📝 Комментарий: {order.comment}")

    # позиции
    lines.append("")
    lines.append("🧾 Состав заказа:")
    for it in order.items.select_related("item").all():
        name = getattr(it.item, "name_ru", str(it.item))
        qty = getattr(it, "qty", 1)
        lt = getattr(it, "line_total", None)
        if lt is None:
            lines.append(f"• {name} × {qty}")
        else:
            lines.append(f"• {name} × {qty} — {_money(lt)}")

    if getattr(order, "total_amount", None) is not None:
        lines.append("")
        lines.append(f"💰 Итого: {_money(order.total_amount)}")

    created = timezone.localtime(order.created_at).strftime("%d.%m.%Y %H:%M")
    lines.append(f"⏰ {created}")

    return "\n".join(lines)


@shared_task
def notify_new_order(order_id: int):
    token = _tg_token()
    if not token:
        return "No TG token"

    order = (
        Order.objects
        .select_related("branch", "table_place")
        .prefetch_related("items__item")
        .get(id=order_id)
    )

    recipients = TelegramRecipient.objects.filter(
        branch=order.branch, is_active=True, notify_new_orders=True
    )
    if not recipients.exists():
        return "No recipients"

    text = _order_text(order)

    sent = 0
    for r in recipients:
        try:
            send_message(
                bot_token=token,
                chat_id=str(r.chat_id),
                text=text,
                parse_mode=None,  # ✅ теги не нужны
                message_thread_id=_thread_id_for(r),
            )
            sent += 1
        except Exception as e:
            print("TG ERROR:", r.chat_id, e)

    return f"sent={sent}"


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def notify_order_status(self, order_id: int, old_status: str, new_status: str):
    token = _tg_token()
    if not token:
        return "No TG_BOT_TOKEN/TELEGRAM_BOT_TOKEN"

    order = (
        Order.objects
        .select_related("branch", "table_place")
        .prefetch_related("items__item")
        .get(id=order_id)
    )

    recipients = TelegramRecipient.objects.filter(
        branch=order.branch, is_active=True, notify_status_changes=True
    )
    if not recipients.exists():
        return "No recipients"

    # Русский статус через get_status_display()
    title = f"🔄 <b>СТАТУС ИЗМЕНЁН</b>\n➡️ Было: <b>{escape(old_status)}</b>\n➡️ Стало: <b>{escape(new_status)}</b>"
    text = _order_text(order, title_override=title)

    sent = 0
    for r in recipients:
        try:
            send_message(
                bot_token=token,
                chat_id=str(r.chat_id),
                text=text,
                parse_mode="HTML",
                message_thread_id=_thread_id_for(r),
            )
            sent += 1
        except Exception as e:
            print("TG ERROR:", r.chat_id, e)

    return f"sent={sent}"
