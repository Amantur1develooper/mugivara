from django.db import models
from django.utils.text import slugify
from decimal import Decimal
from django.db import models, transaction
from django.utils.text import slugify
from django.utils import timezone

class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Store(models.Model):
    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    logo = models.ImageField(upload_to="stores/logos/", blank=True, null=True)
    about_ru = models.TextField(blank=True, default="")
    about_ky = models.TextField(blank=True, default="")
    about_en = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name_ru)[:220]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name_ru


class StoreBranch(TimeStampedModel):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="branches")
    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    map_url = models.URLField(blank=True, default="")
    cover_photo = models.ImageField(upload_to="stores/branches/", blank=True, null=True)

    # настройки доставки
    delivery_enabled = models.BooleanField(default=False)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tg_group_chat_id = models.BigIntegerField(null=True, blank=True)   # группа
    tg_thread_id     = models.IntegerField(null=True, blank=True)      # если форум-топик
    tg_manager_chat_id = models.BigIntegerField(null=True, blank=True) # личка менеджера
    phone = models.CharField(max_length=32, blank=True, default="")


    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.store} — {self.name_ru}"


class StoreCategory(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="categories")
    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return f"{self.store}: {self.name_ru}"


class StoreProduct(models.Model):
    class Unit(models.TextChoices):
        PCS = "pcs", "шт"
        KG = "kg", "кг"
        L = "l", "л"

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="products")
    category = models.ForeignKey(StoreCategory, on_delete=models.SET_NULL, null=True, related_name="products")
    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    description_ru = models.TextField(blank=True, default="")
    description_ky = models.TextField(blank=True, default="")
    description_en = models.TextField(blank=True, default="")
    photo = models.ImageField(upload_to="stores/products/", blank=True, null=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.PCS)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name_ru


class StoreStock(models.Model):
    branch = models.ForeignKey(StoreBranch, on_delete=models.CASCADE, related_name="stocks")
    product = models.ForeignKey(StoreProduct, on_delete=models.CASCADE, related_name="stocks")
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)  # 1.000, 0.500 и т.д.

    class Meta:
        unique_together = ("branch", "product")

    def __str__(self):
        return f"{self.branch}: {self.product} = {self.qty}"















class StoreOrder(TimeStampedModel):
    class Type(models.TextChoices):
        DELIVERY = "delivery", "Доставка"
        PICKUP = "pickup", "В магазине"

    class Pay(models.TextChoices):
        CASH = "cash", "Наличные"
        ONLINE = "online", "Онлайн"
        
    class Mode(models.TextChoices):
        DELIVERY = "delivery", "Доставка"
        IN_STORE = "in_store", "В магазине"

    class Status(models.TextChoices):
        NEW = "new", "Новый"
        CONFIRMED = "confirmed", "Подтвержден"
        DONE = "done", "Завершен"
        CANCELED = "canceled", "Отменен"

    branch = models.ForeignKey(StoreBranch, on_delete=models.CASCADE, related_name="orders")
    order_type = models.CharField(max_length=20, choices=Type.choices, default=Type.DELIVERY)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.DELIVERY)
    name = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=20)  # +996XXXXXXXXX
    address = models.CharField(max_length=255, blank=True, default="")  # обязательно только для доставки
    comment = models.TextField(blank=True, default="")
    payment_method = models.CharField(max_length=20, choices=Pay.choices, default=Pay.CASH)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"#{self.id} {self.branch} {self.order_type} {self.total}"


class StoreOrderItem(TimeStampedModel):
    order = models.ForeignKey(StoreOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(StoreProduct, on_delete=models.PROTECT)
    qty = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    unit = models.CharField(max_length=10, default="pcs")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.order_id}: {self.product} x {self.qty}"
