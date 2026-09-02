from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .models import (
    Hotel, HotelBranch, HotelMembership, RoomCategory, Room, HotelBooking,
    HotelService, HotelServiceSession, HotelServiceBooking,
    FinanceAccount, FinanceCategory, FinanceTxn, RoomRequest,
)

LOGIN_URL = "dashboard:login"


# ── helpers ──────────────────────────────────────────────────────────────────

def _user_hotels(user):
    ids = HotelMembership.objects.filter(user=user).values_list("hotel_id", flat=True)
    return Hotel.objects.filter(id__in=ids)


def _has_hotel_access(user, hotel):
    return HotelMembership.objects.filter(user=user, hotel=hotel).exists()


def _has_branch_access(user, branch):
    return _has_hotel_access(user, branch.hotel)


def _dec(val, default="0"):
    try:
        return Decimal(val or default)
    except InvalidOperation:
        return Decimal(default)


# ── HOME ─────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def hotel_home(request):
    hotels = _user_hotels(request.user).prefetch_related("branches")
    data = []
    for h in hotels:
        branches = list(h.branches.order_by("name_ru"))
        new_bookings = HotelBooking.objects.filter(
            branch__hotel=h, status=HotelBooking.Status.NEW
        ).count()
        data.append({"hotel": h, "branches": branches, "new_bookings": new_bookings})
    return render(request, "dashboard/hotels/home.html", {"data": data})


# ── HOTEL EDIT ────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def hotel_edit(request, hotel_id):
    hotel = get_object_or_404(Hotel, id=hotel_id)
    if not _has_hotel_access(request.user, hotel):
        return redirect("dashboard:hotel_home")

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if name:
            hotel.name_ru = name
        hotel.about_ru    = request.POST.get("about_ru", "").strip()
        hotel.is_active   = request.POST.get("is_active") == "on"
        if request.FILES.get("logo"):
            hotel.logo = request.FILES["logo"]
        hotel.save()
        messages.success(request, "Данные отеля сохранены")
        return redirect("dashboard:hotel_edit", hotel_id=hotel.id)

    return render(request, "dashboard/hotels/hotel_edit.html", {"hotel": hotel})


# ── BRANCH EDIT ───────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def hotel_branch_edit(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")

    if request.method == "POST":
        branch.name_ru     = request.POST.get("name_ru", branch.name_ru).strip()
        branch.address     = request.POST.get("address", "").strip()
        branch.phone       = request.POST.get("phone", "").strip()
        branch.map_url     = request.POST.get("map_url", "").strip()
        branch.is_active   = request.POST.get("is_active") == "on"
        branch.tg_chat_id  = request.POST.get("tg_chat_id", "").strip()
        tgt = request.POST.get("tg_thread_id", "").strip()
        branch.tg_thread_id = int(tgt) if tgt.isdigit() else None
        if request.FILES.get("cover_photo"):
            branch.cover_photo = request.FILES["cover_photo"]
        branch.save()
        messages.success(request, "Настройки сохранены")
        return redirect("dashboard:hotel_branch_edit", branch_id=branch.id)

    return render(request, "dashboard/hotels/branch_edit.html", {"branch": branch, "hotel": branch.hotel})


# ── ROOM LIST ─────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def hotel_room_list(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")

    categories = (
        RoomCategory.objects
        .filter(branch=branch)
        .prefetch_related("rooms")
        .order_by("sort_order", "id")
    )
    uncategorized = branch.rooms.filter(category__isnull=True).order_by("sort_order", "id")

    return render(request, "dashboard/hotels/room_list.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "categories": categories,
        "uncategorized": uncategorized,
    })


# ── ROOM ADD ──────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def hotel_room_add(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")

    categories = RoomCategory.objects.filter(branch=branch).order_by("sort_order")

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if not name:
            messages.error(request, "Укажите название номера")
            return redirect("dashboard:hotel_room_add", branch_id=branch.id)

        cat_id = request.POST.get("category") or None
        category = None
        if cat_id:
            try:
                category = RoomCategory.objects.get(id=cat_id, branch=branch)
            except RoomCategory.DoesNotExist:
                pass

        room = Room(
            branch=branch,
            category=category,
            name_ru=name,
            description_ru=request.POST.get("description_ru", "").strip(),
            amenities_ru=request.POST.get("amenities_ru", "").strip(),
            price_per_night=_dec(request.POST.get("price_per_night")),
            price_per_extra_guest=_dec(request.POST.get("price_per_extra_guest")),
            max_guests=max(1, int(request.POST.get("max_guests") or 2)),
            is_available=request.POST.get("is_available") == "on",
            sort_order=int(request.POST.get("sort_order") or 0),
        )
        for fname in ("photo1", "photo2", "photo3"):
            f = request.FILES.get(fname)
            if f:
                setattr(room, fname, f)
        room.save()
        messages.success(request, f"Номер «{name}» добавлен")
        return redirect("dashboard:hotel_room_list", branch_id=branch.id)

    return render(request, "dashboard/hotels/room_edit.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "categories": categories,
        "room": None,
    })


