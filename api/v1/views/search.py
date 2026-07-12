from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from drf_spectacular.openapi import OpenApiTypes
from rest_framework import serializers
from django.db.models import Q

from core.models import Restaurant, Branch
from catalog.models import BranchItem
from api.v1.serializers import PlaceListSerializer, MenuItemSerializer


_SearchResponse = inline_serializer("SearchResponse", fields={
    "places": serializers.ListField(child=inline_serializer("SearchPlace", fields={
        "id":                  serializers.IntegerField(),
        "slug":                serializers.CharField(),
        "name_ru":             serializers.CharField(),
        "name_ky":             serializers.CharField(),
        "name_en":             serializers.CharField(),
        "logo_url":            serializers.URLField(allow_null=True),
        "cover_url":           serializers.URLField(allow_null=True),
        "rating":              serializers.DecimalField(max_digits=3, decimal_places=1, allow_null=True),
        "branches_count":      serializers.IntegerField(),
        "is_open_now":         serializers.BooleanField(),
        "place_category_slug": serializers.CharField(allow_null=True),
    })),
    "items": serializers.ListField(child=inline_serializer("SearchItem", fields={
        "id":                  serializers.IntegerField(),
        "item_id":             serializers.IntegerField(),
        "name_ru":             serializers.CharField(),
        "name_ky":             serializers.CharField(),
        "name_en":             serializers.CharField(),
        "description":         serializers.CharField(),
        "photo_url":           serializers.URLField(allow_null=True),
        "price":               serializers.DecimalField(max_digits=10, decimal_places=2),
        "is_available":        serializers.BooleanField(),
        "rating":              serializers.DecimalField(max_digits=3, decimal_places=1),
        "orders_count":        serializers.IntegerField(),
        "branch_id":           serializers.IntegerField(),
        "branch_name_ru":      serializers.CharField(),
        "branch_name_ky":      serializers.CharField(),
        "branch_name_en":      serializers.CharField(),
        "place_category_slug": serializers.CharField(allow_null=True),
    })),
})


@extend_schema(
    summary="Поиск по платформе",
    description=(
        "Подстрочный поиск по названию заведений и позиций меню/каталога. "
        "Возвращает до 50 заведений и 50 позиций. "
        "Параметр `q` обязателен."
    ),
    parameters=[
        OpenApiParameter("q", OpenApiTypes.STR, description="Поисковый запрос", required=True),
        OpenApiParameter("category", OpenApiTypes.STR, description="Фильтр по slug категории", required=False),
    ],
    responses={200: _SearchResponse},
    tags=["Поиск"],
)
@api_view(["GET"])
def search(request):
    q = request.query_params.get("q", "").strip()
    if not q:
        return Response(
            {"detail": "Параметр q обязателен."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cat_slug = request.query_params.get("category", "").strip()

    # ── Заведения ────────────────────────────────────────────────────────────
    place_qs = Restaurant.objects.filter(
        is_active=True,
    ).filter(
        Q(name_ru__icontains=q) | Q(name_ky__icontains=q) | Q(name_en__icontains=q)
    ).prefetch_related("branches").select_related("place_category")

    if cat_slug:
        place_qs = place_qs.filter(place_category__slug=cat_slug)

    place_qs = place_qs.order_by("-rating", "id")[:50]

    places_data = PlaceListSerializer(
        place_qs, many=True, context={"request": request}
    ).data
    # добавляем place_category_slug в каждый элемент
    places_list = []
    for idx, place in enumerate(place_qs):
        row = dict(places_data[idx])
        row["place_category_slug"] = place.place_category.slug if place.place_category_id else None
        places_list.append(row)

    # ── Позиции меню/каталога ─────────────────────────────────────────────────
    item_qs = (
        BranchItem.objects
        .select_related("item", "branch__restaurant__place_category")
        .filter(
            is_available=True,
            branch__is_active=True,
            branch__restaurant__is_active=True,
        ).filter(
            Q(item__name_ru__icontains=q)
            | Q(item__name_ky__icontains=q)
            | Q(item__name_en__icontains=q)
            | Q(item__description_ru__icontains=q)
        )
    )

    if cat_slug:
        item_qs = item_qs.filter(branch__restaurant__place_category__slug=cat_slug)

    item_qs = item_qs.order_by("-item__order_count", "id")[:50]

    items_base = MenuItemSerializer(item_qs, many=True, context={"request": request}).data
    items_list = []
    for idx, bi in enumerate(item_qs):
        row = dict(items_base[idx])
        row["branch_id"]           = bi.branch_id
        row["branch_name_ru"]      = bi.branch.name_ru
        row["branch_name_ky"]      = bi.branch.name_ky
        row["branch_name_en"]      = bi.branch.name_en
        row["place_category_slug"] = (
            bi.branch.restaurant.place_category.slug
            if bi.branch.restaurant.place_category_id else None
        )
        items_list.append(row)

    return Response({"places": places_list, "items": items_list})
