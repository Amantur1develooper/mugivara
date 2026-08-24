import json
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.shortcuts import render, get_object_or_404

from .models import RealtyAgency, Apartment


def agency_list(request):
    agencies = RealtyAgency.objects.filter(is_active=True)
    return render(request, "realestate/agency_list.html", {"agencies": agencies})


def agency_detail(request, slug):
    agency = get_object_or_404(RealtyAgency, slug=slug, is_active=True)
    q = request.GET.get("q", "").strip()
    apartments = agency.apartments.filter(is_active=True).exclude(
        status=Apartment.Status.SOLD
    ).prefetch_related("photos")
    if q:
        filters = Q(address__icontains=q) | Q(district__icontains=q) | Q(city__icontains=q)
        try:
            filters |= Q(area=Decimal(q.replace(",", ".")))
        except (InvalidOperation, ValueError):
            pass
        apartments = apartments.filter(filters)
    return render(request, "realestate/agency_detail.html", {"agency": agency, "apartments": apartments, "q": q})


def apartment_detail(request, slug, apartment_id):
    agency = get_object_or_404(RealtyAgency, slug=slug, is_active=True)
    apartment = get_object_or_404(Apartment, id=apartment_id, agency=agency, is_active=True)
    photo_urls = [p.photo.url for p in apartment.photos.all()]
    return render(request, "realestate/apartment_detail.html", {
        "agency": agency, "apartment": apartment,
        "photo_urls_json": json.dumps(photo_urls),
    })
