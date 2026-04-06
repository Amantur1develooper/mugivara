from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.utils.html import escape
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


def _order_text(order: Order, title_override: str = None) -> str:
    lines = []
    lines.append(title_override if title_override else _order_header(order))
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

    # контакт
    if getattr(order, "customer_name", ""):
        lines.append(f"👤 Имя: {order.customer_name}")
    if getattr(order, "customer_phone", ""):
        lines.append(f"📞 Телефон: {order.customer_phone}")

    # адрес/стол (всегда показываем — там может быть номер стола)
    if getattr(order, "delivery_address", ""):
        label = "📍 Адрес" if order.type == Order.Type.DELIVERY else "🪑 Стол/место"
        lines.append(f"{label}: {order.delivery_address}")

    if getattr(order, "comment", ""):
        lines.append(f"📝 Комментарий: {order.comment}")

    # ── СОСТАВ ЗАКАЗА ─────────────────────────────────────────────────────────
    items = list(order.items.select_related("item").all())
    if items:
        lines.append("")
        lines.append("📋 Состав заказа:")
        for it in items:
            name = getattr(it.item, "name_ru", None) or str(it.item)
            qty = getattr(it, "qty", 1)
            lt = getattr(it, "line_total", None)
            if lt is not None:
                lines.append(f"  • {name} × {qty}  —  {_money(lt)}")
            else:
                lines.append(f"  • {name} × {qty}")
    else:
        lines.append("")
        lines.append("⚠️ Состав: нет позиций")

    if getattr(order, "total_amount", None) is not None:
        lines.append("")
        lines.append(f"💰 ИТОГО: {_money(order.total_amount)}")

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
# $mPx32u5

from celery import shared_task
from django.utils import timezone
from django.conf import settings
import requests

from reservations.models import Place
from integrations.models import TelegramRecipient

def _tg_send(chat_id: str, text: str, message_thread_id=None):
    if not getattr(settings, "TG_BOT_TOKEN", None):
        return
    url = f"https://api.telegram.org/bot{settings.TG_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    if message_thread_id:
        payload["message_thread_id"] = int(message_thread_id)
    requests.post(url, json=payload, timeout=10)

@shared_task
def notify_call_waiter(place_id: int, note: str = ""):
    place = Place.objects.select_related("floor__branch").get(id=place_id)
    branch = place.floor.branch

    # Кому отправлять: берем активных получателей филиала
    # (лучше тем, у кого включено notify_new_orders=True)
    recs = TelegramRecipient.objects.filter(
        branch=branch,
        is_active=True,
        notify_new_orders=True,
    )

    t = timezone.localtime().strftime("%d.%m.%Y %H:%M")
    text = (
        f"🔔 <b>Позвали официанта</b>\n"
        f"🏢 Филиал: <b>{branch.name_ru}</b>\n"
        f"🍽️ Место: <b>{place.title}</b>\n"
    )
    if note:
        text += f"💬 Комментарий: {note}\n"
    text += f"🕒 {t}"

    for r in recs:
        _tg_send(r.chat_id, text, r.message_thread_id)
