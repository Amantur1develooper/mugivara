import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages

from django.db.models import Sum, Count
from .models import (KaraokeVenue, RoomCategory, KaraokeRoom, KaraokeRoomPhoto,
                     KaraokeBooking, KaraokeMenuCategory, KaraokeMenuItem, KaraokeMembership,
                     KaraokeOrder, KaraokeOrderItem)

LOGIN_URL = "dashboard:login"


def _user_venues(user):
    if user.is_staff or user.is_superuser:
        return KaraokeVenue.objects.all()
    ids = KaraokeMembership.objects.filter(user=user).values_list("venue_id", flat=True)
    return KaraokeVenue.objects.filter(id__in=ids)


def _check_access(user, venue):
    if user.is_staff or user.is_superuser:
        return True
    return KaraokeMembership.objects.filter(user=user, venue=venue).exists()


# ── ГЛАВНАЯ ──────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def karaoke_home(request):
    venues = _user_venues(request.user).prefetch_related("rooms")
    return render(request, "dashboard/karaoke/home.html", {"venues": venues})


# ── НАСТРОЙКИ ЗАВЕДЕНИЯ ───────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def karaoke_venue_edit(request, venue_id):
    venue = get_object_or_404(KaraokeVenue, id=venue_id)
    if not _check_access(request.user, venue):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:karaoke_home")

    if request.method == "POST":
        for field in ["name", "tagline", "description", "address", "phone",
                      "whatsapp", "working_hours", "map_url", "tg_chat_id"]:
            setattr(venue, field, request.POST.get(field, "").strip())
        tg_thread = request.POST.get("tg_thread_id", "").strip()
        venue.tg_thread_id = int(tg_thread) if tg_thread.isdigit() else None
        if "logo" in request.FILES:
            venue.logo = request.FILES["logo"]
        elif request.POST.get("logo_clear"):
            venue.logo = None
        if "cover" in request.FILES:
            venue.cover = request.FILES["cover"]
        elif request.POST.get("cover_clear"):
            venue.cover = None
        venue.save()
        messages.success(request, "Данные заведения обновлены.")
        return redirect("dashboard:karaoke_venue_edit", venue_id=venue.id)

    return render(request, "dashboard/karaoke/venue_edit.html", {"venue": venue})


# ── КАБИНКИ ───────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def karaoke_rooms(request, venue_id):
    venue = get_object_or_404(KaraokeVenue, id=venue_id)
    if not _check_access(request.user, venue):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:karaoke_home")
    categories = venue.room_categories.prefetch_related("rooms__photos").all()
    uncategorized = venue.rooms.filter(category__isnull=True).prefetch_related("photos")
    return render(request, "dashboard/karaoke/rooms.html", {
        "venue": venue, "categories": categories, "uncategorized": uncategorized,
    })


@login_required(login_url=LOGIN_URL)
def karaoke_room_add(request, venue_id):
    venue = get_object_or_404(KaraokeVenue, id=venue_id)
    if not _check_access(request.user, venue):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:karaoke_home")

    if request.method == "POST":
        room = KaraokeRoom(venue=venue)
        room.name = request.POST.get("name", "").strip()
        room.description = request.POST.get("description", "").strip()
        room.capacity = request.POST.get("capacity") or 6
        room.price_per_hour = request.POST.get("price_per_hour") or 0
        room.sort_order = request.POST.get("sort_order") or 0
        cat_id = request.POST.get("category_id")
        if cat_id and cat_id.isdigit():
            room.category_id = int(cat_id)
        if not room.name:
            messages.error(request, "Введите название кабинки.")
        else:
            room.save()
            # Фотографии (до 5)
            for f in request.FILES.getlist("photos")[:5]:
                KaraokeRoomPhoto.objects.create(room=room, photo=f)
            messages.success(request, f"Кабинка «{room.name}» добавлена.")
            return redirect("dashboard:karaoke_rooms", venue_id=venue.id)

    categories = venue.room_categories.all()
    return render(request, "dashboard/karaoke/room_form.html",
                  {"venue": venue, "room": None, "categories": categories})


