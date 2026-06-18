from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from core.models import Branch
from catalog.models import BranchCategory, BranchCategoryItem, DishConstructor
from api.v1.serializers import (
    BranchMenuSerializer, MenuCategorySerializer,
    MenuItemSerializer, DishConstructorSerializer,
)


@extend_schema(
    summary="Полное меню филиала",
    description=(
        "Возвращает все активные категории и позиции меню для указанного филиала. "
        "Только доступные (is_available=True) блюда."
    ),
    responses={200: BranchMenuSerializer},
    tags=["Меню"],
)
@api_view(["GET"])
def branch_menu(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)

    branch_cats = (
        BranchCategory.objects
        .select_related("category")
        .filter(branch=branch, is_active=True)
        .order_by("sort_order", "id")
    )

    categories = []
    for bc in branch_cats:
        bcis = (
            BranchCategoryItem.objects
            .select_related("branch_item__item")
            .filter(branch_category=bc, branch_item__is_available=True)
            .order_by("sort_order", "id")
        )
        items = [bci.branch_item for bci in bcis]

        categories.append({
            "category_id":      bc.category_id,
            "category_name_ru": bc.category.name_ru,
            "category_name_ky": bc.category.name_ky,
            "category_name_en": bc.category.name_en,
            "items":            items,
        })

    data = {
        "branch_id":   branch.id,
        "branch_name": branch.name_ru,
        "categories":  categories,
    }
    serializer = BranchMenuSerializer(data, context={"request": request})
    return Response(serializer.data)


@extend_schema(
    summary="Конструкторы блюд филиала",
    description=(
        "Возвращает все активные конструкторы ('Собери сам') с группами и ингредиентами. "
        "Используется для интерактивного сборщика блюд в приложении."
    ),
    responses={200: DishConstructorSerializer(many=True)},
    tags=["Меню"],
)
@api_view(["GET"])
def branch_constructors(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    qs = (
        DishConstructor.objects
        .prefetch_related("groups__ingredients")
        .filter(branch=branch, is_active=True)
        .order_by("sort_order", "id")
    )
    serializer = DishConstructorSerializer(qs, many=True, context={"request": request})
    return Response(serializer.data)
