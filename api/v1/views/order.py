from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiExample, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from catalog.models import BranchItem
from core.models import Branch, PromoCode
from orders.models import Order, OrderItem


# ── Схемы для документации ────────────────────────────────────────────────────

_DeliveryOrderRequest = inline_serializer("DeliveryOrderRequest", fields={
    "type": serializers.ChoiceField(
        choices=["delivery", "pickup"],
        help_text="delivery — доставка, pickup — самовывоз",
    ),
    "items": serializers.ListField(
        child=inline_serializer("DeliveryItemInput", fields={
            "branch_item_id": serializers.IntegerField(),
            "qty":            serializers.IntegerField(min_value=1),
        })
    ),
    "customer_name":    serializers.CharField(help_text="Имя получателя"),
    "customer_phone":   serializers.CharField(help_text="Телефон получателя"),
    "delivery_address": serializers.CharField(
        required=False, allow_blank=True,
        help_text="Адрес доставки (обязателен при type=delivery)",
    ),
    "payment_method": serializers.ChoiceField(
        choices=["cash", "online"], default="cash",
    ),
    "comment":    serializers.CharField(required=False, allow_blank=True),
    "promo_code": serializers.CharField(
        required=False, allow_blank=True,
        help_text="Промокод (необязательно)",
    ),
})

_DeliveryOrderResponse = inline_serializer("DeliveryOrderResponse", fields={
    "order_id":      serializers.IntegerField(),
    "status":        serializers.CharField(),
    "type":          serializers.CharField(),
    "subtotal":      serializers.DecimalField(max_digits=10, decimal_places=2),
    "delivery_fee":  serializers.DecimalField(max_digits=10, decimal_places=2),
    "discount":      serializers.DecimalField(max_digits=10, decimal_places=2),
    "total":         serializers.DecimalField(max_digits=10, decimal_places=2),
    "promo_applied": serializers.BooleanField(),
    "promo_message": serializers.CharField(),
})

_PromoCheckRequest = inline_serializer("PromoCheckRequest", fields={
    "code":       serializers.CharField(),
    "cart_total": serializers.DecimalField(max_digits=10, decimal_places=2),
})

_PromoCheckResponse = inline_serializer("PromoCheckResponse", fields={
    "valid":          serializers.BooleanField(),
    "discount_type":  serializers.CharField(),
    "discount_value": serializers.DecimalField(max_digits=10, decimal_places=2),
    "discount_amount": serializers.DecimalField(max_digits=10, decimal_places=2),
    "message":        serializers.CharField(),
})


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _calc_promo(promo: PromoCode, subtotal: Decimal, delivery_fee: Decimal):
    """Возвращает (discount, new_delivery_fee, message)."""
    if promo.discount_type == PromoCode.DiscountType.FREE_DELIVERY:
        return Decimal("0"), Decimal("0"), "Доставка бесплатна"
    if promo.discount_type == PromoCode.DiscountType.PERCENT:
        discount = (subtotal * promo.discount_value / 100).quantize(Decimal("1"))
        return discount, delivery_fee, f"Скидка {promo.discount_value}%"
    if promo.discount_type == PromoCode.DiscountType.FIXED:
        discount = min(promo.discount_value, subtotal)
        return discount, delivery_fee, f"Скидка {promo.discount_value} сом"
    return Decimal("0"), delivery_fee, ""


# ── Views ─────────────────────────────────────────────────────────────────────

