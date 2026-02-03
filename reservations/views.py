from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.translation import gettext as _

from core.models import Branch
from .models import Floor, Place, Booking
from reservations.tasks import notify_new_booking


def reservation_page(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)

    floors = (
        Floor.objects
        .filter(branch=branch, is_active=True)
        .order_by("sort_order", "id")
        .prefetch_related("places")
    )

    busy_ids = set(
        Booking.objects.filter(
            branch=branch,
            status__in=[Booking.Status.ACTIVE, Booking.Status.ARRIVED],
        ).values_list("place_id", flat=True)
    )

    floors_data = []
    for f in floors:
        places = []
        for p in f.places.all():
            places.append({
                "obj": p,
                "busy": p.id in busy_ids,
            })
        floors_data.append({"floor": f, "places": places})

    return render(request, "public_site/reservation.html", {
        "branch": branch,
        "floors_data": floors_data,
    })
import json
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.utils.translation import gettext as _
from django.contrib import messages
from django.utils import timezone

from core.models import Branch
from reservations.models import Floor, Place, Booking
from reservations.tasks import notify_new_booking


def hall_plan(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)

    floors = (Floor.objects
              .filter(branch=branch, is_active=True)
              .order_by("sort_order", "id")
              .prefetch_related("places"))

    active_bookings = (Booking.objects
                       .filter(branch=branch, status__in=[Booking.Status.ACTIVE, Booking.Status.ARRIVED])
                       .select_related("place"))

    booking_by_place = {b.place_id: b for b in active_bookings}

    floors_data = []
    for f in floors:
        places = []
        for p in f.places.filter(is_active=True).order_by("id"):
            places.append({
                "place": p,
                "booking": booking_by_place.get(p.id),
            })
        floors_data.append({"floor": f, "places": places})

    return render(request, "public_site/hall_plan.html", {
        "branch": branch,
        "floors_data": floors_data,
    })


@require_POST
def place_move(request, place_id: int):
    place = get_object_or_404(Place, id=place_id)

    # принимаем JSON {x:..., y:...}
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        payload = request.POST

    x = int(payload.get("x", 0))
    y = int(payload.get("y", 0))

    # ограничим чтобы не улетало в минус
    place.x = max(0, x)
    place.y = max(0, y)
    place.save(update_fields=["x", "y"])

    return JsonResponse({"ok": True, "x": place.x, "y": place.y})


@require_POST
def booking_set_status(request, booking_id: int, status: str):
    booking = get_object_or_404(Booking, id=booking_id)

    if status == "arrived":
        booking.status = Booking.Status.ARRIVED
        booking.save(update_fields=["status"])
        messages.success(request, _("Статус: гость пришёл ✅"))
    elif status == "free":
        booking.status = Booking.Status.DONE
        booking.ended_at = timezone.now()
        booking.save(update_fields=["status", "ended_at"])
        messages.success(request, _("Место освобождено ✅"))
    elif status == "cancel":
        booking.status = Booking.Status.CANCELED
        booking.ended_at = timezone.now()
        booking.save(update_fields=["status", "ended_at"])
        messages.success(request, _("Бронь отменена ✅"))
    else:
        messages.error(request, _("Неизвестный статус."))

    return redirect("public_site:hall_plan", branch_id=booking.branch_id)


@require_POST
def reserve_create(request, branch_id: int, place_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    place = get_object_or_404(Place, id=place_id, floor__branch=branch, is_active=True)

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    guests = int(request.POST.get("guests") or 2)
    guests = max(1, min(guests, 99))
    comment = (request.POST.get("comment") or "").strip()

    try:
        booking = Booking.create_active_booking(
            branch=branch,
            place=place,
            customer_name=name,
            customer_phone=phone,
            guests_count=guests,
            comment=comment,
        )
        notify_new_booking.delay(booking.id)  # ✅ телега
        messages.success(request, _("Бронь создана. Место занято до снятия кассиром/админом."))
    except ValueError as e:
        if str(e) == "PLACE_BUSY":
            messages.error(request, _("Это место уже занято. Выберите другое."))
        else:
            messages.error(request, _("Ошибка бронирования."))

    return redirect("public_site:hall_plan", branch_id=branch.id)


# @require_POST
# def reserve_create(request, branch_id: int, place_id: int):
#     branch = get_object_or_404(Branch, id=branch_id, is_active=True)
#     place = get_object_or_404(Place, id=place_id, floor__branch=branch, is_active=True)

#     name = (request.POST.get("name") or "").strip()
#     phone = (request.POST.get("phone") or "").strip()
#     guests = int(request.POST.get("guests") or 2)
#     guests = max(1, min(guests, 99))
#     comment = (request.POST.get("comment") or "").strip()

#     try:
#         booking = Booking.create_active_booking(
#             branch=branch,
#             place=place,
#             customer_name=name,
#             customer_phone=phone,
#             guests_count=guests,
#             comment=comment,
#         )

#         # ✅ телеграм уведомление
#         notify_new_booking.delay(booking.id)

#         messages.success(request, _("Бронь создана. Место занято до снятия кассиром/админом."))
#     except ValueError as e:
#         if str(e) == "PLACE_BUSY":
#             messages.error(request, _("Это место уже занято. Выберите другое."))
#         else:
#             messages.error(request, _("Ошибка бронирования."))

#     return redirect("public_site:reservation", branch_id=branch.id)