@login_required(login_url=LOGIN_URL)
def karaoke_room_edit(request, room_id):
    room = get_object_or_404(KaraokeRoom, id=room_id)
    venue = room.venue
    if not _check_access(request.user, venue):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:karaoke_home")

    if request.method == "POST":
        room.name = request.POST.get("name", room.name).strip()
        room.description = request.POST.get("description", "").strip()
        room.capacity = request.POST.get("capacity") or room.capacity
        room.price_per_hour = request.POST.get("price_per_hour") or room.price_per_hour
        room.sort_order = request.POST.get("sort_order") or 0
        cat_id = request.POST.get("category_id")
        room.category_id = int(cat_id) if cat_id and cat_id.isdigit() else None
        room.save()

        # Удаление выбранных фото
        for pid in request.POST.getlist("delete_photo"):
            KaraokeRoomPhoto.objects.filter(id=pid, room=room).delete()

        # Добавить новые фото (до 5 итого)
        existing = room.photos.count()
        slots = max(0, 5 - existing)
        for f in request.FILES.getlist("photos")[:slots]:
            KaraokeRoomPhoto.objects.create(room=room, photo=f)

        messages.success(request, f"Кабинка «{room.name}» обновлена.")
        return redirect("dashboard:karaoke_rooms", venue_id=venue.id)

    categories = venue.room_categories.all()
    return render(request, "dashboard/karaoke/room_form.html",
                  {"venue": venue, "room": room, "categories": categories})


@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_room_toggle(request, room_id):
    room = get_object_or_404(KaraokeRoom, id=room_id)
    if not _check_access(request.user, room.venue):
        return JsonResponse({"ok": False}, status=403)
    room.is_active = not room.is_active
    room.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": room.is_active})


@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_room_delete(request, room_id):
    room = get_object_or_404(KaraokeRoom, id=room_id)
    venue_id = room.venue_id
    if not _check_access(request.user, room.venue):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:karaoke_home")
    room.delete()
    messages.success(request, "Кабинка удалена.")
    return redirect("dashboard:karaoke_rooms", venue_id=venue_id)


# ── КАТЕГОРИИ КАБИНОК ─────────────────────────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_cat_add(request, venue_id):
    venue = get_object_or_404(KaraokeVenue, id=venue_id)
    if not _check_access(request.user, venue):
        return JsonResponse({"ok": False}, status=403)
    name = (request.POST.get("name") or "").strip()
    if not name:
        return JsonResponse({"ok": False, "error": "Введите название"}, status=400)
    cat = RoomCategory.objects.create(venue=venue, name=name)
    return JsonResponse({"ok": True, "id": cat.id, "name": cat.name})


@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_cat_delete(request, cat_id):
    cat = get_object_or_404(RoomCategory, id=cat_id)
    if not _check_access(request.user, cat.venue):
        return JsonResponse({"ok": False}, status=403)
    cat.delete()
    return JsonResponse({"ok": True})


# ── ШАХМАТКА (бронирования) ───────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def karaoke_chess(request, venue_id):
    venue = get_object_or_404(KaraokeVenue, id=venue_id)
    if not _check_access(request.user, venue):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:karaoke_home")

    today = date.today()
    date_str = request.GET.get("date", today.isoformat())
    try:
        view_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        view_date = today

    rooms = venue.rooms.filter(is_active=True)
    bookings = KaraokeBooking.objects.filter(
        venue=venue, booking_date=view_date
    ).exclude(status="cancelled").select_related("room")

    # Слоты с 09:00 до 03:00 (+1 день) с шагом 1 час
    hours = list(range(9, 24)) + [0, 1, 2, 3]
    slots = [f"{h:02d}:00" for h in hours]

    # Маппинг room_id → список занятых слотов
    booked = {}
    for b in bookings:
        rid = b.room_id
        if rid not in booked:
            booked[rid] = []
        booked[rid].append(b)

    return render(request, "dashboard/karaoke/chess.html", {
        "venue": venue,
        "rooms": rooms,
        "bookings": bookings,
        "booked": booked,
        "slots": slots,
        "view_date": view_date,
        "prev_date": (view_date - timedelta(days=1)).isoformat(),
        "next_date": (view_date + timedelta(days=1)).isoformat(),
        "today": today,
    })


