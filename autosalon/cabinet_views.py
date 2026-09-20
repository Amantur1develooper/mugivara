import csv
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import AutoDealership, Car, CarPhoto, DealershipMembership, Lead

LOGIN_URL = "acabinet:login"
MAX_PHOTOS = 12


def _decimal(raw):
    raw = (raw or "").strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    return raw or None


def _int(raw):
    raw = (raw or "").strip()
    return int(raw) if raw.isdigit() else None


def _user_dealerships(user):
    if user.is_staff or user.is_superuser:
        return AutoDealership.objects.all()
    ids = DealershipMembership.objects.filter(user=user).values_list("dealership_id", flat=True)
    return AutoDealership.objects.filter(id__in=ids)


def _membership(user, dealership):
    return DealershipMembership.objects.filter(user=user, dealership=dealership).first()


def _check_access(user, dealership):
    if user.is_staff or user.is_superuser:
        return True
    return DealershipMembership.objects.filter(user=user, dealership=dealership).exists()


def _is_director(user, dealership):
    if user.is_staff or user.is_superuser:
        return True
    m = _membership(user, dealership)
    return bool(m and m.role == DealershipMembership.Role.DIRECTOR)


def _visible_cars(user, dealership):
    if _is_director(user, dealership):
        return dealership.cars.all()
    m = _membership(user, dealership)
    if m:
        return dealership.cars.filter(manager=m)
    return dealership.cars.none()


def _current_dealership(request):
    dealerships = _user_dealerships(request.user)
    dealership_id = request.session.get("as_dealership_id")
    if dealership_id:
        d = dealerships.filter(id=dealership_id).first()
        if d:
            return d, dealerships
    d = dealerships.first()
    if d:
        request.session["as_dealership_id"] = d.id
    return d, dealerships


# ── AUTH ─────────────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("acabinet:home")

    if request.method == "POST":
        user = authenticate(
            request,
            username=request.POST.get("username", "").strip(),
            password=request.POST.get("password", ""),
        )
        if user:
            login(request, user)
            return redirect("acabinet:home")
        messages.error(request, "Неверный логин или пароль")

    return render(request, "acabinet/login.html")


def logout_view(request):
    logout(request)
    return redirect("acabinet:login")


