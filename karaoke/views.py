import json
import requests
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import (KaraokeVenue, KaraokeRoom, KaraokeBooking,
                     KaraokeMenuCategory, KaraokeMenuItem,
                     KaraokeOrder, KaraokeOrderItem)


def karaoke_list(request):
    venues = KaraokeVenue.objects.filter(is_active=True)
    return render(request, "karaoke/list.html", {"venues": venues})


def karaoke_detail(request, slug):
    venue = get_object_or_404(KaraokeVenue, slug=slug, is_active=True)
    categories = venue.room_categories.prefetch_related("rooms__photos").all()
    uncategorized = venue.rooms.filter(is_active=True, category__isnull=True).prefetch_related("photos")
    menu_cats = venue.menu_categories.prefetch_related("items").all()
    return render(request, "karaoke/detail.html", {
        "venue": venue,
        "categories": categories,
        "uncategorized": uncategorized,
        "menu_cats": menu_cats,
    })


def karaoke_menu(request, slug):
    venue = get_object_or_404(KaraokeVenue, slug=slug, is_active=True)
    menu_cats = venue.menu_categories.prefetch_related("items").all()
    return render(request, "karaoke/menu.html", {"venue": venue, "menu_cats": menu_cats})


def karaoke_slots(request, slug):
    """AJAX: возвращает занятые слоты для комнаты на дату."""
    venue = get_object_or_404(KaraokeVenue, slug=slug, is_active=True)
    room_id = request.GET.get("room")
    date_str = request.GET.get("date")
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        room = get_object_or_404(KaraokeRoom, id=room_id, venue=venue)
    except Exception:
        return JsonResponse({"ok": False, "slots": []})

    bookings = KaraokeBooking.objects.filter(
        room=room, booking_date=d
    ).exclude(status="cancelled").values("start_time", "end_time", "status")

    slots = [
        {"start": str(b["start_time"])[:5], "end": str(b["end_time"])[:5], "status": b["status"]}
        for b in bookings
    ]
    return JsonResponse({"ok": True, "slots": slots})


@require_POST
def karaoke_book(request, slug, room_id):
    venue = get_object_or_404(KaraokeVenue, slug=slug, is_active=True)
    room  = get_object_or_404(KaraokeRoom, id=room_id, venue=venue, is_active=True)

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    customer_name  = (data.get("name") or "").strip()
    customer_phone = (data.get("phone") or "").strip()
    booking_date   = (data.get("date") or "").strip()
    start_time     = (data.get("start") or "").strip()
    end_time       = (data.get("end") or "").strip()
    guests         = data.get("guests") or 1
    notes          = (data.get("notes") or "").strip()

    if not all([customer_name, customer_phone, booking_date, start_time, end_time]):
        return JsonResponse({"ok": False, "error": "Заполните все обязательные поля"}, status=400)

    try:
        bd = datetime.strptime(booking_date, "%Y-%m-%d").date()
        st = datetime.strptime(start_time, "%H:%M").time()
        et = datetime.strptime(end_time, "%H:%M").time()
    except ValueError:
        return JsonResponse({"ok": False, "error": "Неверный формат даты/времени"}, status=400)

    if st >= et:
        return JsonResponse({"ok": False, "error": "Время окончания должно быть позже начала"}, status=400)

    # Проверка конфликтов
    conflict = KaraokeBooking.objects.filter(
        room=room, booking_date=bd
    ).exclude(status="cancelled").filter(
        start_time__lt=et, end_time__gt=st
    ).exists()
    if conflict:
        return JsonResponse({"ok": False, "error": "Это время уже занято. Выберите другое."}, status=409)

    booking = KaraokeBooking.objects.create(
        venue=venue, room=room,
        customer_name=customer_name, customer_phone=customer_phone,
        booking_date=bd, start_time=st, end_time=et,
        guests=int(guests), notes=notes, status="pending",
    )

    # ── Telegram ──────────────────────────────────────────────────────────────
    token   = (getattr(settings, "TG_BOT_TOKEN", "") or getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = venue.tg_chat_id.strip()
    if token and chat_id:
        t = timezone.localtime().strftime("%d.%m.%Y %H:%M")
        lines = [
            "🎤 <b>НОВОЕ БРОНИРОВАНИЕ — Karaoke</b>",
            "",
            f"🏢 <b>{escape(venue.name)}</b>",
            f"🚪 Кабинка: <b>{escape(room.name)}</b>",
            "",
            f"📅 Дата: <b>{bd.strftime('%d.%m.%Y')}</b>",
            f"⏰ Время: <b>{start_time} – {end_time}</b>",
            f"👥 Гостей: <b>{guests}</b>",
            "",
            f"👤 Имя: <b>{escape(customer_name)}</b>",
            f"📞 Телефон: {escape(customer_phone)}",
        ]
        if notes:
            lines += ["", f"💬 Примечание: {escape(notes)}"]
        lines += ["", f"⏱ {t}"]
        payload = {"chat_id": chat_id, "text": "\n".join(lines), "parse_mode": "HTML"}
        if venue.tg_thread_id:
            payload["message_thread_id"] = venue.tg_thread_id
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json=payload, timeout=8)
        except Exception as e:
            print("Karaoke TG error:", e)

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    wa = venue.whatsapp.strip()
    wa_url = None
    if wa:
        msg = (
            f"🎤 Новое бронирование!\n"
            f"Заведение: {venue.name}\n"
            f"Кабинка: {room.name}\n"
            f"Дата: {bd.strftime('%d.%m.%Y')}\n"
            f"Время: {start_time} – {end_time}\n"
            f"Гостей: {guests}\n"
            f"Имя: {customer_name}\n"
            f"Телефон: {customer_phone}"
        )
        if notes:
            msg += f"\nПримечание: {notes}"
        import urllib.parse
        wa_url = f"https://wa.me/{wa}?text={urllib.parse.quote(msg)}"

    return JsonResponse({"ok": True, "booking_id": booking.id, "wa_url": wa_url})


