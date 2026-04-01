import json
from urllib.parse import quote
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse

from .models import Hotel, HotelBranch, RoomCategory, Room


def hotel_list(request):
    hotels = (
        Hotel.objects
        .filter(is_active=True)
        .prefetch_related("branches")
        .order_by("-rating", "name_ru")
    )
    cards = []
    for h in hotels:
        branches = [b for b in h.branches.all() if b.is_active]
        if not branches:
            continue
        cover = next((b.cover_photo for b in branches if b.cover_photo), None)
        cards.append({"obj": h, "branches_count": len(branches), "cover": cover})

    return render(request, "hotels/hotel_list.html", {"cards": cards})


def hotel_detail(request, slug):
    hotel = get_object_or_404(Hotel, slug=slug, is_active=True)
    branches = hotel.branches.filter(is_active=True).order_by("name_ru")
    return render(request, "hotels/hotel_detail.html", {
        "hotel": hotel,
        "branches": branches,
    })


def hotel_branch(request, branch_id):
    branch = get_object_or_404(HotelBranch, id=branch_id, is_active=True)

    categories = (
        RoomCategory.objects
        .filter(branch=branch)
        .prefetch_related("rooms")
        .order_by("sort_order", "id")
    )
    uncategorized = branch.rooms.filter(category__isnull=True).order_by("sort_order", "id")

    # все номера -> JSON для JS-модалей
    all_rooms = []
    for cat in categories:
        all_rooms.extend(cat.rooms.all())
    all_rooms.extend(uncategorized)

    rooms_json = json.dumps([
        {
            "id": r.id,
            "name": r.name_ru,
            "price": float(r.price_per_night),
            "max_guests": r.max_guests,
            "description": r.description_ru or "",
            "amenities": r.amenities_list,
            "photos": [p.url for p in r.photos],
            "book_url": reverse("hotels:room_book", args=[r.id]),
            "available": r.is_available,
        }
        for r in all_rooms
    ], ensure_ascii=False)

    return render(request, "hotels/hotel_branch.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "categories": categories,
        "uncategorized": uncategorized,
        "rooms_json": rooms_json,
    })


@require_POST
def room_book(request, room_id):
    room = get_object_or_404(Room, id=room_id, is_available=True)
    branch = room.branch

    name      = (request.POST.get("name") or "").strip() or "Гость"
    phone     = (request.POST.get("phone") or "").strip()
    checkin   = (request.POST.get("checkin") or "").strip()
    nights    = (request.POST.get("nights") or "1").strip()
    guests    = (request.POST.get("guests") or "1").strip()
    comment   = (request.POST.get("comment") or "").strip()
    book_type = request.POST.get("book_type", "booking")  # booking | checkin

    if not phone:
        messages.error(request, "Укажите телефон")
        return redirect("hotels:hotel_branch", branch_id=branch.id)

    try:
        nights_int = max(1, int(nights))
    except ValueError:
        nights_int = 1

    total = room.price_per_night * nights_int

    action_text = "Заселиться" if book_type == "checkin" else "Бронирование"

    msg = (
        f"🏨 {action_text}\n"
        f"Отель: {branch.hotel.name_ru}\n"
        f"Филиал: {branch.name_ru}\n"
        f"Номер: {room.name_ru}\n"
        f"Цена: {room.price_per_night} сом/ночь\n"
        f"Заезд: {checkin}\n"
        f"Ночей: {nights_int}\n"
        f"Гостей: {guests}\n"
        f"Итого: {total} сом\n"
        f"Имя: {name}\n"
        f"Телефон: {phone}\n"
    )
    if comment:
        msg += f"Комментарий: {comment}\n"

    wa_number = "".join(ch for ch in (branch.phone or "") if ch.isdigit())
    if wa_number:
        return redirect(f"https://wa.me/{wa_number}?text={quote(msg)}")

    messages.success(request, "Ваша заявка принята! Мы свяжемся с вами.")
    return redirect("hotels:hotel_branch", branch_id=branch.id)
