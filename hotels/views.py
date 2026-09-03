import json
from urllib.parse import quote
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse

from .models import (
    Hotel, HotelBranch, RoomCategory, Room, HotelBooking, HotelService,
    HotelServiceSession, HotelServiceBooking, RoomRequest,
)


def _get_bot_token():
    return (getattr(settings, "TG_BOT_TOKEN", "") or getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()


def _notify_hotel_booking(branch, msg):
    token = _get_bot_token()
    if not token or not branch.tg_chat_id:
        return
    try:
        from integrations.telegram import send_message
        send_message(token, branch.tg_chat_id, msg, message_thread_id=branch.tg_thread_id)
    except Exception:
        pass


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
        .prefetch_related("rooms__bookings")
        .order_by("sort_order", "id")
    )
    uncategorized = (
        branch.rooms.filter(category__isnull=True)
        .prefetch_related("bookings")
        .order_by("sort_order", "id")
    )

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
            "price_extra": float(r.price_per_extra_guest),
            "max_guests": r.max_guests,
            "description": r.description_ru or "",
            "amenities": r.amenities_list,
            "photos": [p.url for p in r.photos],
            "book_url": reverse("hotels:room_book", args=[r.id]),
            "available": r.public_available,
            "busy_until": r.busy_until.strftime("%d.%m.%Y") if r.busy_until else None,
            # занятые интервалы — чтобы форма не давала выбрать пересекающиеся даты
            "busy_ranges": [
                [b.checkin_date.isoformat(), b.checkout_date.isoformat()]
                for b in r._blocking_bookings()
            ],
        }
        for r in all_rooms
    ], ensure_ascii=False)

    services = (
        HotelService.objects
        .filter(branch=branch, is_active=True)
        .prefetch_related("sessions")
        .order_by("sort_order", "id")
    )
    services_json = json.dumps([
        {
            "id": s.id,
            "name": s.name_ru,
            "price": float(s.price),
            "description": s.description_ru or "",
            "photos": [p.url for p in s.photos],
            "sessions": [
                {"id": ss.id, "label": ss.label}
                for ss in s.sessions.filter(is_active=True)
            ],
            "book_url": reverse("hotels:service_book", args=[s.id]),
        }
        for s in services
    ], ensure_ascii=False)

    return render(request, "hotels/hotel_branch.html", {
        "branch": branch,
        "hotel": branch.hotel,
        "categories": categories,
        "uncategorized": uncategorized,
        "rooms_json": rooms_json,
        "services": services,
        "services_json": services_json,
    })


