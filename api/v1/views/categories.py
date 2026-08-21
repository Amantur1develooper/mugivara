from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

from core.models import PlaceCategory, Restaurant, Branch
from shops.models import Store
from hotels.models import Hotel
from pharmacy.models import Pharmacy
from markets.models import Market
from legal.models import LegalOrg
from eco.models import EcoProject
from agency.models import Agency
from barbershop.models import Barbershop
from printshop.models import PrintCenter
from karaoke.models import KaraokeVenue
from simracing.models import SimRacingVenue

from api.v1.serializers import (
    PlaceCategorySerializer, RestaurantSerializer, BranchSerializer,
)


# ── Реестр всех типов заведений платформы ──────────────────────────────────
# ключ — код типа, отдаётся в поле place_type; значение — (модель, related_name филиалов или None)
PLACE_TYPES = {
    "restaurant": (Restaurant, "branches"),
    "store":      (Store, "branches"),
    "hotel":      (Hotel, "branches"),
    "pharmacy":   (Pharmacy, "branches"),
    "printshop":  (PrintCenter, "branches"),
    "market":     (Market, None),
    "legal":      (LegalOrg, None),
    "eco":        (EcoProject, None),
    "agency":     (Agency, None),
    "barbershop": (Barbershop, None),
    "karaoke":    (KaraokeVenue, None),
    "simracing":  (SimRacingVenue, None),
}

def _category_place_item_serializer(**kwargs):
    return inline_serializer(
        name="CategoryPlaceItem",
        fields={
            "id":             serializers.IntegerField(),
            "place_type":     serializers.CharField(help_text="Тип заведения: restaurant, store, hotel, pharmacy, printshop, market, legal, eco, agency, barbershop, karaoke, simracing"),
            "slug":           serializers.SlugField(),
            "name_ru":        serializers.CharField(),
            "name_ky":        serializers.CharField(),
            "name_en":        serializers.CharField(),
            "logo_url":       serializers.URLField(allow_null=True),
            "cover_url":      serializers.URLField(allow_null=True),
            "rating":         serializers.DecimalField(max_digits=3, decimal_places=1, allow_null=True),
            "address":        serializers.CharField(),
            "phone":          serializers.CharField(),
            "branches_count": serializers.IntegerField(),
            "is_open_now":    serializers.BooleanField(),
        },
        **kwargs,
    )


def _abs(request, field):
    if field and request:
        try:
            return request.build_absolute_uri(field.url)
        except ValueError:
            return None
    return None


def _place_name(obj):
    """(name_ru, name_ky, name_en) независимо от того, есть у модели локали или одно поле name."""
    if hasattr(obj, "name_ru"):
        return obj.name_ru or "", getattr(obj, "name_ky", "") or "", getattr(obj, "name_en", "") or ""
    return getattr(obj, "name", "") or "", "", ""


def _place_to_dict(obj, place_type: str, request) -> dict:
    _, branches_rel = PLACE_TYPES[place_type]
    name_ru, name_ky, name_en = _place_name(obj)

    branches_count = 0
    is_open_now = False
    if branches_rel:
        branches_qs = getattr(obj, branches_rel).filter(is_active=True)
        branches_count = branches_qs.count()
        is_open_now = any(
            b.is_open_now() for b in branches_qs if hasattr(b, "is_open_now")
        )

    return {
        "id": obj.id,
        "place_type": place_type,
        "slug": obj.slug,
        "name_ru": name_ru,
        "name_ky": name_ky,
        "name_en": name_en,
        "logo_url": _abs(request, getattr(obj, "logo", None)),
        "cover_url": _abs(request, getattr(obj, "cover", None)),
        "rating": getattr(obj, "rating", None),
        "address": getattr(obj, "address", "") or "",
        "phone": getattr(obj, "phone", "") or "",
        "branches_count": branches_count,
        "is_open_now": is_open_now,
    }


