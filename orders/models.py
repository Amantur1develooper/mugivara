from django.db import models
# orders/models.py
from reservations.models import Place
from django.db import models
from core.models import Branch, TimeStampedModel
from tables.models import TableSession
from catalog.models import Item

class Order(TimeStampedModel):
    class Type(models.TextChoices):
        DINE_IN = "dine_in", "В заведении"
        DELIVERY = "delivery", "Доставка"
        PICKUP = "pickup", "Самовывоз"

    class Status(models.TextChoices):
        NEW = "new", "Новый"
        ACCEPTED = "accepted", "Принят"
        COOKING = "cooking", "Готовится"
        READY = "ready", "Готов"
        CLOSED = "closed", "Закрыт"
        CANCELLED = "cancelled", "Отменён"
        # class Type(models.TextChoices):
        # DELIVERY = "delivery", "Доставка"
        # PICKUP = "pickup", "Самовывоз"
        # TABLE = "table", "В зале"   # ✅

    type = models.CharField(max_length=20, choices=Type.choices, default=Type.PICKUP)

    # ✅ на какой стол
    table_place = models.ForeignKey(
        Place, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="orders"
    )
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)

    table_session = models.ForeignKey(TableSession, on_delete=models.SET_NULL, null=True, blank=True)

    customer_name = models.CharField(max_length=120, blank=True)
    customer_phone = models.CharField(max_length=50, blank=True)
    delivery_address = models.CharField(max_length=300, blank=True)
    comment = models.TextField(blank=True)

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Наличные"
        ONLINE = "online", "Онлайн"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Не оплачено"
        PAID = "paid", "Оплачено"

    payment_method = models.CharField(
        max_length=10, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )
    
    
class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField(default=1)
    price_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    line_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)