@require_POST
def room_book(request, room_id):
    room = get_object_or_404(Room, id=room_id, is_available=True)
    branch = room.branch

    name        = (request.POST.get("name") or "").strip()
    phone       = (request.POST.get("phone") or "").strip()
    checkin     = (request.POST.get("checkin") or "").strip()
    nights      = (request.POST.get("nights") or "1").strip()
    guests      = (request.POST.get("guests") or "1").strip()
    rooms       = (request.POST.get("rooms_count") or "1").strip()
    comment     = (request.POST.get("comment") or "").strip()
    book_type   = request.POST.get("book_type", "booking")  # booking | checkin

    if not phone or len(phone) < 10:
        messages.error(request, "Укажите номер телефона")
        return redirect("hotels:hotel_branch", branch_id=branch.id)

    try:
        nights_int = max(1, int(nights))
    except ValueError:
        nights_int = 1

    try:
        guests_int = max(1, int(guests))
    except ValueError:
        guests_int = 1

    try:
        rooms_int = max(1, int(rooms))
    except ValueError:
        rooms_int = 1

    # цена за ночь = (базовая + доплата за гостей) × кол-во номеров
    price_per_night = room.price_per_night + room.price_per_extra_guest * max(0, guests_int - 1)
    total = price_per_night * nights_int * rooms_int

    # Дата заезда: форма присылает YYYY-MM-DD. Для «заселиться сейчас» без даты — сегодня.
    from datetime import datetime, timedelta, date as _date
    checkin_date = None
    try:
        checkin_date = datetime.strptime(checkin, "%Y-%m-%d").date()
    except ValueError:
        if book_type == "checkin":
            checkin_date = _date.today()
    checkout_date = checkin_date + timedelta(days=nights_int) if checkin_date else None

    # Проверка занятости по шахматке: номер не должен быть уже забронирован/заселён на этот период
    if checkin_date and checkout_date and not room.is_free_between(checkin_date, checkout_date):
        busy = room.busy_until
        if busy:
            messages.error(request, f"«{room.name_ru}» занят до {busy:%d.%m.%Y}. Выберите другие даты или номер.")
        else:
            messages.error(request, f"«{room.name_ru}» уже забронирован на выбранные даты. Выберите другие даты или номер.")
        return redirect("hotels:hotel_branch", branch_id=branch.id)

    # Формат даты для сообщения: дд.мм.гггг
    checkin_fmt = checkin_date.strftime("%d.%m.%Y") if checkin_date else (checkin or "—")

    nights_word = "ночь" if nights_int == 1 else ("ночи" if 2 <= nights_int <= 4 else "ночей")
    guests_word = "гость" if guests_int == 1 else ("гостя" if 2 <= guests_int <= 4 else "гостей")
    rooms_word  = "номер" if rooms_int == 1 else ("номера" if 2 <= rooms_int <= 4 else "номеров")

    total_fmt = f"{int(total):,}".replace(",", " ")

    rooms_line = f"{rooms_int} {rooms_word}" if rooms_int > 1 else ""

    if book_type == "checkin":
        msg = f"Заселение сегодня\n\n"
        msg += f"{branch.hotel.name_ru} — {room.name_ru}\n"
        if rooms_line:
            msg += f"Номеров: {rooms_line}\n"
        msg += f"Заезд: {checkin_fmt} · {nights_int} {nights_word} · {guests_int} {guests_word}\n"
        msg += f"Сумма: {total_fmt} сом\n\n"
        msg += f"Гость: {name}\n"
        msg += f"Тел: {phone}\n"
        if comment:
            msg += f"Комментарий: {comment}\n"
    else:
        msg = f"Запрос на бронь\n\n"
        msg += f"{branch.hotel.name_ru} — {room.name_ru}\n"
        if rooms_line:
            msg += f"Номеров: {rooms_line}\n"
        msg += f"Заезд: {checkin_fmt} · {nights_int} {nights_word} · {guests_int} {guests_word}\n"
        msg += f"Сумма: {total_fmt} сом\n\n"
        msg += f"Гость: {name}\n"
        msg += f"Тел: {phone}\n"
        if comment:
            msg += f"Комментарий: {comment}\n"
        msg += f"\nЕсли номер свободен, готов(а) подтвердить бронь. Подскажите, пожалуйста, условия и реквизиты для оплаты задатка."

    # сохраняем в БД
    HotelBooking.objects.create(
        branch=branch,
        room=room,
        book_type=book_type,
        customer_name=name,
        customer_phone=phone,
        checkin_date=checkin_date,
        checkout_date=checkout_date,
        nights=nights_int,
        guests=guests_int,
        rooms_count=rooms_int,
        price_per_night=price_per_night,
        total=total,
        comment=comment,
        status=HotelBooking.Status.NEW,
    )

    _notify_hotel_booking(branch, msg)

    wa_number = "".join(ch for ch in (branch.phone or "") if ch.isdigit())
    if wa_number:
        return redirect(f"https://wa.me/{wa_number}?text={quote(msg)}")

    messages.success(request, "Ваша заявка принята! Мы свяжемся с вами.")
    return redirect("hotels:hotel_branch", branch_id=branch.id)


