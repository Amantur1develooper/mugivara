from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from .models import Hotel, HotelBranch, HotelMembership, RoomCategory, Room, HotelBooking

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
        hotel.external_url = request.POST.get("external_url", "").strip()
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
        branch.external_url = request.POST.get("external_url", "").strip()
        branch.is_active   = request.POST.get("is_active") == "on"
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
        room.max_guests           = max(1, int(request.POST.get("max_guests") or 1))
        room.is_available         = request.POST.get("is_available") == "on"
        room.sort_order           = int(request.POST.get("sort_order") or 0)

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
    qs = HotelBooking.objects.filter(branch=branch).select_related("room")
    if status_filter:
        qs = qs.filter(status=status_filter)

    return render(request, "dashboard/hotels/bookings.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "bookings": qs,
        "status_filter": status_filter,
        "statuses": HotelBooking.Status.choices,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def hotel_booking_status(request, booking_id):
    booking = get_object_or_404(HotelBooking, id=booking_id)
    if not _has_branch_access(request.user, booking.branch):
        return redirect("dashboard:hotel_home")
    new_status = request.POST.get("status", "")
    if new_status in dict(HotelBooking.Status.choices):
        booking.status = new_status
        booking.save(update_fields=["status", "updated_at"])
        messages.success(request, "Статус обновлён")
    return redirect("dashboard:hotel_bookings", branch_id=booking.branch_id)
