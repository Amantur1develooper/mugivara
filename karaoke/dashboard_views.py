import json
from datetime import date, datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages

from .models import (KaraokeVenue, RoomCategory, KaraokeRoom, KaraokeRoomPhoto,
                     KaraokeBooking, KaraokeMenuCategory, KaraokeMenuItem, KaraokeMembership)

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
    cat_id = request.POST.get("cat_id")
    item.category_id = int(cat_id) if cat_id and cat_id.isdigit() else None
    if "photo" in request.FILES:
        item.photo = request.FILES["photo"]
    if not item.name:
        return JsonResponse({"ok": False, "error": "Введите название"}, status=400)
    item.save()
    photo_url = item.photo.url if item.photo else ""
    return JsonResponse({"ok": True, "id": item.id, "name": item.name,
                         "price": str(item.price), "photo": photo_url})


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