# ── БРОНИРОВАНИЕ (создание из дашборда) ──────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_booking_add(request, venue_id):
    venue = get_object_or_404(KaraokeVenue, id=venue_id)
    if not _check_access(request.user, venue):
        return JsonResponse({"ok": False}, status=403)

    room_id = request.POST.get("room_id")
    room = get_object_or_404(KaraokeRoom, id=room_id, venue=venue)
    customer_name  = request.POST.get("name", "").strip()
    customer_phone = request.POST.get("phone", "").strip()
    booking_date   = request.POST.get("date", "").strip()
    start_time     = request.POST.get("start", "").strip()
    end_time       = request.POST.get("end", "").strip()
    guests         = request.POST.get("guests") or 1
    notes          = request.POST.get("notes", "").strip()

    try:
        bd = datetime.strptime(booking_date, "%Y-%m-%d").date()
        st = datetime.strptime(start_time, "%H:%M").time()
        et = datetime.strptime(end_time, "%H:%M").time()
    except Exception:
        return JsonResponse({"ok": False, "error": "Неверная дата/время"}, status=400)

    conflict = KaraokeBooking.objects.filter(
        room=room, booking_date=bd
    ).exclude(status="cancelled").filter(
        start_time__lt=et, end_time__gt=st
    ).exists()
    if conflict:
        return JsonResponse({"ok": False, "error": "Время занято"}, status=409)

    b = KaraokeBooking.objects.create(
        venue=venue, room=room,
        customer_name=customer_name, customer_phone=customer_phone,
        booking_date=bd, start_time=st, end_time=et,
        guests=int(guests), notes=notes, status="confirmed",
    )
    return JsonResponse({"ok": True, "id": b.id})


@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_booking_status(request, booking_id):
    booking = get_object_or_404(KaraokeBooking, id=booking_id)
    if not _check_access(request.user, booking.venue):
        return JsonResponse({"ok": False}, status=403)
    status = request.POST.get("status")
    if status in dict(KaraokeBooking._meta.get_field("status").choices):
        booking.status = status
        booking.save(update_fields=["status"])
    return JsonResponse({"ok": True, "status": booking.status})


@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_booking_delete(request, booking_id):
    booking = get_object_or_404(KaraokeBooking, id=booking_id)
    if not _check_access(request.user, booking.venue):
        return JsonResponse({"ok": False}, status=403)
    booking.delete()
    return JsonResponse({"ok": True})


# ── МЕНЮ (управление) ─────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def karaoke_menu_manage(request, venue_id):
    venue = get_object_or_404(KaraokeVenue, id=venue_id)
    if not _check_access(request.user, venue):
        messages.error(request, "Нет доступа.")
        return redirect("dashboard:karaoke_home")
    cats = venue.menu_categories.prefetch_related("items").all()
    return render(request, "dashboard/karaoke/menu.html", {"venue": venue, "cats": cats})


@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_menu_cat_add(request, venue_id):
    venue = get_object_or_404(KaraokeVenue, id=venue_id)
    if not _check_access(request.user, venue):
        return JsonResponse({"ok": False}, status=403)
    name = (request.POST.get("name") or "").strip()
    if not name:
        return JsonResponse({"ok": False}, status=400)
    cat = KaraokeMenuCategory.objects.create(venue=venue, name=name)
    return JsonResponse({"ok": True, "id": cat.id, "name": cat.name})


@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_menu_item_add(request, venue_id):
    venue = get_object_or_404(KaraokeVenue, id=venue_id)
    if not _check_access(request.user, venue):
        return JsonResponse({"ok": False}, status=403)
    item = KaraokeMenuItem(venue=venue)
    item.name = (request.POST.get("name") or "").strip()
    item.price = request.POST.get("price") or 0
    item.cost_price = request.POST.get("cost_price") or 0
    cat_id = request.POST.get("cat_id")
    item.category_id = int(cat_id) if cat_id and cat_id.isdigit() else None
    if "photo" in request.FILES:
        item.photo = request.FILES["photo"]
    if not item.name:
        return JsonResponse({"ok": False, "error": "Введите название"}, status=400)
    item.save()
    photo_url = item.photo.url if item.photo else ""
    return JsonResponse({"ok": True, "id": item.id, "name": item.name,
                         "price": str(item.price), "cost_price": str(item.cost_price),
                         "photo": photo_url})