def _find_place(category, place_slug: str):
    """Ищет заведение с данным slug среди всех 12 типов. Возвращает (obj, place_type) или (None, None)."""
    for place_type, (model, _rel) in PLACE_TYPES.items():
        obj = model.objects.filter(
            slug=place_slug, place_category=category, is_active=True
        ).first()
        if obj:
            return obj, place_type
    return None, None


@extend_schema(
    summary="Список категорий платформы",
    description=(
        "Возвращает все активные категории (Еда, Отели, Магазины, …) с флагами поведения. "
        "Приложение строит главный экран и навигацию на основе этих данных — "
        "добавление новой категории в админке сразу отражается у всех пользователей."
    ),
    responses={200: PlaceCategorySerializer(many=True)},
    tags=["Категории"],
)
@api_view(["GET"])
def category_list(request):
    qs = PlaceCategory.objects.filter(is_active=True).order_by("sort_order", "id")
    return Response(PlaceCategorySerializer(qs, many=True).data)


@extend_schema(
    summary="Заведения категории",
    description=(
        "Список всех активных заведений в данной категории платформы — по всем типам бизнеса "
        "(рестораны, магазины, отели, аптеки, рынки, юристы, эко-проекты, IT-агентства, "
        "барбершопы, полиграфия, караоке, симрейсинг). Тип конкретного заведения указан в поле "
        "place_type — используйте его вместе со slug для запроса деталей."
    ),
    responses={200: _category_place_item_serializer(many=True)},
    tags=["Категории"],
)
@api_view(["GET"])
def category_places(request, slug: str):
    category = get_object_or_404(PlaceCategory, slug=slug, is_active=True)

    results = []
    for place_type, (model, _rel) in PLACE_TYPES.items():
        qs = model.objects.filter(place_category=category, is_active=True)
        results.extend(_place_to_dict(obj, place_type, request) for obj in qs)

    results.sort(key=lambda r: (-(float(r["rating"]) if r["rating"] else -1)))
    return Response(results)


@extend_schema(
    summary="Детали заведения (через категорию)",
    description=(
        "Полные данные заведения. Для ресторанов отдаётся расширенная форма (контакты, соцсети, "
        "рейтинг); для остальных типов бизнеса — единая облегчённая форма (см. CategoryPlaceItem), "
        "т.к. у них разная структура (адрес прямо на организации, филиалов может не быть)."
    ),
    responses={200: RestaurantSerializer},
    tags=["Категории"],
)
@api_view(["GET"])
def category_place_detail(request, slug: str, place_slug: str):
    category = get_object_or_404(PlaceCategory, slug=slug, is_active=True)
    obj, place_type = _find_place(category, place_slug)
    if obj is None:
        raise Http404

    if place_type == "restaurant":
        return Response(RestaurantSerializer(obj, context={"request": request}).data)
    return Response(_place_to_dict(obj, place_type, request))


@extend_schema(
    summary="Филиалы заведения (через категорию)",
    description=(
        "Список активных филиалов заведения. Не у всех типов бизнеса есть филиалы (юристы, "
        "эко-проекты, агентства, барбершопы, караоке, симрейсинг, рынки — это единичные "
        "организации) — для них отдаётся пустой список, контакты смотрите в деталях заведения."
    ),
    responses={200: BranchSerializer(many=True)},
    tags=["Категории"],
)
@api_view(["GET"])
def category_place_branches(request, slug: str, place_slug: str):
    category = get_object_or_404(PlaceCategory, slug=slug, is_active=True)
    obj, place_type = _find_place(category, place_slug)
    if obj is None:
        raise Http404

    if place_type == "restaurant":
        qs = Branch.objects.filter(restaurant=obj, is_active=True)
        return Response(BranchSerializer(qs, many=True, context={"request": request}).data)

    _, branches_rel = PLACE_TYPES[place_type]
    if not branches_rel:
        return Response([])

    branches = getattr(obj, branches_rel).filter(is_active=True)
    data = [
        {
            "id": b.id,
            "address": getattr(b, "address", "") or "",
            "phone": getattr(b, "phone", "") or "",
            "is_active": getattr(b, "is_active", True),
        }
        for b in branches
    ]
    return Response(data)
