from django.db import models
from django.conf import settings
from django.utils import timezone
import os
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True


class Restaurant(TimeStampedModel):
    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=220, unique=True)
    logo = models.ImageField(upload_to="restaurants/logos/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    rating = models.DecimalField("Рейтинг", max_digits=3, decimal_places=1, default=0.0)
    about_ru = models.TextField(blank=True, default="")
    about_ky = models.TextField(blank=True, default="")
    about_en = models.TextField(blank=True, default="")
    external_url = models.URLField(
        "Ссылка на сайт / приложение",
        blank=True, default="",
        help_text="Если заполнено — кнопка «Перейти к заказу» будет вести на этот сайт"
    )
    phone        = models.CharField("Телефон", max_length=60, blank=True, default="")
    whatsapp     = models.CharField("WhatsApp (номер)", max_length=60, blank=True, default="",
                                    help_text="Только цифры со знаком +, напр. +996700123456")
    instagram    = models.URLField("Instagram", blank=True, default="")
    telegram     = models.CharField("Telegram (@username или ссылка)", max_length=120, blank=True, default="")
    map_url      = models.URLField("Ссылка на карту (2GIS / Google Maps)", blank=True, default="")
    tiktok       = models.URLField("TikTok", blank=True, default="")

    class Meta:
        verbose_name = "Ресторан"
        verbose_name_plural = "Рестораны"
        indexes = [
            models.Index(fields=["is_active", "-rating"], name="restaurant_active_rating_idx"),
            models.Index(fields=["slug"], name="restaurant_slug_idx"),
        ]
        
    def __str__(self):
        return self.name_ru
    

class Branch(TimeStampedModel):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="branches")
    
    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    map_url = models.URLField("Ссылка на карту", blank=True, default="")
    address = models.CharField(max_length=300, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    
    delivery_enabled = models.BooleanField(default=False)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    free_delivery_from = models.DecimalField(
        "Бесплатная доставка от (сом)", max_digits=10, decimal_places=2,
        default=0, help_text="0 = не действует"
    )
    
    is_open_24h = models.BooleanField(default=False)
    open_time = models.TimeField(null=True, blank=True)   # например 09:00
    close_time = models.TimeField(null=True, blank=True)  # например 22:00
    cover_photo = models.ImageField(upload_to="branches/covers/", blank=True, null=True)
    promo_photo = models.ImageField(
        "Фото для акции (фон карусели)",
        upload_to="branches/promo/", blank=True, null=True,
    )
    external_url = models.URLField(
        "Внешний сайт / приложение",
        blank=True, default="",
        help_text="Если заполнено — кнопка «Открыть меню» будет вести на этот адрес"
    )

    def save(self, *args, **kwargs):
        self.photo_compression = None
        if self.promo_photo and hasattr(self.promo_photo, 'file'):
            try:
                original_size = self.promo_photo.file.seek(0, 2) or self.promo_photo.file.tell()
                self.promo_photo.file.seek(0)
                img = Image.open(self.promo_photo).convert("RGB")
                orig_w, orig_h = img.size
                img.thumbnail((1200, 600), Image.LANCZOS)
                new_w, new_h = img.size
                buf = BytesIO()
                img.save(buf, format="WEBP", quality=85, method=6)
                compressed_size = buf.tell()
                buf.seek(0)
                name = os.path.splitext(self.promo_photo.name)[0] + ".webp"
                self.promo_photo.save(name, ContentFile(buf.read()), save=False)
                self.photo_compression = {
                    "before_kb": round(original_size / 1024, 1),
                    "after_kb":  round(compressed_size / 1024, 1),
                    "saved_pct": round((1 - compressed_size / original_size) * 100) if original_size else 0,
                    "orig_size": f"{orig_w}×{orig_h}",
                    "new_size":  f"{new_w}×{new_h}",
                }
            except Exception:
                pass
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Филиал"
        verbose_name_plural = "Филиалы"
        indexes = [
            models.Index(fields=["restaurant", "is_active"], name="branch_restaurant_active_idx"),
        ]
        
    def __str__(self):
        return f"{self.restaurant.name_ru} — {self.name_ru}"
    
    def is_open_now(self) -> bool:
        if not self.is_active:
            return False
        if self.is_open_24h:
            return True
        if not self.open_time or not self.close_time:
            return False

        now = timezone.localtime()
        t = now.time()

        # обычный режим (09:00-22:00)
        if self.open_time < self.close_time:
            return self.open_time <= t < self.close_time
        # через полночь (18:00-02:00)
        return t >= self.open_time or t < self.close_time

class PromoCode(TimeStampedModel):
    class DiscountType(models.TextChoices):
        FREE_DELIVERY = "free_delivery", "Бесплатная доставка"
        PERCENT       = "percent",       "Скидка в процентах"
        FIXED         = "fixed",         "Скидка фиксированной суммой"

    branch         = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="promo_codes")
    code           = models.CharField("Промокод", max_length=50)
    discount_type  = models.CharField("Тип скидки", max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(
        "Размер скидки", max_digits=10, decimal_places=2, default=0,
        help_text="Для % — число (10 = 10%). Для суммы — сом (500). Для бесплатной доставки — 0.",
    )
    valid_until    = models.DateField("Действует до", null=True, blank=True)
    is_active      = models.BooleanField("Активен", default=True)
    max_uses       = models.PositiveIntegerField("Макс. использований", default=0, help_text="0 = без ограничений")
    used_count     = models.PositiveIntegerField("Использован раз", default=0, editable=False)

    class Meta:
        verbose_name = "Промокод"
        verbose_name_plural = "Промокоды"
        unique_together = ("branch", "code")

    def __str__(self):
        return f"{self.code} ({self.branch.restaurant.name_ru})"

    def is_valid(self):
        from django.utils import timezone
        if not self.is_active:
            return False, "Промокод неактивен"
        if self.valid_until and self.valid_until < timezone.localdate():
            return False, "Срок действия промокода истёк"
        if self.max_uses > 0 and self.used_count >= self.max_uses:
            return False, "Промокод исчерпан"
        return True, "ok"


class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MANAGER = "manager", "Manager"
        CASHIER = "cashier", "Cashier"
        KITCHEN = "kitchen", "Kitchen"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices)
        
    class Meta:
        verbose_name = "Доступ к ресторану"
        verbose_name_plural = "Доступы к ресторанам"
        unique_together = ("user", "restaurant", "branch")

    def __str__(self):
        branch_str = f" / {self.branch.name_ru}" if self.branch else " / все филиалы"
        return f"{self.user} → {self.restaurant}{branch_str} ({self.role})"


