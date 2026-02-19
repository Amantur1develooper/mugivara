# shops/tasks.py
import re
import requests
from celery import shared_task
from django.conf import settings

from .models import StoreOrder


def _tg_token():
    # подхватит любой из вариантов, который ты используешь
    return getattr(settings, "TG_BOT_TOKEN", None) or getattr(settings, "TELEGRAM_BOT_TOKEN", None)


def _send_tg(chat_id, text: str, thread_id=None):
    token = _tg_token()
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if thread_id:
        payload["message_thread_id"] = thread_id

    try:
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass


def _money(x):
    try:
        return f"{x:.2f}"
    except Exception:
        return str(x)


@shared_task
def notify_new_shop_order(order_id: int):
    try:
        order = (
            StoreOrder.objects
            .select_related("branch", "branch__store")
            .prefetch_related("items__product")
            .get(pk=order_id)
        )
    except StoreOrder.DoesNotExist:
        return

    b = order.branch

    # определяем тип заказа (на случай если поля mode нет)
    mode = getattr(order, "mode", None) or getattr(order, "order_type", None) or ""
    is_delivery = (mode == "delivery") or bool(getattr(order, "address", ""))

    lines = []
    lines.append("🛒 Новый заказ (магазин)")
    lines.append(f"Заказ: #{order.id}")
    lines.append(f"Филиал: {getattr(b, 'name', '')}")
    lines.append(f"Тип: {'Доставка' if is_delivery else 'В магазине'}")

    if getattr(order, "phone", ""):
        lines.append(f"Телефон: {order.phone}")
    if getattr(order, "name", ""):
        lines.append(f"Имя: {order.name}")
    if is_delivery and getattr(order, "address", ""):
        lines.append(f"Адрес: {order.address}")
    if getattr(order, "comment", ""):
        lines.append(f"Комментарий: {order.comment}")

    lines.append("")
    lines.append("Состав:")

    for it in order.items.all():
        p = it.product
        pname = getattr(p, "name_ru", None) or getattr(p, "name", None) or str(p)

        line_total = getattr(it, "line_total", None)
        if line_total is None:
            # если line_total нет в модели — считаем сами
            line_total = (it.price or 0) * (it.qty or 0)

        lines.append(f"• {pname} × {it.qty} = {_money(line_total)} сом")

    if getattr(order, "total", None) is not None:
        lines.append("")
        lines.append(f"Итого: {_money(order.total)} сом")

    msg = "\n".join(lines)

    # У каждого магазина/филиала свои TG чаты (как ты хотел)
    if getattr(b, "tg_group_chat_id", None):
        _send_tg(b.tg_group_chat_id, msg, thread_id=getattr(b, "tg_thread_id", None))

    if getattr(b, "tg_manager_chat_id", None):
        _send_tg(b.tg_manager_chat_id, msg)
