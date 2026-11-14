# -*- coding: utf-8 -*-
"""Кнопки заказа магазина из Telegram и страница мини-приложения."""
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from integrations import tgbot

from . import tg
from .models import StoreOrder

log = logging.getLogger(__name__)

CARD_BUTTONS = {
    "new":       [["confirm", "✅ Подтвердить", True], ["cancel", "❌ Отменить", False]],
    "confirmed": [["done", "🏁 Выполнен", True], ["cancel", "❌ Отменить", False]],
    "done":      [["reopen", "↩️ Вернуть в новые", False, True]],
    "canceled":  [["reopen", "↩️ Вернуть в новые", False, True]],
}


def _order(ident):
    return (StoreOrder.objects
            .filter(id=ident)
            .select_related("branch")
            .prefetch_related("items__product", "constructor_items")
            .first())


def handle_callback(cq):
    """Нажали кнопку под заказом магазина."""
    _, action, raw_id = (cq.get("data") or "").split(":")

    order = _order(raw_id)
    if not order:
        tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
                   text="Заказ не найден", show_alert=True)
        return

    # Кнопку могли переслать в другой чат — меняем статус только из чатов,
    # которым этот заказ и отправляли.
    chat_id = str((cq.get("message") or {}).get("chat", {}).get("id", ""))
    allowed = set(tg.recipients(order.branch)) | set(order.tg_messages or {})
    if chat_id and chat_id not in allowed:
        tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
                   text="Этот заказ не из вашего чата", show_alert=True)
        return

    toast = tg.apply_action(order, action, actor=tgbot.actor_name(cq.get("from")))
    tgbot.call("answerCallbackQuery", callback_query_id=cq["id"],
               text=toast or "Не понял кнопку")


# ── мини-приложение ──────────────────────────────────────────────────────────

def _from_token(token):
    order_id = tg.unsign_order(token)
    return _order(order_id) if order_id else None


def card(request, token):
    order = _from_token(token)
    if not order:
        return render(request, "tg/card.html", {"expired": True}, status=404)

    is_delivery = order.mode == "delivery"
    rows = [("Тип", "Доставка" if is_delivery else "В магазине")]
    if order.name:
        rows.append(("Клиент", order.name))
    if order.phone and order.phone != "-":
        rows.append(("Телефон", order.phone))
    if order.address:
        rows.append(("Адрес" if is_delivery else "Комментарий", order.address))
    if order.comment:
        rows.append(("Комментарий", order.comment))
    rows.append(("Оплата", order.get_payment_method_display()))

    items = []
    for name, qty, total, extra in tg.items_of(order):
        label = f"{name} × {qty}"
        if extra:
            label += f" ({'; '.join(extra)})"
        items.append((label, total))

    return render(request, "tg/card.html", {
        "title": f"Заказ №{order.id}",
        "venue_name": getattr(order.branch, "name_ru", str(order.branch)),
        "status": order.status,
        "status_label": tg.STATUS_LABEL.get(order.status, order.status),
        "rows": rows,
        "items": items,
        "items_title": "Состав заказа",
        "total": order.total,
        "total_note": ("с доставкой" if order.delivery_fee and order.delivery_fee > 0 else ""),
        "phone": order.phone if order.phone != "-" else "",
        "action_url": reverse("shops_tg:card_action", args=[token]),
        "buttons_json": json.dumps(
            {} if order.mode == "in_store" else CARD_BUTTONS, ensure_ascii=False),
    })


@csrf_exempt
@require_POST
def card_action(request, token):
    order = _from_token(token)
    if not order:
        return JsonResponse({"ok": False, "error": "Ссылка устарела"}, status=404)

    user = tgbot.verify_init_data(request.POST.get("init_data", ""))
    if user is None:
        if not settings.DEBUG:
            return JsonResponse(
                {"ok": False, "error": "Откройте карточку кнопкой в Telegram"}, status=403)
        user = {}

    toast = tg.apply_action(order, request.POST.get("action", ""),
                            actor=tgbot.actor_name(user))
    if toast is None:
        return JsonResponse({"ok": False, "error": "Неизвестное действие"}, status=400)
    return JsonResponse({"ok": True, "toast": toast, "status": order.status,
                         "status_label": tg.STATUS_LABEL.get(order.status, order.status)})