@extend_schema(
    summary="Создать заказ (доставка / самовывоз)",
    description=(
        "Создаёт заказ типа **delivery** (доставка) или **pickup** (самовывоз). \n\n"
        "- При `type=delivery` поле `delivery_address` обязательно.\n"
        "- Промокод применяется автоматически если передан и действителен.\n"
        "- Стоимость доставки берётся из настроек филиала (`delivery_fee`). "
        "Если сумма заказа >= `free_delivery_from` — доставка бесплатна.\n"
        "- После создания заказ отправляется на кухонный принтер (если настроен)."
    ),
    request=_DeliveryOrderRequest,
    responses={
        201: _DeliveryOrderResponse,
        400: inline_serializer("DeliveryValidationError", fields={"detail": serializers.CharField()}),
        404: inline_serializer("DeliveryNotFound",        fields={"detail": serializers.CharField()}),
    },
    examples=[
        OpenApiExample(
            "Доставка с промокодом",
            value={
                "type":             "delivery",
                "items":            [{"branch_item_id": 12, "qty": 2}],
                "customer_name":    "Айгуль",
                "customer_phone":   "+996700123456",
                "delivery_address": "ул. Токтогула 123, кв. 45",
                "payment_method":   "cash",
                "promo_code":       "SUMMER10",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Самовывоз",
            value={
                "type":           "pickup",
                "items":          [{"branch_item_id": 7, "qty": 1}],
                "customer_name":  "Бакыт",
                "customer_phone": "+996555987654",
                "payment_method": "online",
            },
            request_only=True,
        ),
        OpenApiExample(
            "Ответ",
            value={
                "order_id": 112, "status": "new", "type": "delivery",
                "subtotal": "1200.00", "delivery_fee": "0.00",
                "discount": "120.00", "total": "1080.00",
                "promo_applied": True, "promo_message": "Скидка 10%",
            },
            response_only=True,
        ),
    ],
    tags=["Заказы"],
)
@api_view(["POST"])
def branch_order_create(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)

    order_type = request.data.get("type", "")
    if order_type not in ("delivery", "pickup"):
        return Response(
            {"detail": "Поле type должно быть 'delivery' или 'pickup'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    customer_name  = request.data.get("customer_name", "").strip()
    customer_phone = request.data.get("customer_phone", "").strip()
    if not customer_name or not customer_phone:
        return Response(
            {"detail": "Поля customer_name и customer_phone обязательны."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    delivery_address = request.data.get("delivery_address", "").strip()
    if order_type == "delivery" and not delivery_address:
        return Response(
            {"detail": "Для доставки поле delivery_address обязательно."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    payment_method = request.data.get("payment_method", "cash")
    if payment_method not in ("cash", "online"):
        return Response(
            {"detail": "payment_method должен быть 'cash' или 'online'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    rows = request.data.get("items", [])
    if not rows:
        return Response(
            {"detail": "Список блюд пустой."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Валидируем блюда до транзакции
    validated = []
    for row in rows:
        try:
            bi  = BranchItem.objects.select_related("item").get(
                id=row["branch_item_id"], branch=branch, is_available=True,
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

    # Считаем сумму заказа
    subtotal = sum(bi.price * qty for bi, qty in validated)

    # Стоимость доставки
    if order_type == "delivery" and branch.delivery_enabled:
        if branch.free_delivery_from and subtotal >= branch.free_delivery_from:
            delivery_fee = Decimal("0")
        else:
            delivery_fee = branch.delivery_fee or Decimal("0")
    else:
        delivery_fee = Decimal("0")

    # Промокод
    promo_applied  = False
    promo_message  = ""
    discount       = Decimal("0")
    promo_code_str = request.data.get("promo_code", "").strip()
    promo_obj      = None

    if promo_code_str:
        try:
            promo_obj = PromoCode.objects.get(
                branch=branch, code__iexact=promo_code_str,
            )
            valid, msg = promo_obj.is_valid()
            if valid:
                discount, delivery_fee, promo_message = _calc_promo(
                    promo_obj, subtotal, delivery_fee,
                )
                promo_applied = True
            else:
                promo_message = msg
        except PromoCode.DoesNotExist:
            promo_message = "Промокод не найден."

    total = subtotal + delivery_fee - discount
    if total < 0:
        total = Decimal("0")

    with transaction.atomic():
        order = Order.objects.create(
            branch=branch,
            type=order_type,
            status=Order.Status.NEW,
            customer_name=customer_name,
            customer_phone=customer_phone,
            delivery_address=delivery_address,
            payment_method=payment_method,
            payment_status=Order.PaymentStatus.UNPAID,
            comment=request.data.get("comment", ""),
            delivery_fee=delivery_fee,
            total_amount=total,
        )

        order_items = [
            OrderItem(
                order=order,
                item=bi.item,
                qty=qty,
                price_snapshot=bi.price,
                line_total=bi.price * qty,
            )
            for bi, qty in validated
        ]
        OrderItem.objects.bulk_create(order_items)

        # Списываем использование промокода
        if promo_applied and promo_obj:
            PromoCode.objects.filter(pk=promo_obj.pk).update(
                used_count=promo_obj.used_count + 1
            )

    # Печать на кухне
    try:
        from printing.jobs import create_print_jobs
        _oid = order.id
        def _do_print_order():
            try:
                from orders.models import Order as _Ord
                create_print_jobs(
                    _Ord.objects
                    .select_related("table_place__floor", "branch__restaurant")
                    .get(id=_oid)
                )
            except Exception as e:
                import traceback
                print("PRINT create_print_jobs ERROR (order-api):", e)
                traceback.print_exc()
        transaction.on_commit(_do_print_order)
    except Exception:
        pass

    return Response(
        {
            "order_id":      order.id,
            "status":        order.status,
            "type":          order.type,
            "subtotal":      str(subtotal),
            "delivery_fee":  str(delivery_fee),
            "discount":      str(discount),
            "total":         str(total),
            "promo_applied": promo_applied,
            "promo_message": promo_message,
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    summary="Проверить промокод",
    description=(
        "Проверяет промокод без создания заказа. "
        "Используется для мгновенного отображения скидки в корзине."
    ),
    request=_PromoCheckRequest,
    responses={
        200: _PromoCheckResponse,
        404: inline_serializer("PromoNotFound", fields={"detail": serializers.CharField()}),
    },
    examples=[
        OpenApiExample(
            "Запрос", value={"code": "SUMMER10", "cart_total": "1500.00"},
            request_only=True,
        ),
        OpenApiExample(
            "Ответ — скидка 10%",
            value={"valid": True, "discount_type": "percent", "discount_value": "10.00",
                   "discount_amount": "150.00", "message": "Скидка 10%"},
            response_only=True,
        ),
        OpenApiExample(
            "Ответ — промокод недействителен",
            value={"valid": False, "discount_type": "", "discount_value": "0.00",
                   "discount_amount": "0.00", "message": "Срок действия промокода истёк"},
            response_only=True,
        ),
    ],
    tags=["Заказы"],
)
@api_view(["POST"])
def promo_check(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)

    code = request.data.get("code", "").strip()
    if not code:
        return Response({"detail": "Поле code обязательно."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        cart_total = Decimal(str(request.data.get("cart_total", "0")))
    except Exception:
        return Response({"detail": "cart_total должен быть числом."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        promo = PromoCode.objects.get(branch=branch, code__iexact=code)
    except PromoCode.DoesNotExist:
        return Response({"detail": "Промокод не найден."}, status=status.HTTP_404_NOT_FOUND)

    valid, message = promo.is_valid()

    discount_amount = Decimal("0")
    if valid:
        if promo.discount_type == PromoCode.DiscountType.PERCENT:
            discount_amount = (cart_total * promo.discount_value / 100).quantize(Decimal("1"))
            message = f"Скидка {promo.discount_value}%"
        elif promo.discount_type == PromoCode.DiscountType.FIXED:
            discount_amount = min(promo.discount_value, cart_total)
            message = f"Скидка {promo.discount_value} сом"
        elif promo.discount_type == PromoCode.DiscountType.FREE_DELIVERY:
            message = "Доставка бесплатна"

    return Response({
        "valid":           valid,
        "discount_type":   promo.discount_type if valid else "",
        "discount_value":  str(promo.discount_value) if valid else "0.00",
        "discount_amount": str(discount_amount),
        "message":         message,
    })