# ── ROOM EDIT ─────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def hotel_room_edit(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    branch = room.branch
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")

    categories = RoomCategory.objects.filter(branch=branch).order_by("sort_order")

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if name:
            room.name_ru = name
        room.description_ru       = request.POST.get("description_ru", "").strip()
        room.amenities_ru         = request.POST.get("amenities_ru", "").strip()
        room.price_per_night      = _dec(request.POST.get("price_per_night"))
        room.price_per_extra_guest = _dec(request.POST.get("price_per_extra_guest"))
        try:
            room.max_guests = max(1, int(request.POST.get("max_guests") or 1))
        except (ValueError, TypeError):
            room.max_guests = 1
        room.is_available = request.POST.get("is_available") == "on"
        try:
            room.sort_order = int(request.POST.get("sort_order") or 0)
        except (ValueError, TypeError):
            room.sort_order = 0

        cat_id = request.POST.get("category") or None
        if cat_id:
            try:
                room.category = RoomCategory.objects.get(id=cat_id, branch=branch)
            except RoomCategory.DoesNotExist:
                room.category = None
        else:
            room.category = None

        for fname in ("photo1", "photo2", "photo3"):
            f = request.FILES.get(fname)
            if f:
                setattr(room, fname, f)
        room.save()
        messages.success(request, "Номер обновлён")
        return redirect("dashboard:hotel_room_list", branch_id=branch.id)

    return render(request, "dashboard/hotels/room_edit.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "categories": categories,
        "room": room,
    })


# ── AJAX: toggle room ─────────────────────────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_room_toggle(request, room_id):
    room = get_object_or_404(Room, id=room_id)
    if not _has_branch_access(request.user, room.branch):
        return JsonResponse({"ok": False}, status=403)
    room.is_available = not room.is_available
    room.save(update_fields=["is_available", "updated_at"])
    return JsonResponse({"ok": True, "is_available": room.is_available})


# ── AJAX: toggle branch ───────────────────────────────────────────────────────

@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_branch_toggle(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return JsonResponse({"ok": False}, status=403)
    branch.is_active = not branch.is_active
    branch.save(update_fields=["is_active", "updated_at"])
    return JsonResponse({"ok": True, "is_active": branch.is_active})


# ── BOOKINGS ──────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def hotel_bookings(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")

    status_filter = request.GET.get("status", "")
    qs = HotelBooking.objects.filter(branch=branch).select_related("room", "branch")
    if status_filter:
        qs = qs.filter(status=status_filter)

    in_house_qs = HotelBooking.objects.filter(
        branch=branch, actual_checkin_at__isnull=False, actual_checkout_at__isnull=True,
    )
    in_house_guests = sum(b.guests for b in in_house_qs)
    in_house_rooms = in_house_qs.count()

    return render(request, "dashboard/hotels/bookings.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "bookings": qs,
        "status_filter": status_filter,
        "statuses": HotelBooking.Status.choices,
        "in_house_guests": in_house_guests,
        "in_house_rooms": in_house_rooms,
    })


