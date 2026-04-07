import logging

from django.db import transaction
from django.db.models import F
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

        # 2. Увеличиваем рейтинг блюд на количество заказанных единиц
        try:
            from catalog.models import Item
            items = list(instance.items.values("item_id", "qty"))
            for row in items:
                Item.objects.filter(pk=row["item_id"]).update(
                    order_count=F("order_count") + row["qty"]
                )
        except Exception as e:
            logger.error("order_count update failed for order %s: %s", instance.id, e)

    transaction.on_commit(_on_commit)
