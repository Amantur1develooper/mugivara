from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.models import Branch, PromoCode, Banner


# ── Схемы ─────────────────────────────────────────────────────────────────────

_PromoSchema = inline_serializer("PromoCard", fields={
    "id":             serializers.IntegerField(),
    "code":           serializers.CharField(),
    "discount_type":  serializers.CharField(
        help_text="free_delivery | percent | fixed"
    ),
    "discount_value": serializers.DecimalField(max_digits=10, decimal_places=2),
    "valid_until":    serializers.DateField(allow_null=True),
    "description":    serializers.CharField(
        help_text="Человекочитаемое описание скидки"
    ),
})

_BannerSchema = inline_serializer("BannerCard", fields={
    "id":              serializers.IntegerField(),
    "title":           serializers.CharField(),
    "image_mobile_url": serializers.URLField(allow_null=True),
    "image_wide_url":   serializers.URLField(allow_null=True),
    "link_url":        serializers.CharField(allow_blank=True),
    "sort_order":      serializers.IntegerField(),
})


def _promo_description(promo: PromoCode) -> str:
    if promo.discount_type == PromoCode.DiscountType.FREE_DELIVERY:
        return "Бесплатная доставка"
    if promo.discount_type == PromoCode.DiscountType.PERCENT:
        return f"Скидка {promo.discount_value:.0f}%"
    if promo.discount_type == PromoCode.DiscountType.FIXED:
        return f"Скидка {promo.discount_value:.0f} сом"
    return ""


# ── Views ─────────────────────────────────────────────────────────────────────

@extend_schema(
    summary="Активные промокоды филиала",
    description=(
        "Публичный список действующих промокодов для отображения в приложении "
        "(например, на экране корзины или промо-странице). "
        "Просроченные и исчерпанные промокоды не возвращаются."
    ),
    responses={200: _PromoSchema},
    tags=["Промокоды и баннеры"],
)
@api_view(["GET"])
def branch_promos(request, branch_id: int):
    branch = get_object_or_404(Branch, id=branch_id, is_active=True)
    today  = timezone.localdate()

    qs = PromoCode.objects.filter(branch=branch, is_active=True).order_by("id")

    result = []
    for promo in qs:
        # Фильтруем просроченные и исчерпанные
        if promo.valid_until and promo.valid_until < today:
            continue
        if promo.max_uses > 0 and promo.used_count >= promo.max_uses:
            continue
        result.append({
            "id":             promo.id,
            "code":           promo.code,
            "discount_type":  promo.discount_type,
            "discount_value": str(promo.discount_value),
            "valid_until":    promo.valid_until,
            "description":    _promo_description(promo),
        })

    return Response(result)


@extend_schema(
    summary="Баннеры главного экрана",
    description=(
        "Активные промо-баннеры для слайдера. "
        "Возвращает URL для трёх форматов: mobile (850px), wide (2560px). "
        "Клик по баннеру открывает `link_url`."
    ),
    responses={200: _BannerSchema},
    tags=["Промокоды и баннеры"],
)
@api_view(["GET"])
def banner_list(request):
    banners = Banner.objects.filter(is_active=True).order_by("sort_order")

    def img_url(field):
        return request.build_absolute_uri(field.url) if field else None

    return Response([
        {
            "id":               b.id,
            "title":            b.title,
            "image_mobile_url": img_url(b.image_mobile),
            "image_wide_url":   img_url(b.image_wide),
            "link_url":         b.link_url or "",
            "sort_order":       b.sort_order,
        }
        for b in banners
    ])


@extend_schema(
    summary="Зарегистрировать клик по баннеру",
    description="Увеличивает счётчик кликов баннера на 1. Вызывается когда пользователь тапает на баннер.",
    request=None,
    responses={200: inline_serializer("BannerClickResponse", fields={
        "clicked": serializers.BooleanField(),
        "detail":  serializers.CharField(required=False),
    })},
    tags=["Промокоды и баннеры"],
)
@api_view(["POST"])
def banner_click(request, banner_id: int):
    from django.db.models import F
    updated = Banner.objects.filter(id=banner_id, is_active=True).update(
        click_count=F("click_count") + 1
    )
    if not updated:
        return Response({"detail": "Баннер не найден."}, status=404)
    return Response({"clicked": True})