@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_menu_item_delete(request, item_id):
    item = get_object_or_404(KaraokeMenuItem, id=item_id)
    if not _check_access(request.user, item.venue):
        return JsonResponse({"ok": False}, status=403)
    item.delete()
    return JsonResponse({"ok": True})


@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_menu_item_toggle(request, item_id):
    item = get_object_or_404(KaraokeMenuItem, id=item_id)
    if not _check_access(request.user, item.venue):
        return JsonResponse({"ok": False}, status=403)
    item.is_active = not item.is_active
    item.save(update_fields=["is_active"])
    return JsonResponse({"ok": True, "is_active": item.is_active})


@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_menu_item_update(request, item_id):
    """Update price, cost_price and/or photo inline."""
    item = get_object_or_404(KaraokeMenuItem, id=item_id)
    if not _check_access(request.user, item.venue):
        return JsonResponse({"ok": False}, status=403)

    fields = []
    if "price" in request.POST:
        try:
            item.price = int(request.POST["price"] or 0)
            fields.append("price")
        except (ValueError, TypeError):
            pass
    if "cost_price" in request.POST:
        try:
            item.cost_price = int(request.POST["cost_price"] or 0)
            fields.append("cost_price")
        except (ValueError, TypeError):
            pass
    if "photo" in request.FILES:
        item.photo = request.FILES["photo"]
        fields.append("photo")
    if request.POST.get("remove_photo") == "1" and item.photo:
        item.photo.delete(save=False)
        item.photo = None
        fields.append("photo")

    if fields:
        item.save(update_fields=fields)

    margin = int(item.price) - int(item.cost_price)
    pct = round(margin / int(item.price) * 100) if item.price else 0
    return JsonResponse({
        "ok": True,
        "price": str(item.price),
        "cost_price": str(item.cost_price),
        "margin": margin,
        "margin_pct": pct,
        "photo_url": item.photo.url if item.photo else "",
    })


# ── ОТЧЁТ ─────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def karaoke_report(request, venue_id):
    venue = get_object_or_404(KaraokeVenue, id=venue_id)
    if not _check_access(request.user, venue):
        return redirect("dashboard:karaoke_home")

    today = date.today()

    # Period from GET params
    period = request.GET.get("period", "week")
    date_from_str = request.GET.get("date_from", "")
    date_to_str   = request.GET.get("date_to", "")

    if period == "today":
        date_from = date_to = today
    elif period == "month":
        date_from = today.replace(day=1)
        date_to   = today
    elif period == "custom" and date_from_str and date_to_str:
        try:
            date_from = datetime.strptime(date_from_str, "%Y-%m-%d").date()
            date_to   = datetime.strptime(date_to_str,   "%Y-%m-%d").date()
        except ValueError:
            date_from = today - timedelta(days=6)
            date_to   = today
    else:  # week default
        period    = "week"
        date_from = today - timedelta(days=6)
        date_to   = today

    # ── Брони ────────────────────────────────────────────────────────────────
    bookings_qs = (
        KaraokeBooking.objects
        .filter(venue=venue, booking_date__range=(date_from, date_to))
        .exclude(status="cancelled")
        .select_related("room")
        .order_by("booking_date", "start_time")
    )

    total_bookings = bookings_qs.count()
    total_guests   = bookings_qs.aggregate(s=Sum("guests"))["s"] or 0

    # Room revenue: price_per_hour * duration
    room_revenue = Decimal("0")
    for b in bookings_qs:
        if b.room and b.room.price_per_hour:
            # duration in hours
            def _mins(t):
                return (t.hour if t.hour >= 6 else t.hour + 24) * 60 + t.minute
            dur_h = (_mins(b.end_time) - _mins(b.start_time)) / 60
            if dur_h > 0:
                room_revenue += b.room.price_per_hour * Decimal(str(round(dur_h, 2)))

    # ── Заказы еды ────────────────────────────────────────────────────────────
    orders_qs = (
        KaraokeOrder.objects
        .filter(venue=venue, order_date__range=(date_from, date_to))
        .prefetch_related("items__menu_item")
        .select_related("room", "booking")
        .order_by("-order_date", "-created_at")
    )

    total_orders    = orders_qs.count()
    total_dishes    = orders_qs.aggregate(s=Sum("items__qty"))["s"] or 0
    food_revenue    = orders_qs.aggregate(s=Sum("total_amount"))["s"] or Decimal("0")
    total_revenue   = room_revenue + food_revenue

    # ── Per-day breakdown ─────────────────────────────────────────────────────
    days = []
    cur = date_from
    while cur <= date_to:
        day_bookings = [b for b in bookings_qs if b.booking_date == cur]
        day_orders   = [o for o in orders_qs   if o.order_date   == cur]
        days.append({
            "date":     cur,
            "bookings": len(day_bookings),
            "guests":   sum(b.guests for b in day_bookings),
            "orders":   len(day_orders),
            "dishes":   sum(i.qty for o in day_orders for i in o.items.all()),
            "food_rev": sum(o.total_amount for o in day_orders),
        })
        cur += timedelta(days=1)

    # ── Menu items for add-order form ─────────────────────────────────────────
    menu_cats = venue.menu_categories.prefetch_related("items").filter(
        items__is_active=True
    ).distinct()

    return render(request, "dashboard/karaoke/report.html", {
        "venue":          venue,
        "period":         period,
        "date_from":      date_from,
        "date_to":        date_to,
        "today":          today,
        # summary
        "total_bookings": total_bookings,
        "total_guests":   total_guests,
        "total_orders":   total_orders,
        "total_dishes":   total_dishes,
        "room_revenue":   room_revenue,
        "food_revenue":   food_revenue,
        "total_revenue":  total_revenue,
        # detail
        "bookings":       bookings_qs,
        "orders":         orders_qs,
        "days":           days,
        "menu_cats":      menu_cats,
    })


