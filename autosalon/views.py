import json
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST

from .models import AutoDealership, Car, Lead


def dealership_list(request):
    dealerships = (
        AutoDealership.objects.filter(is_active=True)
        .prefetch_related("cars")
    )
    return render(request, "autosalon/dealership_list.html", {"dealerships": dealerships})


def dealership_detail(request, slug):
    dealership = get_object_or_404(AutoDealership, slug=slug, is_active=True)
    cars = dealership.cars.filter(is_active=True).exclude(status=Car.Status.HIDDEN).prefetch_related("photos")

    q = request.GET.get("q", "").strip()
    brand = request.GET.get("brand", "").strip()
    condition = request.GET.get("condition", "").strip()
    body_type = request.GET.get("body", "").strip()
    price_max = request.GET.get("price_max", "").strip()

    if q:
        cars = cars.filter(Q(brand__icontains=q) | Q(model_name__icontains=q) | Q(generation__icontains=q))
    if brand:
        cars = cars.filter(brand=brand)
    if condition in dict(Car.Condition.choices):
        cars = cars.filter(condition=condition)
    if body_type in dict(Car.BodyType.choices):
        cars = cars.filter(body_type=body_type)
    if price_max:
        try:
            cars = cars.filter(price__lte=Decimal(price_max))
        except InvalidOperation:
            pass

    brands = (
        dealership.cars.filter(is_active=True).exclude(status=Car.Status.HIDDEN)
        .order_by("brand").values_list("brand", flat=True).distinct()
    )

    return render(request, "autosalon/dealership_detail.html", {
        "dealership": dealership,
        "cars": cars,
        "brands": brands,
        "body_types": Car.BodyType.choices,
        "q": q, "brand": brand, "condition": condition, "body_type": body_type, "price_max": price_max,
    })


def car_detail(request, slug, car_id):
    dealership = get_object_or_404(AutoDealership, slug=slug, is_active=True)
    car = get_object_or_404(Car, id=car_id, dealership=dealership, is_active=True)
    photo_urls = [p.photo.url for p in car.photos.all()]
    similar = (
        dealership.cars.filter(is_active=True, brand=car.brand)
        .exclude(id=car.id).exclude(status=Car.Status.HIDDEN)
        .prefetch_related("photos")[:4]
    )
    return render(request, "autosalon/car_detail.html", {
        "dealership": dealership, "car": car,
        "photo_urls_json": json.dumps(photo_urls),
        "similar": similar,
    })


@require_POST
def lead_create(request, slug, car_id=None):
    dealership = get_object_or_404(AutoDealership, slug=slug, is_active=True)
    car = None
    if car_id:
        car = get_object_or_404(Car, id=car_id, dealership=dealership)

    name = (request.POST.get("name") or "").strip()
    phone = (request.POST.get("phone") or "").strip()
    message = (request.POST.get("message") or "").strip()

    if not phone:
        messages.error(request, "Укажите номер телефона")
    else:
        Lead.objects.create(
            dealership=dealership, car=car, name=name, phone=phone, message=message,
            source=Lead.Source.CAR_PAGE if car else Lead.Source.DEALERSHIP,
        )
        messages.success(request, "Заявка отправлена! Мы свяжемся с вами в ближайшее время.")

    if car:
        return redirect("autosalon:car_detail", slug=slug, car_id=car.id)
    return redirect("autosalon:dealership_detail", slug=slug)
