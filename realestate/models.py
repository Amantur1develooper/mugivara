import os
import urllib.parse
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from PIL import Image

from core.models import TimeStampedModel


def _compress_photo(field, max_side=1080, quality=78):
    """Resize to max_side×max_side, convert to WebP. Returns True if processed."""
    if not (field and hasattr(field, "file")):
        return False
    try:
        field.file.seek(0)
        img = Image.open(field)
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=6)
        buf.seek(0)
        name = os.path.splitext(field.name)[0] + ".webp"
        field.save(name, ContentFile(buf.read()), save=False)
        return True
    except Exception:
        return False


class RealtyAgency(TimeStampedModel):
    place_category = models.ForeignKey(
        "core.PlaceCategory", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="realty_agencies",
        verbose_name="Категория платформы",
    )
    name        = models.CharField("Название агентства", max_length=200)
    slug        = models.SlugField(max_length=220, unique=True)
    logo        = models.ImageField("Логотип", upload_to="realestate/logos/", blank=True, null=True)
    cover       = models.ImageField("Обложка", upload_to="realestate/covers/", blank=True, null=True)
    description = models.TextField("Описание", blank=True, default="")
    phone       = models.CharField("Телефон / WhatsApp агентства", max_length=50, blank=True, default="",
                                   help_text="Резервный номер для кнопки «Купить», если у квартиры не указан риэлтор")
    address     = models.CharField("Адрес", max_length=300, blank=True, default="")
    is_active   = models.BooleanField("Активно", default=True)
    sort_order  = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Агентство недвижимости"
        verbose_name_plural = "Агентства недвижимости"
        ordering            = ["sort_order", "name"]

    def __str__(self):
        return self.name


class RealtyMembership(TimeStampedModel):
    class Role(models.TextChoices):
        DIRECTOR = "director", "Директор"
        REALTOR  = "realtor", "Риэлтор"

    user   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="realty_memberships")
    agency = models.ForeignKey(RealtyAgency, on_delete=models.CASCADE, related_name="memberships")
    role   = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.REALTOR)

    class Meta:
        verbose_name        = "Доступ к агентству"
        verbose_name_plural = "Доступы к агентству"
        unique_together     = ("user", "agency")

    def __str__(self):
        return f"{self.user} → {self.agency} ({self.get_role_display()})"


class Apartment(TimeStampedModel):
    class Renovation(models.TextChoices):
        NONE     = "none", "Без ремонта"
        COSMETIC = "cosmetic", "Косметический"
        EURO     = "euro", "Евроремонт"
        DESIGNER = "designer", "Дизайнерский"

    class Status(models.TextChoices):
        FREE    = "free", "Свободна"
        BOOKED  = "booked", "Забронирована"
        SOLD    = "sold", "Продана"
        REMOVED = "removed", "Снята с продажи"

    class Currency(models.TextChoices):
        KGS = "KGS", "сом"
        USD = "USD", "$"

    agency       = models.ForeignKey(RealtyAgency, on_delete=models.CASCADE, related_name="apartments")
    realtor      = models.ForeignKey(RealtyMembership, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="apartments", verbose_name="Ответственный риэлтор")
    owner_phone  = models.CharField("Телефон хозяина квартиры", max_length=50, blank=True, default="",
                                    help_text="Виден только в кабинете агентства, не показывается публично")

    city         = models.CharField("Город", max_length=120, blank=True, default="")
    district     = models.CharField("Район", max_length=120, blank=True, default="")
    address      = models.CharField("Адрес", max_length=300, blank=True, default="")

    area         = models.DecimalField("Площадь, м²", max_digits=7, decimal_places=1, null=True, blank=True)
    rooms        = models.PositiveSmallIntegerField("Комнат", null=True, blank=True)
    floor        = models.PositiveSmallIntegerField("Этаж", null=True, blank=True)
    floors_total = models.PositiveSmallIntegerField("Этажность дома", null=True, blank=True)
    renovation   = models.CharField("Ремонт", max_length=20, choices=Renovation.choices, blank=True, default="")

    price         = models.DecimalField("Цена продажи", max_digits=14, decimal_places=2, null=True, blank=True)
    price_per_sqm = models.DecimalField("Цена за м²", max_digits=10, decimal_places=2, null=True, blank=True)
    currency      = models.CharField("Валюта", max_length=3, choices=Currency.choices, default=Currency.KGS)
    status        = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.FREE)

    description  = models.TextField("Описание", blank=True, default="")
    review_url_1 = models.URLField("Ссылка на обзор 1", max_length=500, blank=True, default="")
    review_url_2 = models.URLField("Ссылка на обзор 2", max_length=500, blank=True, default="")
    is_active    = models.BooleanField("Активно", default=True)
    sort_order   = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Квартира"
        verbose_name_plural = "Квартиры"
        ordering            = ["-created_at"]

    def __str__(self):
        price = f"{self.price_display}" if self.price is not None else "цена не указана"
        return f"{self.address or 'Без адреса'} — {price}"

    @property
    def main_photo(self):
        return self.photos.first()

    @property
    def currency_symbol(self):
        return "$" if self.currency == self.Currency.USD else "сом"

    @staticmethod
    def _fmt(value):
        value = value if isinstance(value, Decimal) else Decimal(str(value))
        if value == value.to_integral_value():
            return f"{int(value):,}".replace(",", " ")
        return f"{value:,.2f}".replace(",", " ")

    @property
    def price_display(self):
        if self.price is None:
            return ""
        return f"{self._fmt(self.price)} {self.currency_symbol}"

    @property
    def price_per_sqm_display(self):
        if self.price_per_sqm is None:
            return ""
        return f"{self._fmt(self.price_per_sqm)} {self.currency_symbol}/м²"

    @property
    def whatsapp_phone(self):
        return self.agency.phone

    @property
    def owner_whatsapp_url(self):
        digits = "".join(ch for ch in (self.owner_phone or "") if ch.isdigit())
        if not digits:
            return ""
        return f"https://wa.me/{digits}"

    @property
    def whatsapp_url(self):
        digits = "".join(ch for ch in (self.whatsapp_phone or "") if ch.isdigit())
        if not digits:
            return ""
        details = ", ".join(filter(None, [
            self.address or None,
            f"{self.area} м²" if self.area is not None else None,
            self.price_display or None,
        ]))
        text = f"Здравствуйте! Хочу купить квартиру: {details}" if details else "Здравствуйте! Хочу купить квартиру."
        return f"https://wa.me/{digits}?text={urllib.parse.quote(text)}"


class ApartmentPhoto(TimeStampedModel):
    apartment  = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name="photos")
    photo      = models.ImageField("Фото", upload_to="realestate/apartments/")
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    def save(self, *args, **kwargs):
        _compress_photo(self.photo)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name        = "Фото квартиры"
        verbose_name_plural = "Фото квартиры"
        ordering            = ["sort_order", "id"]
