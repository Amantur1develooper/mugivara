from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from orders.models import Order, OrderItem, ConstructorOrderItem
from core.models import UserProfile


# ── Схемы ─────────────────────────────────────────────────────────────────────

_OrderItemSchema = inline_serializer("HistoryOrderItem", fields={
    "type":       serializers.ChoiceField(choices=["dish", "constructor"],
                                          help_text="dish — обычное блюдо, constructor — собери сам"),
    "item_id":    serializers.IntegerField(help_text="BranchItem.item_id для dish, DishConstructor.id для constructor"),
    "name":       serializers.CharField(),
    "qty":        serializers.IntegerField(),
    "price":      serializers.DecimalField(max_digits=10, decimal_places=2),
    "line_total": serializers.DecimalField(max_digits=10, decimal_places=2),
    "selections": serializers.ListField(
        child=serializers.DictField(),
        allow_null=True,
        required=False,
        help_text="null для dish; [{gname, ings:[{name,extra_price}]}] для constructor",
    ),
})

_OrderSchema = inline_serializer("HistoryOrder", fields={
    "id":               serializers.IntegerField(),
    "type":             serializers.CharField(),
    "type_label":       serializers.CharField(),
    "status":           serializers.CharField(),
    "status_label":     serializers.CharField(),
    "branch_id":        serializers.IntegerField(),
    "branch_name":      serializers.CharField(),
    "restaurant_name":  serializers.CharField(),
    "subtotal":         serializers.DecimalField(max_digits=10, decimal_places=2),
    "delivery_fee":     serializers.DecimalField(max_digits=10, decimal_places=2),
    "total":            serializers.DecimalField(max_digits=10, decimal_places=2),
    "payment_method":   serializers.CharField(),
    "delivery_address": serializers.CharField(),
    "comment":          serializers.CharField(),
    "created_at":       serializers.DateTimeField(),
    "items": serializers.ListField(child=_OrderItemSchema),
})

_STATUS_LABELS = {
    Order.Status.NEW:       "Принят",
    Order.Status.ACCEPTED:  "Подтверждён",
    Order.Status.COOKING:   "Готовится",
    Order.Status.READY:     "Готов",
    Order.Status.CLOSED:    "Закрыт",
    Order.Status.CANCELLED: "Отменён",
}

_TYPE_LABELS = {
    Order.Type.DINE_IN:  "В заведении",
    Order.Type.DELIVERY: "Доставка",
    Order.Type.PICKUP:   "Самовывоз",
}


def _serialize_order(order):
    items_data = [
        {
            "type":       "dish",
            "item_id":    oi.item_id,
            "name":       oi.item.name_ru,
            "qty":        oi.qty,
            "price":      str(oi.price_snapshot),
            "line_total": str(oi.line_total),
            "selections": None,
        }
        for oi in order.items.select_related("item").all()
    ]
    for coi in order.constructor_items.all():
        items_data.append({
            "type":       "constructor",
            "item_id":    coi.constructor_id,
            "name":       coi.constructor_name_snapshot,
            "qty":        coi.qty,
            "price":      str(coi.unit_price),
            "line_total": str(coi.line_total),
            "selections": coi.ingredients_snapshot or [],
        })
    return {
        "id":               order.id,
        "type":             order.type,
        "type_label":       _TYPE_LABELS.get(order.type, order.type),
        "status":           order.status,
        "status_label":     _STATUS_LABELS.get(order.status, order.status),
        "branch_id":        order.branch_id,
        "branch_name":      order.branch.name_ru,
        "restaurant_name":  order.branch.restaurant.name_ru,
        "subtotal":         str(order.total_amount - (order.delivery_fee or 0)),
        "delivery_fee":     str(order.delivery_fee or 0),
        "total":            str(order.total_amount),
        "payment_method":   order.payment_method,
        "delivery_address": order.delivery_address or "",
        "comment":          order.comment or "",
        "created_at":       order.created_at,
        "items":            items_data,
    }


# ── Views ─────────────────────────────────────────────────────────────────────

@extend_schema(
    summary="История заказов",
    description=(
        "Возвращает все заказы текущего пользователя (по номеру телефона). "
        "Отсортированы от новых к старым. Требует авторизации."
    ),
    parameters=[
        OpenApiParameter(
            "status", str, OpenApiParameter.QUERY, required=False,
            description="Фильтр по статусу: new / accepted / cooking / ready / closed / cancelled",
        ),
        OpenApiParameter(
            "type", str, OpenApiParameter.QUERY, required=False,
            description="Фильтр по типу: dine_in / delivery / pickup",
        ),
        OpenApiParameter(
            "limit", int, OpenApiParameter.QUERY, required=False,
            description="Количество заказов на страницу (по умолчанию 20)",
        ),
        OpenApiParameter(
            "offset", int, OpenApiParameter.QUERY, required=False,
            description="Смещение для пагинации",
        ),
    ],
    responses={
        200: inline_serializer("OrderHistoryResponse", fields={
            "count":   serializers.IntegerField(),
            "results": serializers.ListField(child=_OrderSchema),
        }),
        401: inline_serializer("Unauthorized", fields={"detail": serializers.CharField()}),
    },
    tags=["История заказов"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_history(request):
    try:
        phone = request.user.profile.phone
    except UserProfile.DoesNotExist:
        return Response({"count": 0, "results": []})

    qs = (
        Order.objects
        .select_related("branch__restaurant")
        .prefetch_related("constructor_items")
        .filter(customer_phone=phone)
        .order_by("-created_at")
    )

    # Фильтры
    status_filter = request.query_params.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)

    type_filter = request.query_params.get("type")
    if type_filter:
        qs = qs.filter(type=type_filter)

    # Пагинация
    try:
        limit  = max(1, min(int(request.query_params.get("limit",  20)), 100))
        offset = max(0, int(request.query_params.get("offset", 0)))
    except (ValueError, TypeError):
        limit, offset = 20, 0

    total = qs.count()
    page  = qs[offset: offset + limit]

    return Response({
        "count":   total,
        "results": [_serialize_order(o) for o in page],
    })


@extend_schema(
    summary="Детали заказа",
    description=(
        "Возвращает полную информацию об одном заказе. "
        "Доступен только владельцу заказа (по номеру телефона)."
    ),
    responses={
        200: _OrderSchema,
        403: inline_serializer("Forbidden",   fields={"detail": serializers.CharField()}),
        404: inline_serializer("OrderNotFound", fields={"detail": serializers.CharField()}),
    },
    tags=["История заказов"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_detail(request, order_id: int):
    try:
        phone = request.user.profile.phone
    except UserProfile.DoesNotExist:
        return Response({"detail": "Профиль не найден."}, status=404)

    order = get_object_or_404(
        Order.objects.select_related("branch__restaurant").prefetch_related("constructor_items"),
        id=order_id,
    )

    if order.customer_phone != phone:
        return Response({"detail": "Нет доступа к этому заказу."}, status=403)

    return Response(_serialize_order(order))
