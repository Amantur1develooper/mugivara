from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.utils.html import escape

from integrations.models import TelegramRecipient
from integrations.telegram import send_message
from orders.models import Order


def _tg_token() -> str:
    # чтобы работало и с TG_BOT_TOKEN, и с TELEGRAM_BOT_TOKEN
    return (getattr(settings, "TG_BOT_TOKEN", "") or getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


def _kind_header(order: Order) -> str:
    """
    🛵🚚 Доставка (онлайн)
    🪑🍽️ Стол (в заведении)
    🥡 Самовывоз
    """
    # если заказ привязан к столу — считаем "стол" (даже если вдруг тип не тот)
    if getattr(order, "table_place_id", None):
        return "🪑🍽️ <b>НОВЫЙ ЗАКАЗ СО СТОЛА</b>"

    if order.type == Order.Type.DELIVERY:
        return "🛵🚚 <b>НОВЫЙ ЗАКАЗ: ДОСТАВКА (онлайн)</b>"

    if order.type == Order.Type.PICKUP:
        return "🥡 <b>НОВЫЙ ЗАКАЗ: САМОВЫВОЗ</b>"

    # DINE_IN без конкретного стола (на всякий)
    return "🍽️ <b>НОВЫЙ ЗАКАЗ: В ЗАВЕДЕНИИ</b>"


def _status_icon(order: Order) -> str:
    m = {
        Order.Status.NEW: "🆕",
        Order.Status.ACCEPTED: "✅",
        Order.Status.COOKING: "👨‍🍳",
        Order.Status.READY: "🍽️",
        Order.Status.CLOSED: "🏁",
        Order.Status.CANCELLED: "❌",
    }
    return m.get(order.status, "🔔")


def _money(v) -> str:
    try:
        return f"{v:.0f} сом"
    except Exception:
        return f"{v} сом"


def _order_text(order: Order, title_override: str | None = None) -> str:
    # безопасно для HTML
    branch_name = escape(getattr(order.branch, "name_ru", str(order.branch)))
    branch_addr = escape(getattr(order.branch, "address", "") or "")
    created = timezone.localtime(order.created_at).strftime("%d.%m.%Y %H:%M")

    header = title_override or _kind_header(order)
    status_line = f"{_status_icon(order)} <b>Статус:</b> {escape(order.get_status_display())}"

    lines = []
    lines.append(header)
    lines.append(f"🧾 <b>Заказ №</b> <code>{order.id}</code>")
    lines.append(f"🏪 <b>Филиал:</b> {branch_name}" + (f"\n📍 <b>Адрес:</b> {branch_addr}" if branch_addr else ""))
    lines.append(status_line)

    # Стол
    if getattr(order, "table_place_id", None) and getattr(order, "table_place", None):
        table_title = escape(getattr(order.table_place, "title", "Стол"))
        lines.append(f"🪑 <b>Стол:</b> {table_title}")

    # Клиент
    cn = escape(getattr(order, "customer_name", "") or "")
    cp = escape(getattr(order, "customer_phone", "") or "")
    if cn:
        lines.append(f"👤 <b>Имя:</b> {cn}")
    if cp:
        lines.append(f"📞 <b>Телефон:</b> {cp}")

    # Доставка
    addr = escape(getattr(order, "delivery_address", "") or "")
    if order.type == Order.Type.DELIVERY and addr:
        lines.append(f"📦 <b>Доставка куда:</b> {addr}")

    # Оплата
    pm = escape(getattr(order, "get_payment_method_display", lambda: "")() or "")
    ps = escape(getattr(order, "get_payment_status_display", lambda: "")() or "")
    if pm or ps:
        if pm and ps:
            lines.append(f"💳 <b>Оплата:</b> {pm} · {ps}")
        elif pm:
            lines.append(f"💳 <b>Оплата:</b> {pm}")
        else:
            lines.append(f"💳 <b>Статус оплаты:</b> {ps}")

    # Коммент
    comment = escape(getattr(order, "comment", "") or "")
    if comment:
        lines.append(f"📝 <b>Комментарий:</b> {comment}")

    # позиции
    lines.append("")
    lines.append("🧾 <b>Состав заказа:</b>")

    # items__item уже prefetch в query
    for it in order.items.select_related("item").all():
        name = escape(getattr(it.item, "name_ru", str(it.item)))
        qty = getattr(it, "qty", 1)
        lt = getattr(it, "line_total", None)
        if lt is None:
            lines.append(f"• {name} × {qty}")
        else:
            lines.append(f"• {name} × {qty} — <b>{_money(lt)}</b>")

    total = getattr(order, "total_amount", None)
    if total is not None:
        lines.append("")
        lines.append(f"💰 <b>ИТОГО:</b> <b>{_money(total)}</b>")

    lines.append("")
    lines.append(f"⏰ <i>{created}</i>")

    return "\n".join(lines)


def _thread_id_for(recipient: TelegramRecipient):
    """
    message_thread_id нужно ТОЛЬКО для тем (topics) в супергруппах.
    Для лички/обычных групп — ставим None.
    """
    kind = (getattr(recipient, "kind", "") or "").lower()
    chat_id = str(getattr(recipient, "chat_id", "") or "")

    # если chat_id не супергруппа (-100...), то thread не нужен
    if not chat_id.startswith("-100"):
        return None

    # для супергруппы может быть тема
    return getattr(recipient, "message_thread_id", None) or None


@shared_task
def notify_new_order(order_id: int):
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
                parse_mode="HTML",
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
