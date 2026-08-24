from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages

from .models import RealtyAgency, RealtyMembership, Apartment, ApartmentPhoto

LOGIN_URL = "rcabinet:login"
MAX_PHOTOS = 10


def _user_agencies(user):
    if user.is_staff or user.is_superuser:
        return RealtyAgency.objects.all()
    ids = RealtyMembership.objects.filter(user=user).values_list("agency_id", flat=True)
    return RealtyAgency.objects.filter(id__in=ids)


def _membership(user, agency):
    return RealtyMembership.objects.filter(user=user, agency=agency).first()


def _check_access(user, agency):
    if user.is_staff or user.is_superuser:
        return True
    return RealtyMembership.objects.filter(user=user, agency=agency).exists()


def _is_director(user, agency):
    if user.is_staff or user.is_superuser:
        return True
    m = _membership(user, agency)
    return bool(m and m.role == RealtyMembership.Role.DIRECTOR)


def _visible_apartments(user, agency):
    if _is_director(user, agency):
        return agency.apartments.all()
    m = _membership(user, agency)
    if m:
        return agency.apartments.filter(realtor=m)
    return agency.apartments.none()


# ── AUTH ─────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("rcabinet:home")

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user:
            login(request, user)
            return redirect("rcabinet:home")
        messages.error(request, "Неверный логин или пароль")

    return render(request, "rcabinet/login.html")


def logout_view(request):
    logout(request)
    return redirect("rcabinet:login")


# ── ГЛАВНАЯ ──────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def home(request):
    agencies = _user_agencies(request.user)
    agency = agencies.first()
    if not agency:
        messages.error(request, "У вас нет доступа ни к одному агентству.")
        return render(request, "rcabinet/home.html", {"agency": None, "apartments": []})

    apartments = _visible_apartments(request.user, agency).select_related("realtor__user").prefetch_related("photos")
    return render(request, "rcabinet/home.html", {
        "agency": agency,
        "apartments": apartments,
        "is_director": _is_director(request.user, agency),
        "statuses": Apartment.Status.choices,
    })


# ── КВАРТИРЫ ─────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def apartment_add(request, agency_id):
    agency = get_object_or_404(RealtyAgency, id=agency_id)
    if not _check_access(request.user, agency):
        messages.error(request, "Нет доступа.")
        return redirect("rcabinet:home")

    is_director = _is_director(request.user, agency)
    membership = _membership(request.user, agency)
    realtors = RealtyMembership.objects.filter(agency=agency).select_related("user") if is_director else []

    if request.method == "POST":
        apt = Apartment(agency=agency)
        apt.city          = request.POST.get("city", "").strip()
        apt.district      = request.POST.get("district", "").strip()
        apt.address       = request.POST.get("address", "").strip()
        area              = request.POST.get("area", "").strip()
        apt.area          = area or None
        rooms             = request.POST.get("rooms", "").strip()
        apt.rooms         = int(rooms) if rooms.isdigit() else None
        floor             = request.POST.get("floor", "").strip()
        apt.floor         = int(floor) if floor.isdigit() else None
        floors_total      = request.POST.get("floors_total", "").strip()
        apt.floors_total  = int(floors_total) if floors_total.isdigit() else None
        apt.renovation    = request.POST.get("renovation", "").strip()
        price             = request.POST.get("price", "").strip()
        apt.price         = price or None
        apt.status        = request.POST.get("status", Apartment.Status.FREE)
        apt.description   = request.POST.get("description", "").strip()
        apt.review_url_1  = request.POST.get("review_url_1", "").strip()
        apt.review_url_2  = request.POST.get("review_url_2", "").strip()

        if is_director:
            realtor_id = request.POST.get("realtor_id")
            apt.realtor_id = int(realtor_id) if realtor_id and realtor_id.isdigit() else None
        else:
            apt.realtor = membership

        apt.save()
        for f in request.FILES.getlist("photos")[:MAX_PHOTOS]:
            ApartmentPhoto.objects.create(apartment=apt, photo=f)
        messages.success(request, "Квартира добавлена.")
        return redirect("rcabinet:home")

    return render(request, "rcabinet/apartment_form.html", {
        "agency": agency, "apartment": None, "is_director": is_director, "realtors": realtors,
        "max_photos": MAX_PHOTOS,
    })


