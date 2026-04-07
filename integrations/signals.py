import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from orders.models import Order
from integrations.tasks import notify_new_order

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order)
def order_created(sender, instance: Order, created: bool, **kwargs):
    if not created:
        return

    def _send():
        try:
            notify_new_order.delay(instance.id)
        except Exception as e:
            # Celery/Redis недоступен — логируем, но заказ уже сохранён
            logger.error("notify_new_order failed for order %s: %s", instance.id, e)

    transaction.on_commit(_send)
