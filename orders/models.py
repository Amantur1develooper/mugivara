from django.db import models
# orders/models.py
from reservations.models import Place
from django.db import models
from core.models import Branch, TimeStampedModel
from tables.models import TableSession
from catalog.models import Item, DishConstructor

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
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
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
    old_price_snapshot = models.DecimalField(
        "Старая цена на момент заказа", max_digits=10, decimal_places=2,
        null=True, blank=True, default=None,
        help_text="Заполняется, если блюдо было по акции в момент заказа",
    )

    line_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def is_on_promo(self):
        return self.old_price_snapshot is not None and self.old_price_snapshot > self.price_snapshot

    @property
    def discount_amount(self):
        if not self.is_on_promo:
            return 0
        return (self.old_price_snapshot - self.price_snapshot) * self.qty


class ConstructorOrderItem(TimeStampedModel):
    """Позиция заказа из конструктора блюд (собери сам)."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="constructor_items")
    constructor = models.ForeignKey(DishConstructor, on_delete=models.PROTECT)
    constructor_name_snapshot = models.CharField(max_length=200)
    qty = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # [{group_name, ings: [{name, extra_price}]}]
    ingredients_snapshot = models.JSONField(default=list)

    class Meta:
        verbose_name = "Позиция заказа (конструктор)"
        verbose_name_plural = "Позиции заказа (конструктор)"