class PageView(models.Model):
    SECTION_CHOICES = [
        ("home",       "Главная"),
        ("markets",    "Рынки"),
        ("shops",      "Магазины"),
        ("hotels",     "Отели"),
        ("pharmacy",   "Аптеки"),
        ("legal",      "Юристы"),
        ("eco",        "Эко-проекты"),
        ("restaurant", "Рестораны / меню"),
        ("other",      "Другое"),
    ]

    section    = models.CharField("Раздел", max_length=20, choices=SECTION_CHOICES, db_index=True)
    path       = models.CharField("URL", max_length=500)
    ip_hash    = models.CharField("Хэш IP", max_length=64)
    session_key = models.CharField("Сессия", max_length=64, blank=True, default="")
    timestamp  = models.DateTimeField("Время", default=timezone.now, db_index=True)

    class Meta:
        verbose_name        = "Просмотр страницы"
        verbose_name_plural = "Просмотры страниц"
        indexes = [
            models.Index(fields=["section", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.section} {self.path} {self.timestamp:%Y-%m-%d %H:%M}"


class AdBanner(models.Model):
    """Рекламный баннер на главной странице."""

    title         = models.CharField("Название (для себя)", max_length=200, blank=True, default="")
    image_desktop = models.ImageField(
        "Фото для ПК (широкий баннер, ~2560×192)",
        upload_to="ads/desktop/", blank=True, null=True,
    )
    image_tablet  = models.ImageField(
        "Фото для планшета (~840×345)",
        upload_to="ads/tablet/", blank=True, null=True,
    )
    image_mobile  = models.ImageField(
        "Фото для телефона (~850×192)",
        upload_to="ads/mobile/", blank=True, null=True,
    )
    link_url      = models.URLField("Ссылка (куда ведёт баннер)", blank=True, default="")
    click_count   = models.PositiveIntegerField("Переходов всего", default=0, editable=False)
    is_active     = models.BooleanField("Активен", default=True)
    sort_order    = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Рекламный баннер"
        verbose_name_plural = "Рекламные баннеры"
        ordering            = ["sort_order"]

    def __str__(self):
        return self.title or f"Баннер #{self.pk}"
