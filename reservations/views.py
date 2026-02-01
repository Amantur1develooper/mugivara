from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.translation import gettext as _
from core.models import Branch
from .models import Floor, Place, Booking
from reservations.tasks import notify_new_booking

def reservation_page(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id)
    floors = Floor.objects.filter(branch=branch, is_active=True).order_by("sort_order","id").prefetch_related("places")

    busy_ids = set(
    Booking.objects.filter(branch=branch, status=Booking.Status.ACTIVE)
    .values_list("place_id", flat=True)
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
        Booking.create_active_booking(
            branch=branch,
            place=place,
            customer_name=name,
            customer_phone=phone,
            guests_count=guests,
            comment=comment,
        )
        messages.success(request, _("Бронь создана. Место занято до снятия кассиром/админом."))
    except ValueError as e:
        if str(e) == "PLACE_BUSY":
            messages.error(request, _("Это место уже занято. Выберите другое."))
        else:
            messages.error(request, _("Ошибка бронирования."))
    booking = Booking.create_active_booking(...)
    notify_new_booking.delay(booking.id)
    # messages.success(...)
    return redirect("public_site:reservation", branch_id=branch.id)