# ── ЗАКАЗ ЕДЫ — создать ───────────────────────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_order_add(request, venue_id):
    venue = get_object_or_404(KaraokeVenue, id=venue_id)
    if not _check_access(request.user, venue):
        return JsonResponse({"ok": False}, status=403)

    order_date_str = request.POST.get("order_date", "").strip()
    booking_id     = request.POST.get("booking_id", "").strip()
    room_id        = request.POST.get("room_id", "").strip()
    comment        = request.POST.get("comment", "").strip()

    try:
        order_date = datetime.strptime(order_date_str, "%Y-%m-%d").date()
    except ValueError:
        order_date = date.today()

    booking = None
    if booking_id.isdigit():
        booking = KaraokeBooking.objects.filter(id=int(booking_id), venue=venue).first()

    room = None
    if room_id.isdigit():
        room = KaraokeRoom.objects.filter(id=int(room_id), venue=venue).first()
    elif booking:
        room = booking.room

    order = KaraokeOrder.objects.create(
        venue=venue,
        booking=booking,
        room=room,
        order_date=order_date,
        comment=comment,
    )

    # Items: item_id_{n} + qty_{n} pairs from POST
    total = Decimal("0")
    for key, val in request.POST.items():
        if key.startswith("item_id_"):
            n = key[len("item_id_"):]
            qty_str = request.POST.get(f"qty_{n}", "1")
            try:
                item_id = int(val)
                qty = max(1, int(qty_str))
                menu_item = KaraokeMenuItem.objects.get(id=item_id, venue=venue, is_active=True)
                oi = KaraokeOrderItem(order=order, menu_item=menu_item, qty=qty,
                                      price_snapshot=menu_item.price)
                oi.save()
                total += oi.line_total
            except (KaraokeMenuItem.DoesNotExist, ValueError):
                continue

    order.total_amount = total
    order.save(update_fields=["total_amount"])

    return JsonResponse({"ok": True, "id": order.id, "total": str(total)})


# ── ЗАКАЗ ЕДЫ — удалить ──────────────────────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def karaoke_order_delete(request, order_id):
    order = get_object_or_404(KaraokeOrder, id=order_id)
    if not _check_access(request.user, order.venue):
        return JsonResponse({"ok": False}, status=403)
    order.delete()
    return JsonResponse({"ok": True})