@login_required(login_url=LOGIN_URL)
def apartment_edit(request, apartment_id):
    apt = get_object_or_404(Apartment, id=apartment_id)
    agency = apt.agency
    if not _check_access(request.user, agency):
        messages.error(request, "Нет доступа.")
        return redirect("rcabinet:home")

    is_director = _is_director(request.user, agency)
    membership = _membership(request.user, agency)
    if not is_director and apt.realtor_id != (membership.id if membership else None):
        messages.error(request, "Нет доступа к этой квартире.")
        return redirect("rcabinet:home")

    realtors = RealtyMembership.objects.filter(agency=agency).select_related("user") if is_director else []

    if request.method == "POST":
        apt.city          = request.POST.get("city", "").strip()
        apt.district      = request.POST.get("district", "").strip()
        apt.address       = request.POST.get("address", "").strip()
        area              = request.POST.get("area", "").strip()
        apt.area          = area or None
        rooms             = request.POST.get("rooms", "").strip()
        apt.rooms         = int(rooms) if rooms.isdigit() else None
        floor             = request.POST.get("floor", "").strip()
        apt.floor         = int(floor) if floor.isdigit() else None
        floors_total      = request.POST.get("floors_total", "").strip()
        apt.floors_total  = int(floors_total) if floors_total.isdigit() else None
        apt.renovation    = request.POST.get("renovation", "").strip()
        price             = request.POST.get("price", "").strip()
        apt.price         = price or None
        apt.status        = request.POST.get("status", apt.status)
        apt.description   = request.POST.get("description", "").strip()
        apt.review_url_1  = request.POST.get("review_url_1", "").strip()
        apt.review_url_2  = request.POST.get("review_url_2", "").strip()

        if is_director:
            realtor_id = request.POST.get("realtor_id")
            apt.realtor_id = int(realtor_id) if realtor_id and realtor_id.isdigit() else None

        apt.save()

        for pid in request.POST.getlist("delete_photo"):
            ApartmentPhoto.objects.filter(id=pid, apartment=apt).delete()

        existing = apt.photos.count()
        slots = max(0, MAX_PHOTOS - existing)
        for f in request.FILES.getlist("photos")[:slots]:
            ApartmentPhoto.objects.create(apartment=apt, photo=f)

        messages.success(request, "Квартира обновлена.")
        return redirect("rcabinet:home")

    return render(request, "rcabinet/apartment_form.html", {
        "agency": agency, "apartment": apt, "is_director": is_director, "realtors": realtors,
        "max_photos": MAX_PHOTOS,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def apartment_status(request, apartment_id):
    apt = get_object_or_404(Apartment, id=apartment_id)
    agency = apt.agency
    membership = _membership(request.user, agency)
    if not _is_director(request.user, agency) and apt.realtor_id != (membership.id if membership else None):
        return JsonResponse({"ok": False}, status=403)

    status = request.POST.get("status")
    if status not in Apartment.Status.values:
        return JsonResponse({"ok": False}, status=400)
    apt.status = status
    apt.save(update_fields=["status"])
    return JsonResponse({"ok": True, "status": apt.status, "status_display": apt.get_status_display()})


@require_POST
@login_required(login_url=LOGIN_URL)
def apartment_delete(request, apartment_id):
    apt = get_object_or_404(Apartment, id=apartment_id)
    agency = apt.agency
    membership = _membership(request.user, agency)
    if not _is_director(request.user, agency) and apt.realtor_id != (membership.id if membership else None):
        messages.error(request, "Нет доступа к этой квартире.")
        return redirect("rcabinet:home")
    apt.delete()
    messages.success(request, "Квартира удалена.")
    return redirect("rcabinet:home")
