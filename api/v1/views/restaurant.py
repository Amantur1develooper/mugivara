from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter

from core.models import Restaurant, Branch, Banner
from api.v1.serializers import RestaurantSerializer, BranchSerializer, BannerSerializer


@extend_schema(
    summary="Список ресторанов",
    description="Возвращает все активные рестораны.",
    responses={200: RestaurantSerializer(many=True)},
    tags=["Рестораны"],
)
@api_view(["GET"])
def restaurant_list(request):
    qs = Restaurant.objects.filter(is_active=True).order_by("-rating", "id")
    serializer = RestaurantSerializer(qs, many=True, context={"request": request})
    return Response(serializer.data)


@extend_schema(
    summary="Детали ресторана",
    description="Возвращает один ресторан по slug.",
    responses={200: RestaurantSerializer},
    tags=["Рестораны"],
)
@api_view(["GET"])
def restaurant_detail(request, slug: str):
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    serializer = RestaurantSerializer(restaurant, context={"request": request})
    return Response(serializer.data)


@extend_schema(
    summary="Филиалы ресторана",
    description="Список всех активных филиалов конкретного ресторана.",
    responses={200: BranchSerializer(many=True)},
    tags=["Рестораны"],
)
@api_view(["GET"])
def branch_list(request, slug: str):
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    qs = Branch.objects.filter(restaurant=restaurant, is_active=True)
    serializer = BranchSerializer(qs, many=True, context={"request": request})
    return Response(serializer.data)


@extend_schema(
    summary="Детали филиала",
    description="Возвращает информацию о филиале: адрес, часы работы, is_open_now, настройки доставки.",
    responses={200: BranchSerializer},
    tags=["Рестораны"],
)
@api_view(["GET"])
def branch_detail(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    serializer = BranchSerializer(branch, context={"request": request})
    return Response(serializer.data)


@extend_schema(
    summary="Баннеры главного экрана",
    description="Активные промо-баннеры для слайдера.",
    responses={200: BannerSerializer(many=True)},
    tags=["Главная"],
)
@api_view(["GET"])
def banner_list(request):
    qs = Banner.objects.filter(is_active=True).order_by("sort_order")
    serializer = BannerSerializer(qs, many=True, context={"request": request})
    return Response(serializer.data)
