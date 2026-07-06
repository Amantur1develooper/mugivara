from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiExample, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from catalog.models import BranchCategory, BranchCategoryItem, BranchItem
from orders.models import Order, OrderItem
from tables.models import Table, TableSession
from api.v1.serializers import MenuCategorySerializer


# ── Схемы для документации ────────────────────────────────────────────────────

_QrMenuResponse = inline_serializer("QrMenuResponse", fields={
    "branch_id":   serializers.IntegerField(),
    "branch_name": serializers.CharField(),
    "table_id":    serializers.IntegerField(),
    "table_number": serializers.IntegerField(),
    "categories":  MenuCategorySerializer(many=True),
})

_OrderCreateRequest = inline_serializer("QrOrderCreateRequest", fields={
    "items": serializers.ListField(
        child=inline_serializer("OrderItemInput", fields={
            "branch_item_id": serializers.IntegerField(),
            "qty":            serializers.IntegerField(min_value=1),
        })
    ),
    "customer_name": serializers.CharField(required=False, allow_blank=True),
    "comment":       serializers.CharField(required=False, allow_blank=True),
})

_OrderCreateResponse = inline_serializer("QrOrderCreateResponse", fields={
    "order_id":  serializers.IntegerField(),
    "total":     serializers.DecimalField(max_digits=10, decimal_places=2),
    "status":    serializers.CharField(),
    "table":     serializers.IntegerField(),
    "branch_id": serializers.IntegerField(),
})

_OrderStatusResponse = inline_serializer("QrOrderStatusResponse", fields={
    "order_id":     serializers.IntegerField(),
    "status":       serializers.CharField(),
    "status_label": serializers.CharField(),
    "total":        serializers.DecimalField(max_digits=10, decimal_places=2),
    "items": serializers.ListField(
        child=inline_serializer("OrderStatusItem", fields={
            "name":  serializers.CharField(),
            "qty":   serializers.IntegerField(),
            "price": serializers.DecimalField(max_digits=10, decimal_places=2),
            "total": serializers.DecimalField(max_digits=10, decimal_places=2),
        })
    ),
})


# ── Views ─────────────────────────────────────────────────────────────────────

@extend_schema(
    summary="Меню стола по QR-токену",
    description=(
        "Сканирование QR-кода стола. Возвращает название ресторана, номер стола "
        "и полное меню с категориями. Используется как начальный экран после сканирования QR."
    ),
    responses={
        200: _QrMenuResponse,
        404: inline_serializer("QrMenuNotFound", fields={"detail": serializers.CharField()}),
    },
    tags=["QR-стол"],
)
@api_view(["GET"])
def qr_menu(request, token: str):
    table  = get_object_or_404(Table, qr_token=token)
    branch = table.branch

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
        if not items:
            continue
        categories.append({
            "category_id":       bc.category_id,
            "category_name_ru":  bc.category.name_ru,
            "category_name_ky":  bc.category.name_ky,
            "category_name_en":  bc.category.name_en,
            "items":             items,
        })

    return Response({
        "branch_id":    branch.id,
        "branch_name":  branch.name_ru,
        "table_id":     table.id,
        "table_number": table.number,
        "categories":   MenuCategorySerializer(
            categories, many=True, context={"request": request}
        ).data,
    })


