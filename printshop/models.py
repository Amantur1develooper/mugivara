import os
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from PIL import Image


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


# ── VENUE ────────────────────────────────────────────────────────────────

class PrintCenter(models.Model):
    name_ru = models.CharField("Название", max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    logo = models.ImageField("Логотип", upload_to="printshop/logos/", blank=True, null=True)
    description_ru = models.TextField("Описание", blank=True, default="")
    description_ky = models.TextField(blank=True, default="")
    description_en = models.TextField(blank=True, default="")
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Полиграфический центр"
        verbose_name_plural = "Полиграфические центры"

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


class PrintBranch(TimeStampedModel):
    center = models.ForeignKey(PrintCenter, on_delete=models.CASCADE, related_name="branches")

    name_ru = models.CharField("Название филиала", max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")

    banner = models.ImageField("Баннер", upload_to="printshop/banners/", blank=True, null=True)
    address = models.CharField("Адрес", max_length=255, blank=True, default="")
    phone = models.CharField("Телефон", max_length=32, blank=True, default="")
    whatsapp = models.CharField("WhatsApp (если отличается)", max_length=32, blank=True, default="")
    telegram = models.CharField(
        "Telegram (@username или ссылка)", max_length=120, blank=True, default="",
        help_text="Публичный контакт для кнопки «Telegram» на витрине (не путать с Chat ID для уведомлений)",
    )
    taplink_url = models.URLField("Taplink", blank=True, default="")
    map_url = models.URLField("Ссылка на карту (Маршрут)", blank=True, default="")
    lat = models.DecimalField("Широта", max_digits=10, decimal_places=7, null=True, blank=True)
    lon = models.DecimalField("Долгота", max_digits=10, decimal_places=7, null=True, blank=True)

    delivery_enabled = models.BooleanField("Доставка включена", default=True)
    min_order_amount = models.DecimalField("Мин. сумма заказа", max_digits=10, decimal_places=2, default=0)
    free_delivery_from = models.DecimalField(
        "Бесплатная доставка от", max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Пусто или 0 = бесплатная доставка не действует",
    )
    delivery_fee = models.DecimalField("Стоимость доставки", max_digits=10, decimal_places=2, default=0)

    tg_chat_id = models.CharField("Telegram Chat ID", max_length=50, blank=True, default="")
    tg_thread_id = models.PositiveIntegerField("Telegram Thread ID", null=True, blank=True)

    is_open_24h = models.BooleanField("Круглосуточно", default=False)
    open_time = models.TimeField("Время открытия", null=True, blank=True)
    close_time = models.TimeField("Время закрытия", null=True, blank=True)
    work_days = models.CharField(
        "Рабочие дни", max_length=20, blank=True, default="",
        help_text="Например 0,1,2,3,4,5,6 (0=пн ... 6=вс), пусто = все дни",
    )

    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Филиал"
        verbose_name_plural = "Филиалы"
        ordering = ("center", "name_ru")

    def is_open_now(self) -> bool:
        if not self.is_active:
            return False
        if self.is_open_24h:
            return True
        now = timezone.localtime()
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
        result = _compress(self.banner)
        if result:
            name, content = result
            self.banner.save(name, content, save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.center} — {self.name_ru}"


# ── CATALOG ──────────────────────────────────────────────────────────────

class PrintCategory(models.Model):
    center = models.ForeignKey(PrintCenter, on_delete=models.CASCADE, related_name="categories")
    name_ru = models.CharField("Название", max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активна", default=True)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return f"{self.center}: {self.name_ru}"


class PrintProduct(models.Model):
    center = models.ForeignKey(PrintCenter, on_delete=models.CASCADE, related_name="products")
    category = models.ForeignKey(
        PrintCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )

    name_ru = models.CharField("Название", max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    description_ru = models.TextField("Описание", blank=True, default="")
    description_ky = models.TextField(blank=True, default="")
    description_en = models.TextField(blank=True, default="")

    main_photo = models.ImageField("Главное фото", upload_to="printshop/products/", blank=True, null=True)
    sku = models.CharField("Артикул", max_length=64, blank=True, default="")

    base_price = models.DecimalField(
        "Базовая цена", max_digits=10, decimal_places=2, default=0,
        help_text="Используется, если у товара нет вариантов",
    )

    is_available = models.BooleanField("В наличии", default=True)
    is_new = models.BooleanField("Новинка", default=False)
    is_popular = models.BooleanField("Популярное", default=False)
    is_promo = models.BooleanField("Акция", default=False)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Товар/услуга"
        verbose_name_plural = "Товары/услуги"

    def save(self, *args, **kwargs):
        result = _compress(self.main_photo)
        if result:
            name, content = result
            self.main_photo.save(name, content, save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name_ru

    @property
    def display_price(self):
        """Цена для карточки в каталоге: самый дешёвый активный вариант, иначе базовая цена."""
        variant = self.variants.filter(is_active=True).order_by("price").first()
        return variant.price if variant else self.base_price


class PrintProductPhoto(models.Model):
    product = models.ForeignKey(PrintProduct, on_delete=models.CASCADE, related_name="photos")
    photo = models.ImageField("Фото", upload_to="printshop/products/gallery/")
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Фото товара"
        verbose_name_plural = "Фото товара (галерея)"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.product_id and self.pk is None:
            if self.product.photos.count() >= 5:
                raise ValidationError("У товара уже 5 фото в галерее (максимум).")

    def save(self, *args, **kwargs):
        result = _compress(self.photo)
        if result:
            name, content = result
            self.photo.save(name, content, save=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product} — фото {self.sort_order}"


# ── VARIANTS (взаимоисключающие, своя абсолютная цена) ───────────────────

class PrintProductVariant(models.Model):
    product = models.ForeignKey(PrintProduct, on_delete=models.CASCADE, related_name="variants")
    label = models.CharField("Название варианта", max_length=100, help_text='Например "S", "1×1 м", "100 шт"')
    price = models.DecimalField("Цена", max_digits=10, decimal_places=2, default=0)
    is_default = models.BooleanField("По умолчанию", default=False)
    is_active = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Вариант (размер/тираж)"
        verbose_name_plural = "Варианты (размер/тираж)"

    def __str__(self):
        return f"{self.product}: {self.label} ({self.price})"


# ── ДОП. ПАРАМЕТРЫ (аддитивные, произвольные группы) ──────────────────────

class PrintOptionGroup(models.Model):
    product = models.ForeignKey(PrintProduct, on_delete=models.CASCADE, related_name="option_groups")
    name = models.CharField("Название группы", max_length=150, help_text='Например "Материал", "Ламинация"')
    is_required = models.BooleanField("Обязательный выбор", default=False)
    allow_multiple = models.BooleanField("Множественный выбор (чекбоксы)", default=False)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Группа доп. параметров"
        verbose_name_plural = "Группы доп. параметров"

    def __str__(self):
        return f"{self.product}: {self.name}"


class PrintOptionValue(models.Model):
    group = models.ForeignKey(PrintOptionGroup, on_delete=models.CASCADE, related_name="values")
    label = models.CharField("Значение", max_length=150, help_text='Например "Бумага", "Да"')
    price_delta = models.DecimalField("Доплата", max_digits=10, decimal_places=2, default=0)
    is_default = models.BooleanField("По умолчанию", default=False)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Значение параметра"
        verbose_name_plural = "Значения параметра"

    def __str__(self):
        return f"{self.group}: {self.label} (+{self.price_delta})"


# ── ДОСТУП ───────────────────────────────────────────────────────────────

class PrintMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Владелец"
        MANAGER = "manager", "Менеджер"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="printshop_memberships"
    )
    center = models.ForeignKey(PrintCenter, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.MANAGER)

    class Meta:
        verbose_name = "Доступ к полигр. центру"
        verbose_name_plural = "Доступы к полигр. центрам"
        unique_together = ("user", "center")

    def __str__(self):
        return f"{self.user} → {self.center} ({self.role})"


# ── ПРОМОКОДЫ ────────────────────────────────────────────────────────────

class PrintPromoCode(TimeStampedModel):
    class DiscountType(models.TextChoices):
        FREE_DELIVERY = "free_delivery", "Бесплатная доставка"
        PERCENT = "percent", "Скидка в процентах"
        FIXED = "fixed", "Скидка фиксированной суммой"

    branch = models.ForeignKey(PrintBranch, on_delete=models.CASCADE, related_name="promo_codes")
    code = models.CharField("Промокод", max_length=50)
    discount_type = models.CharField("Тип скидки", max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(
        "Размер скидки", max_digits=10, decimal_places=2, default=0,
        help_text="Для % — число (10 = 10%). Для суммы — сом. Для бесплатной доставки — 0.",
    )
    valid_until = models.DateField("Действует до", null=True, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    max_uses = models.PositiveIntegerField("Макс. использований", default=0, help_text="0 = без ограничений")
    used_count = models.PositiveIntegerField("Использован раз", default=0, editable=False)

    class Meta:
        verbose_name = "Промокод"
        verbose_name_plural = "Промокоды"
        unique_together = ("branch", "code")

    def __str__(self):
        return f"{self.code} ({self.branch})"

    def is_valid(self):
        if not self.is_active:
            return False, "Промокод неактивен"
        if self.valid_until and self.valid_until < timezone.localdate():
            return False, "Срок действия промокода истёк"
        if self.max_uses > 0 and self.used_count >= self.max_uses:
            return False, "Промокод исчерпан"
        return True, "ok"


# ── ЗАКАЗЫ ───────────────────────────────────────────────────────────────

class PrintOrder(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        CONFIRMED = "confirmed", "Подтвержден"
        IN_PROGRESS = "in_progress", "В работе"
        DONE = "done", "Завершен"
        CANCELED = "canceled", "Отменен"

    class Pay(models.TextChoices):
        CASH = "cash", "Наличные"
        ONLINE = "online", "Онлайн"

    branch = models.ForeignKey(PrintBranch, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    name = models.CharField(max_length=120, blank=True, default="")
    phone = models.CharField(max_length=20)
    address = models.CharField(max_length=255, blank=True, default="")
    comment = models.TextField(blank=True, default="")
    payment_method = models.CharField(max_length=20, choices=Pay.choices, default=Pay.CASH)

    promo_code = models.ForeignKey(
        PrintPromoCode, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ("-created_at",)

    def __str__(self):
        return f"#{self.id} {self.branch} {self.total}"


class PrintOrderItem(TimeStampedModel):
    order = models.ForeignKey(PrintOrder, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(PrintProduct, on_delete=models.PROTECT)
    product_name_snapshot = models.CharField(max_length=200)
    qty = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    comment = models.CharField("Комментарий к позиции", max_length=300, blank=True, default="")

    # {"variant": {"label": str, "price": str} | None,
    #  "options": [{"group_name": str, "value_label": str, "price_delta": str}, ...]}
    selection_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"

    def __str__(self):
        return f"{self.order_id}: {self.product_name_snapshot} × {self.qty}"