# ── ЗАЯВКИ ИЗ НОМЕРОВ ────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def hotel_room_requests(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")

    show = request.GET.get("show", "new")
    qs = (
        RoomRequest.objects.filter(branch=branch)
        .select_related("room").prefetch_related("services")
        .order_by("-created_at")
    )
    if show == "new":
        qs = qs.filter(status=RoomRequest.Status.NEW)

    return render(request, "dashboard/hotels/room_requests.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "requests": qs[:200],
        "show": show,
        "new_count": RoomRequest.objects.filter(branch=branch, status=RoomRequest.Status.NEW).count(),
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_room_request_done(request, req_id):
    req = get_object_or_404(RoomRequest, id=req_id)
    if not _has_branch_access(request.user, req.branch):
        return redirect("dashboard:hotel_home")
    req.status = (RoomRequest.Status.NEW if req.status == RoomRequest.Status.DONE
                  else RoomRequest.Status.DONE)
    req.save(update_fields=["status", "updated_at"])
    return _safe_next(request) or redirect("dashboard:hotel_room_requests", branch_id=req.branch_id)


@login_required(login_url=LOGIN_URL)
def hotel_chessboard(request, branch_id):
    from datetime import date, timedelta

    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")

    days = 14
    try:
        start = date.fromisoformat(request.GET.get("start", ""))
    except ValueError:
        start = date.today()
    date_list = [start + timedelta(days=i) for i in range(days)]

    rooms = (
        Room.objects.filter(branch=branch)
        .select_related("category")
        .order_by("category__sort_order", "sort_order", "id")
    )

    bookings = (
        HotelBooking.objects.filter(
            branch=branch,
            room__isnull=False,
            checkin_date__lt=date_list[-1] + timedelta(days=1),
            checkout_date__gt=date_list[0],
        )
        .exclude(status=HotelBooking.Status.CANCELLED)
        .select_related("room")
    )

    date_set = set(date_list)
    cell_map = {}
    bookings_json = {}
    for b in bookings:
        if not b.checkin_date or not b.checkout_date:
            continue
        bookings_json[b.id] = {
            "id": b.id,
            "name": b.customer_name,
            "phone": b.customer_phone,
            "room": b.room.name_ru,
            "checkin": b.checkin_date.strftime("%d.%m.%Y"),
            "checkout": b.checkout_date.strftime("%d.%m.%Y"),
            "nights": b.nights,
            "guests": b.guests,
            "total": int(b.total or 0),
            "status": b.status,
            "inhouse": bool(b.actual_checkin_at and not b.actual_checkout_at),
            "done": bool(b.actual_checkout_at),
        }
        d = b.checkin_date
        while d < b.checkout_date:
            if d in date_set:
                cell_map[(b.room_id, d)] = b
            d += timedelta(days=1)

    grid = []
    rooms_meta = []
    for room in rooms:
        grid.append({
            "room": room,
            "cells": [{"date": d, "booking": cell_map.get((room.id, d))} for d in date_list],
        })
        rooms_meta.append({
            "id": room.id,
            "name": room.name_ru,
            "price": int(room.price_per_night),
            "extra": int(room.price_per_extra_guest),
            "max_guests": room.max_guests,
        })

    return render(request, "dashboard/hotels/chessboard.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "date_list": date_list,
        "grid": grid,
        "rooms_meta": rooms_meta,
        "bookings_json": bookings_json,
        "today": date.today(),
        "prev_start": (start - timedelta(days=days)).isoformat(),
        "next_start": (start + timedelta(days=days)).isoformat(),
        "statuses": HotelBooking.Status.choices,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_chess_book(request, branch_id):
    """Создать бронь/заселение прямо из шахматки."""
    from datetime import datetime, timedelta, date

    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")

    fallback = _safe_next(request) or redirect("dashboard:hotel_chessboard", branch_id=branch.id)

    room = Room.objects.filter(id=request.POST.get("room") or 0, branch=branch).first()
    if not room:
        messages.error(request, "Номер не найден")
        return fallback

    name    = (request.POST.get("name") or "").strip()
    phone   = (request.POST.get("phone") or "").strip()
    comment = (request.POST.get("comment") or "").strip()
    book_type = request.POST.get("book_type", HotelBooking.BookType.BOOKING)
    if book_type not in dict(HotelBooking.BookType.choices):
        book_type = HotelBooking.BookType.BOOKING

    try:
        checkin_date = datetime.strptime(request.POST.get("checkin", ""), "%Y-%m-%d").date()
    except ValueError:
        checkin_date = date.today()
    try:
        nights = max(1, int(request.POST.get("nights") or 1))
    except (TypeError, ValueError):
        nights = 1
    try:
        guests = max(1, int(request.POST.get("guests") or 1))
    except (TypeError, ValueError):
        guests = 1
    checkout_date = checkin_date + timedelta(days=nights)

    if not name or not phone:
        messages.error(request, "Укажите имя и телефон гостя")
        return fallback

    clash = (
        HotelBooking.objects
        .filter(branch=branch, room=room,
                checkin_date__lt=checkout_date, checkout_date__gt=checkin_date)
        .exclude(status=HotelBooking.Status.CANCELLED)
        .exists()
    )
    if clash:
        messages.error(request, f"{room.name_ru}: на эти даты уже есть бронь")
        return fallback

    price_per_night = room.price_per_night + room.price_per_extra_guest * max(0, guests - 1)
    total = price_per_night * nights

    is_checkin = book_type == HotelBooking.BookType.CHECKIN
    HotelBooking.objects.create(
        branch=branch, room=room, book_type=book_type,
        customer_name=name, customer_phone=phone,
        checkin_date=checkin_date, checkout_date=checkout_date,
        nights=nights, guests=guests, rooms_count=1,
        price_per_night=price_per_night, total=total, comment=comment,
        status=HotelBooking.Status.CHECKEDIN if is_checkin else HotelBooking.Status.NEW,
        actual_checkin_at=timezone.now() if is_checkin else None,
    )
    messages.success(
        request,
        f"{'Заселён' if is_checkin else 'Бронь создана'}: {name} · {room.name_ru} · "
        f"{checkin_date:%d.%m}–{checkout_date:%d.%m}"
    )
    return fallback


def _safe_next(request):
    """redirect на ?next=, если он ведёт на этот же хост; иначе None."""
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return None


def _booking_redirect(request, booking):
    """Вернуться на страницу, с которой пришёл запрос (шахматка / список), с фолбэком на список."""
    return _safe_next(request) or redirect("dashboard:hotel_bookings", branch_id=booking.branch_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_booking_status(request, booking_id):
    booking = get_object_or_404(HotelBooking, id=booking_id)
    if not _has_branch_access(request.user, booking.branch):
        return redirect("dashboard:hotel_home")
    new_status = request.POST.get("status", "")
    if new_status in dict(HotelBooking.Status.choices):
        booking.status = new_status
        fields = ["status", "updated_at"]
        # держим фактические отметки заезда/выезда в согласии со статусом
        if new_status == HotelBooking.Status.CHECKEDIN and not booking.actual_checkin_at:
            booking.actual_checkin_at = timezone.now()
            fields.append("actual_checkin_at")
        if new_status == HotelBooking.Status.COMPLETED and not booking.actual_checkout_at:
            booking.actual_checkout_at = timezone.now()
            fields.append("actual_checkout_at")
        booking.save(update_fields=fields)
        messages.success(request, "Статус обновлён")
    return _booking_redirect(request, booking)


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_booking_checkin(request, booking_id):
    booking = get_object_or_404(HotelBooking, id=booking_id)
    if not _has_branch_access(request.user, booking.branch):
        return redirect("dashboard:hotel_home")
    booking.actual_checkin_at = timezone.now()
    booking.status = HotelBooking.Status.CHECKEDIN
    booking.save(update_fields=["actual_checkin_at", "status", "updated_at"])
    messages.success(request, f"{booking.customer_name} заселён(а) — {timezone.localtime(booking.actual_checkin_at):%d.%m %H:%M}")
    return _booking_redirect(request, booking)


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_booking_checkout(request, booking_id):
    booking = get_object_or_404(HotelBooking, id=booking_id)
    if not _has_branch_access(request.user, booking.branch):
        return redirect("dashboard:hotel_home")
    booking.actual_checkout_at = timezone.now()
    booking.status = HotelBooking.Status.COMPLETED
    booking.save(update_fields=["actual_checkout_at", "status", "updated_at"])
    messages.success(request, f"{booking.customer_name} выселен(а) — {timezone.localtime(booking.actual_checkout_at):%d.%m %H:%M}")
    return _booking_redirect(request, booking)


# ── HOTEL SERVICES ────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def hotel_services(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")
    services = branch.services.prefetch_related("sessions").order_by("sort_order", "id")
    return render(request, "dashboard/hotels/services.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "services": services,
    })


@login_required(login_url=LOGIN_URL)
def hotel_service_edit(request, branch_id=None, service_id=None):
    if service_id:
        service = get_object_or_404(HotelService, id=service_id)
        branch = service.branch
    else:
        branch = get_object_or_404(HotelBranch, id=branch_id)
        service = None

    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")

    if request.method == "POST":
        name = request.POST.get("name_ru", "").strip()
        if not name:
            messages.error(request, "Укажите название")
            return redirect(request.path)

        if service is None:
            service = HotelService(branch=branch)

        service.name_ru = name
        service.description_ru = request.POST.get("description_ru", "").strip()
        service.price = _dec(request.POST.get("price"))
        service.is_active = request.POST.get("is_active") == "on"
        service.show_in_room = request.POST.get("show_in_room") == "on"
        try:
            service.sort_order = int(request.POST.get("sort_order") or 0)
        except (ValueError, TypeError):
            service.sort_order = 0

        for fname in ("photo1", "photo2", "photo3"):
            f = request.FILES.get(fname)
            if f:
                setattr(service, fname, f)
        service.save()
        messages.success(request, "Услуга сохранена")
        return redirect("dashboard:hotel_services", branch_id=branch.id)

    return render(request, "dashboard/hotels/service_edit.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "service": service,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_service_delete(request, service_id):
    service = get_object_or_404(HotelService, id=service_id)
    if not _has_branch_access(request.user, service.branch):
        return redirect("dashboard:hotel_home")
    branch_id = service.branch_id
    service.delete()
    messages.success(request, "Услуга удалена")
    return redirect("dashboard:hotel_services", branch_id=branch_id)


@login_required(login_url=LOGIN_URL)
def hotel_service_sessions(request, service_id):
    service = get_object_or_404(HotelService, id=service_id)
    if not _has_branch_access(request.user, service.branch):
        return redirect("dashboard:hotel_home")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add":
            label = request.POST.get("label", "").strip()
            if label:
                sort_order = service.sessions.count()
                HotelServiceSession.objects.create(service=service, label=label, sort_order=sort_order)
                messages.success(request, "Сеанс добавлен")
        elif action == "delete":
            session_id = request.POST.get("session_id")
            HotelServiceSession.objects.filter(id=session_id, service=service).delete()
            messages.success(request, "Сеанс удалён")
        elif action == "toggle":
            session_id = request.POST.get("session_id")
            s = get_object_or_404(HotelServiceSession, id=session_id, service=service)
            s.is_active = not s.is_active
            s.save(update_fields=["is_active", "updated_at"])
        return redirect("dashboard:hotel_service_sessions", service_id=service.id)

    sessions = service.sessions.all()
    return render(request, "dashboard/hotels/service_sessions.html", {
        "service": service,
        "branch": service.branch,
        "hotel": service.branch.hotel,
        "sessions": sessions,
    })


@login_required(login_url=LOGIN_URL)
def hotel_service_bookings(request, service_id):
    service = get_object_or_404(HotelService, id=service_id)
    if not _has_branch_access(request.user, service.branch):
        return redirect("dashboard:hotel_home")

    bookings = service.bookings.select_related("session").order_by("-created_at")
    return render(request, "dashboard/hotels/service_bookings.html", {
        "service": service,
        "branch": service.branch,
        "hotel": service.branch.hotel,
        "bookings": bookings,
        "statuses": HotelServiceBooking.Status.choices,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_service_booking_status(request, booking_id):
    booking = get_object_or_404(HotelServiceBooking, id=booking_id)
    if not _has_branch_access(request.user, booking.service.branch):
        return redirect("dashboard:hotel_home")
    new_status = request.POST.get("status", "")
    if new_status in dict(HotelServiceBooking.Status.choices):
        booking.status = new_status
        booking.save(update_fields=["status", "updated_at"])
    return redirect("dashboard:hotel_service_bookings", service_id=booking.service_id)


# ── ФИНАНСЫ / ДДС ────────────────────────────────────────────────────────────

def _fin_period(request):
    """Разбирает ?from=&to= (ISO). По умолчанию — текущий месяц."""
    from datetime import date
    import calendar

    today = date.today()
    try:
        d_from = date.fromisoformat(request.GET.get("from", ""))
    except ValueError:
        d_from = today.replace(day=1)
    try:
        d_to = date.fromisoformat(request.GET.get("to", ""))
    except ValueError:
        last = calendar.monthrange(d_from.year, d_from.month)[1]
        d_to = d_from.replace(day=last)
    if d_to < d_from:
        d_from, d_to = d_to, d_from

    # быстрые ссылки на соседние месяцы (от d_from)
    pm_y, pm_m = (d_from.year - 1, 12) if d_from.month == 1 else (d_from.year, d_from.month - 1)
    nm_y, nm_m = (d_from.year + 1, 1) if d_from.month == 12 else (d_from.year, d_from.month + 1)
    prev_from = date(pm_y, pm_m, 1)
    next_from = date(nm_y, nm_m, 1)
    return {
        "from": d_from, "to": d_to,
        "prev_from": prev_from.isoformat(),
        "prev_to": date(pm_y, pm_m, calendar.monthrange(pm_y, pm_m)[1]).isoformat(),
        "next_from": next_from.isoformat(),
        "next_to": date(nm_y, nm_m, calendar.monthrange(nm_y, nm_m)[1]).isoformat(),
    }


@login_required(login_url=LOGIN_URL)
def hotel_finance(request, branch_id):
    from datetime import timedelta
    from django.db.models import Sum

    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")

    period = _fin_period(request)
    d_from, d_to = period["from"], period["to"]
    day_before = d_from - timedelta(days=1)

    accounts = list(FinanceAccount.objects.filter(branch=branch).order_by("sort_order", "id"))
    txns_period = (
        FinanceTxn.objects.filter(branch=branch, date__gte=d_from, date__lte=d_to)
        .select_related("account", "to_account", "category", "booking")
        .order_by("-date", "-id")
    )

    # сводка по счетам
    acc_rows = []
    total_open = total_close = Decimal("0")
    for a in accounts:
        opening = a.balance_on(day_before)
        closing = a.balance_on(d_to)
        acc_rows.append({"acc": a, "opening": opening, "closing": closing})
        total_open += opening
        total_close += closing

    income_total  = txns_period.filter(kind=FinanceTxn.Kind.INCOME).aggregate(s=Sum("amount"))["s"] or Decimal("0")
    expense_total = txns_period.filter(kind=FinanceTxn.Kind.EXPENSE).aggregate(s=Sum("amount"))["s"] or Decimal("0")

    def _by_cat(kind):
        rows = (
            txns_period.filter(kind=kind)
            .values("category__name")
            .annotate(s=Sum("amount"))
            .order_by("-s")
        )
        return [{"name": r["category__name"] or "Без статьи", "sum": r["s"]} for r in rows]

    ctx = {
        "branch": branch,
        "hotel": branch.hotel,
        "accounts": accounts,
        "acc_rows": acc_rows,
        "total_open": total_open,
        "total_close": total_close,
        "income_total": income_total,
        "expense_total": expense_total,
        "net_flow": income_total - expense_total,
        "income_by_cat": _by_cat(FinanceTxn.Kind.INCOME),
        "expense_by_cat": _by_cat(FinanceTxn.Kind.EXPENSE),
        "txns": txns_period,
        "categories_in":  FinanceCategory.objects.filter(branch=branch, flow=FinanceCategory.Flow.IN,  is_active=True),
        "categories_out": FinanceCategory.objects.filter(branch=branch, flow=FinanceCategory.Flow.OUT, is_active=True),
        "period": period,
        "kinds": FinanceTxn.Kind.choices,
    }
    return render(request, "dashboard/hotels/finance.html", ctx)


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_finance_txn_add(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")

    back = _safe_next(request) or redirect("dashboard:hotel_finance", branch_id=branch.id)

    kind = request.POST.get("kind")
    if kind not in dict(FinanceTxn.Kind.choices):
        messages.error(request, "Неверный тип операции")
        return back

    amount = _dec(request.POST.get("amount"))
    if amount <= 0:
        messages.error(request, "Сумма должна быть больше нуля")
        return back

    try:
        from datetime import date
        txn_date = date.fromisoformat(request.POST.get("date", ""))
    except ValueError:
        from datetime import date
        txn_date = date.today()

    account = FinanceAccount.objects.filter(id=request.POST.get("account") or 0, branch=branch).first()
    if not account:
        messages.error(request, "Выберите счёт")
        return back

    to_account = None
    category = None
    if kind == FinanceTxn.Kind.TRANSFER:
        to_account = FinanceAccount.objects.filter(id=request.POST.get("to_account") or 0, branch=branch).first()
        if not to_account or to_account.id == account.id:
            messages.error(request, "Для перевода выберите другой счёт зачисления")
            return back
    else:
        flow = FinanceCategory.Flow.IN if kind == FinanceTxn.Kind.INCOME else FinanceCategory.Flow.OUT
        category = FinanceCategory.objects.filter(
            id=request.POST.get("category") or 0, branch=branch, flow=flow
        ).first()

    FinanceTxn.objects.create(
        branch=branch, kind=kind, date=txn_date, amount=amount,
        account=account, to_account=to_account, category=category,
        comment=(request.POST.get("comment") or "").strip()[:255],
        created_by=request.user,
    )
    messages.success(request, "Операция добавлена")
    return back


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_finance_txn_delete(request, txn_id):
    txn = get_object_or_404(FinanceTxn, id=txn_id)
    if not _has_branch_access(request.user, txn.branch):
        return redirect("dashboard:hotel_home")
    if txn.is_auto:
        messages.error(request, "Автооперация по брони — меняется через саму бронь")
    else:
        txn.delete()
        messages.success(request, "Операция удалена")
    return _safe_next(request) or redirect("dashboard:hotel_finance", branch_id=txn.branch_id)


@login_required(login_url=LOGIN_URL)
def hotel_finance_refs(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")
    return render(request, "dashboard/hotels/finance_refs.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "accounts": FinanceAccount.objects.filter(branch=branch).order_by("sort_order", "id"),
        "categories_in":  FinanceCategory.objects.filter(branch=branch, flow=FinanceCategory.Flow.IN),
        "categories_out": FinanceCategory.objects.filter(branch=branch, flow=FinanceCategory.Flow.OUT),
        "account_kinds": FinanceAccount.Kind.choices,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_finance_account_save(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")
    back = redirect("dashboard:hotel_finance_refs", branch_id=branch.id)

    acc_id = request.POST.get("id")
    acc = FinanceAccount.objects.filter(id=acc_id or 0, branch=branch).first() if acc_id else FinanceAccount(branch=branch)
    if acc is None:
        return back

    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Укажите название счёта")
        return back
    acc.name = name[:100]
    acc.kind = request.POST.get("kind") if request.POST.get("kind") in dict(FinanceAccount.Kind.choices) else FinanceAccount.Kind.CASH
    acc.opening_balance = _dec(request.POST.get("opening_balance"))
    acc.is_active = bool(request.POST.get("is_active"))
    acc.is_default = bool(request.POST.get("is_default"))
    acc.save()
    if acc.is_default:
        FinanceAccount.objects.filter(branch=branch, is_default=True).exclude(id=acc.id).update(is_default=False)
    messages.success(request, "Счёт сохранён")
    return back


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_finance_account_delete(request, account_id):
    acc = get_object_or_404(FinanceAccount, id=account_id)
    if not _has_branch_access(request.user, acc.branch):
        return redirect("dashboard:hotel_home")
    branch_id = acc.branch_id
    if acc.txns.exists() or acc.txns_in.exists():
        acc.is_active = False
        acc.save(update_fields=["is_active", "updated_at"])
        messages.info(request, "По счёту есть операции — он скрыт, но не удалён")
    else:
        acc.delete()
        messages.success(request, "Счёт удалён")
    return redirect("dashboard:hotel_finance_refs", branch_id=branch_id)


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_finance_category_save(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id)
    if not _has_branch_access(request.user, branch):
        return redirect("dashboard:hotel_home")
    back = redirect("dashboard:hotel_finance_refs", branch_id=branch.id)

    cat_id = request.POST.get("id")
    cat = FinanceCategory.objects.filter(id=cat_id or 0, branch=branch).first() if cat_id else FinanceCategory(branch=branch)
    if cat is None:
        return back

    name = (request.POST.get("name") or "").strip()
    if not name:
        messages.error(request, "Укажите название статьи")
        return back
    cat.name = name[:120]
    if not cat_id:  # тип задаётся только при создании
        cat.flow = request.POST.get("flow") if request.POST.get("flow") in dict(FinanceCategory.Flow.choices) else FinanceCategory.Flow.OUT
    cat.is_active = bool(request.POST.get("is_active"))
    cat.save()
    messages.success(request, "Статья сохранена")
    return back


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_finance_category_delete(request, category_id):
    cat = get_object_or_404(FinanceCategory, id=category_id)
    if not _has_branch_access(request.user, cat.branch):
        return redirect("dashboard:hotel_home")
    branch_id = cat.branch_id
    if cat.txns.exists():
        cat.is_active = False
        cat.save(update_fields=["is_active", "updated_at"])
        messages.info(request, "По статье есть операции — она скрыта, но не удалена")
    else:
        cat.delete()
        messages.success(request, "Статья удалена")
    return redirect("dashboard:hotel_finance_refs", branch_id=branch_id)
