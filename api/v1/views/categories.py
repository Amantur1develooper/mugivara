from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

from core.models import PlaceCategory, Restaurant, Branch
from api.v1.serializers import (
    PlaceCategorySerializer, PlaceListSerializer,
    RestaurantSerializer, BranchSerializer,
)


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
    description="Список всех активных заведений в данной категории платформы.",
    responses={200: PlaceListSerializer(many=True)},
    tags=["Категории"],
)
@api_view(["GET"])
def category_places(request, slug: str):
    category = get_object_or_404(PlaceCategory, slug=slug, is_active=True)
    qs = (
        Restaurant.objects
        .filter(place_category=category, is_active=True)
        .prefetch_related("branches")
        .order_by("-rating", "id")
    )
    return Response(PlaceListSerializer(qs, many=True, context={"request": request}).data)


@extend_schema(
    summary="Детали заведения (через категорию)",
    description="Полные данные заведения: контакты, соцсети, рейтинг, количество филиалов.",
    responses={200: RestaurantSerializer},
    tags=["Категории"],
)
@api_view(["GET"])
def category_place_detail(request, slug: str, place_slug: str):
    category = get_object_or_404(PlaceCategory, slug=slug, is_active=True)
    place = get_object_or_404(
        Restaurant, slug=place_slug, place_category=category, is_active=True
    )
    return Response(RestaurantSerializer(place, context={"request": request}).data)


@extend_schema(
    summary="Филиалы заведения (через категорию)",
    description="Список активных филиалов заведения с адресами, часами работы и настройками доставки.",
    responses={200: BranchSerializer(many=True)},
    tags=["Категории"],
)
@api_view(["GET"])
def category_place_branches(request, slug: str, place_slug: str):
    category = get_object_or_404(PlaceCategory, slug=slug, is_active=True)
    place = get_object_or_404(
        Restaurant, slug=place_slug, place_category=category, is_active=True
    )
    qs = Branch.objects.filter(restaurant=place, is_active=True)
    return Response(BranchSerializer(qs, many=True, context={"request": request}).data)