@extend_schema(
    summary="Создать заказ со стола (QR)",
    description=(
        "Гость отправляет список блюд и количество. "
        "Создаётся заказ типа dine_in, открывается сессия стола. "
        "После создания заказ сразу отправляется на кухонный принтер (если настроен)."
    ),
    request=_OrderCreateRequest,
    responses={
        201: _OrderCreateResponse,
        400: inline_serializer("QrOrderValidationError", fields={"detail": serializers.CharField()}),
        404: inline_serializer("QrOrderNotFound",        fields={"detail": serializers.CharField()}),
    },
    examples=[
        OpenApiExample(
            "Пример запроса",
            value={
                "items": [
                    {"branch_item_id": 12, "qty": 2},
                    {"branch_item_id": 37, "qty": 1},
                ],
                "customer_name": "Азамат",
                "comment": "Без лука в бургере",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Пример ответа",
            value={"order_id": 105, "total": "1450.00", "status": "new",
                   "table": 3, "branch_id": 2},
            response_only=True,
        ),
    ],
    tags=["QR-стол"],
)
@api_view(["POST"])
def qr_order_create(request, token: str):
    table  = get_object_or_404(Table, qr_token=token)
    branch = table.branch

    rows = request.data.get("items", [])
    if not rows:
        return Response({"detail": "Список блюд пустой."}, status=status.HTTP_400_BAD_REQUEST)

    # Валидируем все позиции заранее, до начала транзакции
    validated = []
    for row in rows:
        try:
            bi  = BranchItem.objects.select_related("item").get(
                id=row["branch_item_id"], branch=branch, is_available=True
            )
            qty = int(row.get("qty", 1))
            if qty < 1:
                raise ValueError
        except (BranchItem.DoesNotExist, KeyError, ValueError, TypeError):
            return Response(
                {"detail": f"Позиция branch_item_id={row.get('branch_item_id')} недоступна."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        validated.append((bi, qty))

    with transaction.atomic():
        session, _ = TableSession.objects.get_or_create(
            table=table,
            status=TableSession.Status.OPEN,
        )

        order = Order.objects.create(
            branch=branch,
            type=Order.Type.DINE_IN,
            status=Order.Status.NEW,
            table_session=session,
            customer_name=request.data.get("customer_name", ""),
            comment=request.data.get("comment", ""),
        )

        total = Decimal("0")
        order_items = []
        for bi, qty in validated:
            line = bi.price * qty
            total += line
            order_items.append(OrderItem(
                order=order,
                item=bi.item,
                qty=qty,
                price_snapshot=bi.price,
                line_total=line,
            ))

        OrderItem.objects.bulk_create(order_items)
        order.total_amount = total
        order.save(update_fields=["total_amount"])

    # Печать на кухне (вне транзакции, чтобы не тормозить ответ)
    try:
        from printing.jobs import create_print_jobs
        from django.db import transaction as tx
        _oid = order.id
        def _do_print_qr():
            try:
                from orders.models import Order as _Ord
                create_print_jobs(
                    _Ord.objects
                    .select_related("table_place__floor", "branch__restaurant")
                    .get(id=_oid)
                )
            except Exception as e:
                import traceback
                print("PRINT create_print_jobs ERROR (qr-api):", e)
                traceback.print_exc()
        tx.on_commit(_do_print_qr)
    except Exception:
        pass

    return Response(
        {
            "order_id":  order.id,
            "total":     str(order.total_amount),
            "status":    order.status,
            "table":     table.number,
            "branch_id": branch.id,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    summary="Статус заказа (polling)",
    description=(
        "Мобильное приложение периодически опрашивает этот эндпоинт "
        "чтобы показать гостю текущий статус заказа (принят / готовится / готов)."
    ),
    responses={
        200: _OrderStatusResponse,
        404: inline_serializer("NotFound", fields={"detail": serializers.CharField()}),
    },
    tags=["QR-стол"],
)
@api_view(["GET"])
def qr_order_status(request, order_id: int):
    order = get_object_or_404(
        Order.objects.prefetch_related("items__item"),
        id=order_id,
    )

    status_labels = {
        Order.Status.NEW:       "Принят",
        Order.Status.ACCEPTED:  "Подтверждён",
        Order.Status.COOKING:   "Готовится",
        Order.Status.READY:     "Готов",
        Order.Status.CLOSED:    "Закрыт",
        Order.Status.CANCELLED: "Отменён",
    }

    items_data = [
        {
            "name":  oi.item.name_ru,
            "qty":   oi.qty,
            "price": str(oi.price_snapshot),
            "total": str(oi.line_total),
        }
        for oi in order.items.select_related("item").all()
    ]

    return Response({
        "order_id":     order.id,
        "status":       order.status,
        "status_label": status_labels.get(order.status, order.status),
        "total":        str(order.total_amount),
        "items":        items_data,
    })