@require_POST
def karaoke_menu_order(request, slug):
    """Принимает заказ из публичного меню, сохраняет и шлёт в TG."""
    venue = get_object_or_404(KaraokeVenue, slug=slug, is_active=True)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"ok": False, "error": "bad json"}, status=400)

    items_data = data.get("items", [])   # [{id, name, price, qty}, ...]
    room_name  = (data.get("room") or "").strip()
    phone      = (data.get("phone") or "").strip()
    comment    = (data.get("comment") or "").strip()

    if not items_data:
        return JsonResponse({"ok": False, "error": "empty"}, status=400)

    # ── Сохранить заказ ──────────────────────────────────────────────────────
    order = KaraokeOrder.objects.create(
        venue=venue,
        order_date=date.today(),
        comment=comment,
    )
    total = Decimal("0")
    for it in items_data:
        try:
            menu_item = KaraokeMenuItem.objects.get(id=int(it["id"]), venue=venue, is_active=True)
            qty = max(1, int(it.get("qty", 1)))
            oi = KaraokeOrderItem(order=order, menu_item=menu_item, qty=qty,
                                  price_snapshot=menu_item.price)
            oi.save()
            total += oi.line_total
        except Exception:
            continue
    order.total_amount = total
    order.save(update_fields=["total_amount"])

    # ── Telegram ─────────────────────────────────────────────────────────────
    try:
        token   = (getattr(settings, "TG_BOT_TOKEN", "") or
                   getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        chat_id = (venue.tg_chat_id or "").strip()
        if token and chat_id:
            lines = [
                "🍽️ <b>ЗАКАЗ ЕДЫ — QR-меню</b>",
                "",
                f"🏢 <b>{escape(venue.name)}</b>",
            ]
            if room_name:
                lines.append(f"🚪 Кабинка: <b>{escape(room_name)}</b>")
            if phone:
                lines.append(f"📞 Телефон: {escape(phone)}")
            lines.append("")
            for oi in order.items.select_related("menu_item").all():
                lines.append(
                    f"  • {escape(oi.menu_item.name)} × {oi.qty} = {int(oi.line_total)} сом"
                )
            lines += ["", f"💰 Итого: <b>{int(total)} сом</b>"]
            if comment:
                lines += ["", f"💬 {escape(comment)}"]
            payload = {
                "chat_id": chat_id,
                "text": "\n".join(lines),
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            if venue.tg_thread_id:
                payload["message_thread_id"] = venue.tg_thread_id
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload, timeout=8,
            )
    except Exception as e:
        print(f"[TG menu_order] {e}")

    return JsonResponse({"ok": True, "id": order.id, "total": str(total)})