# ── ГЛАВНАЯ: склад машин сразу видно ────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def home(request):
    dealership, dealerships = _current_dealership(request)
    if not dealership:
        messages.error(request, "У вас нет доступа ни к одному автосалону.")
        return render(request, "acabinet/home.html", {"dealership": None})

    q = request.GET.get("q", "").strip()
    status_f = request.GET.get("status", "").strip()
    cars = _visible_cars(request.user, dealership).select_related("manager__user").prefetch_related("photos")
    if q:
        cars = cars.filter(Q(brand__icontains=q) | Q(model_name__icontains=q) | Q(vin__icontains=q))
    if status_f in dict(Car.Status.choices):
        cars = cars.filter(status=status_f)

    all_cars = _visible_cars(request.user, dealership)
    stock = {
        "available": all_cars.filter(status=Car.Status.AVAILABLE, is_active=True).count(),
        "reserved":  all_cars.filter(status=Car.Status.RESERVED, is_active=True).count(),
        "sold":      all_cars.filter(status=Car.Status.SOLD).count(),
        "total":     all_cars.filter(is_active=True).count(),
    }
    new_leads = Lead.objects.filter(dealership=dealership, status=Lead.Status.NEW).count()

    return render(request, "acabinet/home.html", {
        "dealership": dealership,
        "dealerships": dealerships,
        "cars": cars,
        "q": q, "status_f": status_f,
        "is_director": _is_director(request.user, dealership),
        "statuses": Car.Status.choices,
        "stock": stock,
        "new_leads": new_leads,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def switch_dealership(request, dealership_id):
    dealerships = _user_dealerships(request.user)
    if dealerships.filter(id=dealership_id).exists():
        request.session["as_dealership_id"] = dealership_id
    return redirect("acabinet:home")


# ── МАШИНЫ ───────────────────────────────────────────────────────────────────

def _fill_car_from_post(car, post, is_director, membership):
    car.brand         = post.get("brand", "").strip()
    car.model_name    = post.get("model_name", "").strip()
    car.generation    = post.get("generation", "").strip()
    car.year          = _int(post.get("year")) or car.year or timezone.now().year
    car.condition     = post.get("condition", Car.Condition.USED)
    car.body_type     = post.get("body_type", "").strip()
    car.mileage_km    = _int(post.get("mileage_km"))
    car.fuel_type     = post.get("fuel_type", "").strip()
    car.transmission  = post.get("transmission", "").strip()
    car.drive_type    = post.get("drive_type", "").strip()
    engine = _decimal(post.get("engine_volume"))
    car.engine_volume = Decimal(engine) if engine else None
    car.power_hp      = _int(post.get("power_hp"))
    car.color         = post.get("color", "").strip()
    car.vin           = post.get("vin", "").strip()
    car.price         = _decimal(post.get("price"))
    car.currency      = post.get("currency", Car.Currency.KGS)
    car.description   = post.get("description", "").strip()

    new_status = post.get("status", car.status)
    if new_status != car.status and new_status == Car.Status.SOLD:
        car.sold_at = timezone.now()
    elif new_status != Car.Status.SOLD:
        car.sold_at = None
    car.status = new_status

    if is_director:
        manager_id = post.get("manager_id")
        car.manager_id = int(manager_id) if manager_id and manager_id.isdigit() else None
    elif not car.pk:
        car.manager = membership
    return car


@login_required(login_url=LOGIN_URL)
def car_add(request, dealership_id):
    dealership = get_object_or_404(AutoDealership, id=dealership_id)
    if not _check_access(request.user, dealership):
        messages.error(request, "Нет доступа.")
        return redirect("acabinet:home")

    is_director = _is_director(request.user, dealership)
    membership = _membership(request.user, dealership)
    managers = DealershipMembership.objects.filter(dealership=dealership).select_related("user") if is_director else []

    if request.method == "POST":
        car = Car(dealership=dealership)
        _fill_car_from_post(car, request.POST, is_director, membership)
        car.save()
        for f in request.FILES.getlist("photos")[:MAX_PHOTOS]:
            CarPhoto.objects.create(car=car, photo=f)
        messages.success(request, "Автомобиль добавлен.")
        return redirect("acabinet:home")

    return render(request, "acabinet/car_form.html", {
        "dealership": dealership, "car": None, "Car": Car, "is_director": is_director, "managers": managers,
        "max_photos": MAX_PHOTOS,
    })


@login_required(login_url=LOGIN_URL)
def car_edit(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    dealership = car.dealership
    if not _check_access(request.user, dealership):
        messages.error(request, "Нет доступа.")
        return redirect("acabinet:home")

    is_director = _is_director(request.user, dealership)
    membership = _membership(request.user, dealership)
    if not is_director and car.manager_id != (membership.id if membership else None):
        messages.error(request, "Нет доступа к этому автомобилю.")
        return redirect("acabinet:home")

    managers = DealershipMembership.objects.filter(dealership=dealership).select_related("user") if is_director else []

    if request.method == "POST":
        _fill_car_from_post(car, request.POST, is_director, membership)
        car.save()

        for pid in request.POST.getlist("delete_photo"):
            CarPhoto.objects.filter(id=pid, car=car).delete()

        existing = car.photos.count()
        slots = max(0, MAX_PHOTOS - existing)
        for f in request.FILES.getlist("photos")[:slots]:
            CarPhoto.objects.create(car=car, photo=f)

        messages.success(request, "Автомобиль обновлён.")
        return redirect("acabinet:home")

    return render(request, "acabinet/car_form.html", {
        "dealership": dealership, "car": car, "Car": Car, "is_director": is_director, "managers": managers,
        "max_photos": MAX_PHOTOS,
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def car_status(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    dealership = car.dealership
    membership = _membership(request.user, dealership)
    if not _is_director(request.user, dealership) and car.manager_id != (membership.id if membership else None):
        return JsonResponse({"ok": False}, status=403)

    status = request.POST.get("status")
    if status not in Car.Status.values:
        return JsonResponse({"ok": False}, status=400)
    car.status = status
    car.sold_at = timezone.now() if status == Car.Status.SOLD else None
    car.save(update_fields=["status", "sold_at"])
    return JsonResponse({"ok": True, "status": car.status, "status_display": car.get_status_display()})


@require_POST
@login_required(login_url=LOGIN_URL)
def car_delete(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    dealership = car.dealership
    membership = _membership(request.user, dealership)
    if not _is_director(request.user, dealership) and car.manager_id != (membership.id if membership else None):
        messages.error(request, "Нет доступа к этому автомобилю.")
        return redirect("acabinet:home")
    car.delete()
    messages.success(request, "Автомобиль удалён.")
    return redirect("acabinet:home")


# ── ЛИДЫ ─────────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def leads(request):
    dealership, dealerships = _current_dealership(request)
    if not dealership:
        messages.error(request, "У вас нет доступа ни к одному автосалону.")
        return render(request, "acabinet/leads.html", {"dealership": None})

    status_f = request.GET.get("status", "").strip()
    qs = Lead.objects.filter(dealership=dealership).select_related("car", "manager__user")
    if status_f in dict(Lead.Status.choices):
        qs = qs.filter(status=status_f)

    status_tabs = [
        (val, label, Lead.objects.filter(dealership=dealership, status=val).count())
        for val, label in Lead.Status.choices
    ]

    return render(request, "acabinet/leads.html", {
        "dealership": dealership,
        "leads": qs,
        "status_f": status_f,
        "statuses": Lead.Status.choices,
        "status_tabs": status_tabs,
        "is_director": _is_director(request.user, dealership),
    })


@require_POST
@login_required(login_url=LOGIN_URL)
def lead_update(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id)
    if not _check_access(request.user, lead.dealership):
        return JsonResponse({"ok": False}, status=403)

    status = request.POST.get("status")
    if status and status in Lead.Status.values:
        lead.status = status
    if "note" in request.POST:
        lead.note = request.POST.get("note", "").strip()
    manager_id = request.POST.get("manager_id")
    if manager_id is not None:
        lead.manager_id = int(manager_id) if manager_id.isdigit() else None
    lead.save()
    return JsonResponse({"ok": True, "status": lead.status, "status_display": lead.get_status_display()})


# ── ОТЧЁТЫ ───────────────────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def reports(request):
    dealership, dealerships = _current_dealership(request)
    if not dealership:
        messages.error(request, "У вас нет доступа ни к одному автосалону.")
        return render(request, "acabinet/reports.html", {"dealership": None})

    try:
        days = int(request.GET.get("period", "30"))
    except (TypeError, ValueError):
        days = 30
    days = max(1, min(days, 365))
    now = timezone.now()
    since = now - timedelta(days=days)

    cars_all = Car.objects.filter(dealership=dealership)
    sold_period = cars_all.filter(status=Car.Status.SOLD, sold_at__gte=since)
    revenue = sold_period.aggregate(s=Sum("price"))["s"] or Decimal("0")

    leads_period = Lead.objects.filter(dealership=dealership, created_at__gte=since)
    leads_total = leads_period.count()
    leads_won = leads_period.filter(status=Lead.Status.WON).count()
    conversion = round(leads_won / leads_total * 100, 1) if leads_total else 0

    by_brand = (
        cars_all.filter(is_active=True, status=Car.Status.AVAILABLE)
        .values("brand").annotate(n=Count("id")).order_by("-n")[:8]
    )

    # аналитика просмотров (как у realestate) — по PageView
    import re
    from core.models import PageView
    slug_re = rf"/autosalon/{re.escape(dealership.slug)}(/|$)"
    pv = PageView.objects.filter(section="autosalon", path__regex=slug_re, timestamp__gte=since)
    total_views = pv.count()

    return render(request, "acabinet/reports.html", {
        "dealership": dealership,
        "is_director": _is_director(request.user, dealership),
        "period": days,
        "stock": {
            "available": cars_all.filter(status=Car.Status.AVAILABLE, is_active=True).count(),
            "reserved":  cars_all.filter(status=Car.Status.RESERVED, is_active=True).count(),
            "sold_total": cars_all.filter(status=Car.Status.SOLD).count(),
        },
        "sold_period_count": sold_period.count(),
        "revenue": revenue,
        "leads_total": leads_total,
        "leads_won": leads_won,
        "leads_by_status": {s: leads_period.filter(status=s).count() for s, _lbl in Lead.Status.choices},
        "conversion": conversion,
        "by_brand": by_brand,
        "total_views": total_views,
    })


@login_required(login_url=LOGIN_URL)
def reports_export_cars(request, dealership_id):
    dealership = get_object_or_404(AutoDealership, id=dealership_id)
    if not _check_access(request.user, dealership):
        messages.error(request, "Нет доступа.")
        return redirect("acabinet:home")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="cars_{dealership.slug}.csv"'
    response.write("﻿")  # BOM для корректной кириллицы в Excel
    writer = csv.writer(response)
    writer.writerow(["Марка", "Модель", "Год", "Состояние", "Пробег", "Цена", "Валюта", "Статус", "VIN", "Добавлена"])
    for c in _visible_cars(request.user, dealership).order_by("-created_at"):
        writer.writerow([
            c.brand, c.model_name, c.year, c.get_condition_display(),
            c.mileage_km or "", c.price or "", c.currency, c.get_status_display(),
            c.vin, c.created_at.strftime("%d.%m.%Y"),
        ])
    return response


@login_required(login_url=LOGIN_URL)
def reports_export_leads(request, dealership_id):
    dealership = get_object_or_404(AutoDealership, id=dealership_id)
    if not _check_access(request.user, dealership):
        messages.error(request, "Нет доступа.")
        return redirect("acabinet:home")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="leads_{dealership.slug}.csv"'
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(["Имя", "Телефон", "Автомобиль", "Статус", "Источник", "Сообщение", "Создан"])
    for l in Lead.objects.filter(dealership=dealership).select_related("car").order_by("-created_at"):
        writer.writerow([
            l.name, l.phone, str(l.car) if l.car else "", l.get_status_display(),
            l.get_source_display(), l.message, l.created_at.strftime("%d.%m.%Y %H:%M"),
        ])
    return response


# ── НАСТРОЙКИ АВТОСАЛОНА ─────────────────────────────────────────────────────

@login_required(login_url=LOGIN_URL)
def dealership_settings(request, dealership_id):
    dealership = get_object_or_404(AutoDealership, id=dealership_id)
    if not _is_director(request.user, dealership):
        messages.error(request, "Настройки автосалона доступны только директору.")
        return redirect("acabinet:home")

    if request.method == "POST":
        dealership.name       = request.POST.get("name", dealership.name).strip()
        dealership.phone      = request.POST.get("phone", "").strip()
        dealership.city       = request.POST.get("city", "").strip()
        dealership.address    = request.POST.get("address", "").strip()
        dealership.work_hours = request.POST.get("work_hours", "").strip()
        dealership.description = request.POST.get("description", "").strip()

        if "logo" in request.FILES:
            dealership.logo = request.FILES["logo"]
        elif request.POST.get("logo_clear"):
            dealership.logo = None

        if "cover" in request.FILES:
            dealership.cover = request.FILES["cover"]
        elif request.POST.get("cover_clear"):
            dealership.cover = None

        dealership.save()
        messages.success(request, "Настройки автосалона обновлены.")
        return redirect("acabinet:dealership_settings", dealership_id=dealership.id)

    return render(request, "acabinet/dealership_settings.html", {"dealership": dealership})