@require_POST
def service_book(request, service_id):
    service = get_object_or_404(HotelService, id=service_id, is_active=True)
    branch  = service.branch

    name       = (request.POST.get("name") or "").strip()
    phone      = (request.POST.get("phone") or "").strip()
    date_val   = (request.POST.get("booking_date") or "").strip()
    session_id = request.POST.get("session_id") or None
    comment    = (request.POST.get("comment") or "").strip()

    if not phone or len(phone) < 10:
        messages.error(request, "Укажите номер телефона")
        return redirect("hotels:hotel_branch", branch_id=branch.id)

    session = None
    session_label = "—"
    if session_id:
        try:
            session = HotelServiceSession.objects.get(id=session_id, service=service)
            session_label = session.label
        except HotelServiceSession.DoesNotExist:
            pass

    try:
        from datetime import datetime
        date_fmt = datetime.strptime(date_val, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        date_fmt = date_val

    price_fmt = f"{int(service.price):,}".replace(",", " ")

    msg  = f"Заявка на услугу\n\n"
    msg += f"{branch.hotel.name_ru}\n"
    msg += f"Услуга: {service.name_ru}\n"
    if date_fmt:
        msg += f"Дата: {date_fmt}\n"
    msg += f"Сеанс: {session_label}\n"
    msg += f"Стоимость: {price_fmt} сом\n\n"
    msg += f"Гость: {name}\n"
    msg += f"Тел: {phone}\n"
    if comment:
        msg += f"Комментарий: {comment}\n"

    HotelServiceBooking.objects.create(
        service=service,
        session=session,
        booking_date=date_val,
        customer_name=name,
        customer_phone=phone,
        comment=comment,
        status=HotelServiceBooking.Status.NEW,
    )

    _notify_hotel_booking(branch, msg)

    wa_number = "".join(ch for ch in (branch.phone or "") if ch.isdigit())
    if wa_number:
        return redirect(f"https://wa.me/{wa_number}?text={quote(msg)}")

    messages.success(request, "Заявка принята! Мы свяжемся с вами.")
    return redirect("hotels:hotel_branch", branch_id=branch.id)


# ── ЗАЯВКИ ИЗ НОМЕРА (услуги в номер / вызов сотрудника) ─────────────────────

def _get_room_by_code(code):
    return (
        Room.objects
        .select_related("branch", "branch__hotel")
        .filter(public_code=code, branch__is_active=True)
        .first()
    )


def room_request_page(request, code):
    room = _get_room_by_code(code)
    if not room:
        return render(request, "hotels/room_request.html", {"not_found": True}, status=404)
    # на странице номера — независимо от «показывать на сайте», только галочка show_in_room
    services = HotelService.objects.filter(
        branch=room.branch, show_in_room=True
    ).order_by("sort_order", "id")
    return render(request, "hotels/room_request.html", {
        "room": room,
        "branch": room.branch,
        "hotel": room.branch.hotel,
        "services": services,
    })


@require_POST
def room_request_submit(request, code):
    room = _get_room_by_code(code)
    if not room:
        return render(request, "hotels/room_request.html", {"not_found": True}, status=404)
    branch = room.branch

    kind = request.POST.get("kind", "service")
    if kind not in dict(RoomRequest.Kind.choices):
        kind = RoomRequest.Kind.SERVICE
    guest_name = (request.POST.get("guest_name") or "").strip()[:120]
    comment = (request.POST.get("comment") or "").strip()[:500]

    service_ids = request.POST.getlist("services")
    services = list(HotelService.objects.filter(
        id__in=service_ids, branch=branch, show_in_room=True
    )) if kind == RoomRequest.Kind.SERVICE else []

    if kind == RoomRequest.Kind.SERVICE and not services and not comment:
        messages.error(request, "Выберите услугу или напишите, что нужно")
        return redirect("hotel_room_request", code=code)

    total = sum((s.price for s in services), 0)
    req = RoomRequest.objects.create(
        branch=branch, room=room, kind=kind,
        guest_name=guest_name, comment=comment, total=total,
        status=RoomRequest.Status.NEW,
    )
    if services:
        req.services.set(services)

    if kind == RoomRequest.Kind.LOBBY:
        msg = f"🛎 Вызов сотрудника в номер\n\n"
    else:
        msg = f"🧺 Заявка на услуги в номер\n\n"
    msg += f"{branch.hotel.name_ru} · {branch.name_ru}\n"
    msg += f"Номер: {room.name_ru}\n"
    if services:
        msg += "\nУслуги:\n"
        for s in services:
            msg += f" • {s.name_ru} — {int(s.price):,} сом\n".replace(",", " ")
        msg += f"Итого: {int(total):,} сом\n".replace(",", " ")
    if guest_name:
        msg += f"\nГость: {guest_name}\n"
    if comment:
        msg += f"Комментарий: {comment}\n"
    _notify_hotel_booking(branch, msg)

    messages.success(request, "Заявка отправлена! Скоро подойдём." if kind == RoomRequest.Kind.LOBBY else "Заявка отправлена! Скоро принесём.")
    return redirect("hotel_room_request", code=code)
