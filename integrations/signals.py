import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Case, When
from django.db.models.signals import post_save
from django.dispatch import receiver

from orders.models import Order
from integrations.tasks import notify_new_order

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def order_created(sender, instance: Order, created: bool, **kwargs):
    if not created:
        return

    def _on_commit():
        # 1. TG-уведомление
        try:
            notify_new_order.delay(instance.id)
        except Exception as e:
            logger.error("notify_new_order failed for order %s: %s", instance.id, e)

        # 2. Обновляем order_count и rating для каждого блюда в заказе
        try:
            from catalog.models import Item
            # Уникальные item_id в заказе (каждый +1 раз, независимо от qty)
            item_ids = list(instance.items.values_list("item_id", flat=True).distinct())
            if item_ids:
                # order_count += qty (сколько штук продано)
                for row in instance.items.values("item_id", "qty"):
                    Item.objects.filter(pk=row["item_id"]).update(
                        order_count=F("order_count") + row["qty"]
                    )
                # rating += 0.1 за каждый заказ, cap = 5.0
                Item.objects.filter(pk__in=item_ids).update(
                    rating=Case(
                        When(rating__lt=Decimal("4.9"),
                             then=F("rating") + Decimal("0.1")),
                        default=Decimal("5.0"),
                    )
                )
        except Exception as e:
            logger.error("rating update failed for order %s: %s", instance.id, e)

    transaction.on_commit(_on_commit)
