"""
Единая точка расчёта «цены товара сейчас» с учётом акций (StorePromotion).

Используется и публичной витриной, и корзиной/оформлением заказа, и кассой —
чтобы цена со скидкой везде совпадала и не расходилась по местам (по тому же
принципу, что и constructor_utils.py — одна логика, а не 5 копий).
"""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from .models import StorePromotion


class PromoResolver:
    """Считает лучшую (максимальную) активную скидку на сегодня для магазина,
    один раз на запрос — дальше просто словарный lookup без новых запросов к БД."""

    def __init__(self, store, today_weekday=None):
        self.all_percent = 0
        self.cat_percent = {}
        weekday = date.today().weekday() if today_weekday is None else today_weekday

        promos = (
            StorePromotion.objects
            .filter(store=store, is_active=True, weekday=weekday)
            .prefetch_related("categories")
        )
        for p in promos:
            if p.apply_to_all:
                self.all_percent = max(self.all_percent, p.discount_percent)
            else:
                for cat in p.categories.all():
                    self.cat_percent[cat.id] = max(self.cat_percent.get(cat.id, 0), p.discount_percent)

    def percent_for(self, category_id) -> int:
        return max(self.all_percent, self.cat_percent.get(category_id, 0))

    def price_for(self, product) -> tuple[Decimal, int]:
        """Возвращает (итоговая_цена, процент_скидки). Если скидки нет — (price, 0)."""
        pct = self.percent_for(product.category_id)
        price = Decimal(str(product.price or 0))
        if not pct:
            return price, 0
        discounted = (price * (Decimal(100) - pct) / Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return discounted, pct

    @property
    def has_any(self) -> bool:
        return bool(self.all_percent or self.cat_percent)
