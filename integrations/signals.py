from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from orders.models import Order  # проверь импорт
from integrations.tasks import notify_new_order

@receiver(post_save, sender=Order)
def order_created(sender, instance: Order, created: bool, **kwargs):
    if not created:
        return
    transaction.on_commit(lambda: notify_new_order.delay(instance.id))
