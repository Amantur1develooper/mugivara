"""Единая логика применения промокодов ко всем каналам заказа
(онлайн-доставка, касса/POS, столы по QR)."""
from decimal import Decimal

from django.db.models import F

from core.models import PromoCode


def resolve_promo(branch, code, subtotal, delivery_fee=Decimal("0"), *,
                  allow_free_delivery=True):
    """Проверяет промокод и считает скидку.

    Возвращает кортеж (promo | None, discount: Decimal, delivery_fee: Decimal, label: str).
    discount — скидка на позиции (в сомах). delivery_fee может обнулиться для
    «бесплатной доставки». label — короткая строка для чека/Telegram.
    Ничего не сохраняет и НЕ увеличивает счётчик использований — это делает вызывающий
    код после успешного создания заказа (через bump_promo_use).
    """
    code = (code or "").strip().upper()
    delivery_fee = Decimal(delivery_fee or 0)
    if not code:
        return None, Decimal("0"), delivery_fee, ""

    try:
        promo = PromoCode.objects.get(branch=branch, code=code)
    except PromoCode.DoesNotExist:
        return None, Decimal("0"), delivery_fee, ""

    ok, _ = promo.is_valid()
    if not ok:
        return None, Decimal("0"), delivery_fee, ""

    subtotal = Decimal(subtotal or 0)
    discount = Decimal("0")

    if promo.discount_type == PromoCode.DiscountType.FREE_DELIVERY:
        if allow_free_delivery:
            delivery_fee = Decimal("0")
        label = f"{promo.code}: бесплатная доставка"
    elif promo.discount_type == PromoCode.DiscountType.PERCENT:
        discount = (subtotal * promo.discount_value / Decimal("100")).quantize(Decimal("1"))
        discount = min(discount, subtotal)
        label = f"{promo.code}: −{int(promo.discount_value)}% (−{int(discount)} сом)"
    else:  # FIXED
        discount = min(promo.discount_value, subtotal)
        label = f"{promo.code}: −{int(discount)} сом"

    return promo, discount, delivery_fee, label


def bump_promo_use(promo):
    """Атомарно увеличивает счётчик использований промокода."""
    if promo:
        PromoCode.objects.filter(pk=promo.pk).update(used_count=F("used_count") + 1)
