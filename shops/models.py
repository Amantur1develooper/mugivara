from django.db import models
from django.utils.text import slugify
from decimal import Decimal
from django.db import models, transaction
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image
import os


def _compress(field, max_size=(1200, 900), quality=85):
    """Compress and convert an image field to WebP. Returns (name, content) or None."""
    if not field or not hasattr(field, "file"):
        return None
    # Skip already-committed files (only process new uploads)
    if getattr(field, "_committed", True):
        return None
    try:
        field.file.seek(0)
        img = Image.open(field.file).convert("RGB")
        img.thumbnail(max_size, Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=6)
        buf.seek(0)
        name = os.path.splitext(os.path.basename(field.name))[0] + ".webp"
        return name, ContentFile(buf.read())
    except Exception:
        return None

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
    youtube_url    = models.URLField("YouTube канал",    blank=True, default="")
    instagram_url  = models.URLField("Instagram (1)",   blank=True, default="")
    instagram_url_2 = models.URLField("Instagram (2)",  blank=True, default="")
    order_phone    = models.CharField("Телефон для индивидуальных заказов", max_length=32, blank=True, default="")
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name_ru)[:220]
        result = _compress(self.logo)
        if result:
            name, content = result
            self.logo.save(name, content, save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name_ru


class StoreBranch(TimeStampedModel):
    class City(models.TextChoices):
        BISHKEK = "bishkek", "Бишкек"
        OSH     = "osh",     "Ош"
        OTHER   = "other",   "Другой город"

    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="branches")
    city  = models.CharField("Город", max_length=20, choices=City.choices, default=City.OSH)
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
    phone2 = models.CharField("WhatsApp 2", max_length=32, blank=True, default="")
    lat = models.DecimalField("Широта",  max_digits=10, decimal_places=7, null=True, blank=True)
    lon = models.DecimalField("Долгота", max_digits=10, decimal_places=7, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    # часы работы
    is_open_24h = models.BooleanField("Круглосуточно", default=False)
    open_time   = models.TimeField("Время открытия", null=True, blank=True)
    close_time  = models.TimeField("Время закрытия", null=True, blank=True)
    # рабочие дни: строка вида "0,1,2,3,4,5,6" (0=пн, 6=вс), пусто = все дни
    work_days   = models.CharField("Рабочие дни", max_length=20, blank=True, default="")

    def is_open_now(self) -> bool:
        if not self.is_active:
            return False
        if self.is_open_24h:
            return True
        from django.utils import timezone
        now = timezone.localtime()
        # проверяем день недели (0=пн … 6=вс)
        if self.work_days:
            allowed = {int(d) for d in self.work_days.split(",") if d.strip().isdigit()}
            if now.weekday() not in allowed:
                return False
        if not self.open_time or not self.close_time:
            return False
        t = now.time()
        if self.open_time < self.close_time:
            return self.open_time <= t < self.close_time
        return t >= self.open_time or t < self.close_time

    def save(self, *args, **kwargs):
        result = _compress(self.cover_photo)
        if result:
            name, content = result
            self.cover_photo.save(name, content, save=False)
        super().save(*args, **kwargs)

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
    barcode = models.CharField("Штрих-код", max_length=64, blank=True, default="")

    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        result = _compress(self.photo)
        if result:
            name, content = result
            self.photo.save(name, content, save=False)
        super().save(*args, **kwargs)

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


class StoreMembership(models.Model):
    class Role(models.TextChoices):
        OWNER   = "owner",   "Владелец"
        MANAGER = "manager", "Менеджер"

    user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="store_memberships")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="memberships")
    role  = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.MANAGER)

    class Meta:
        verbose_name        = "Доступ к магазину"
        verbose_name_plural = "Доступы к магазинам"
        unique_together     = ("user", "store")

    def __str__(self):
        return f"{self.user} → {self.store} ({self.role})"
