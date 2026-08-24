import urllib.parse

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


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
        verbose_name        = "Риэлторское агентство"
        verbose_name_plural = "Риэлторские агентства"
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
    phone  = models.CharField("WhatsApp риэлтора", max_length=50, blank=True, default="",
                              help_text="На этот номер ведёт кнопка «Купить» на карточках его квартир")

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

    agency       = models.ForeignKey(RealtyAgency, on_delete=models.CASCADE, related_name="apartments")
    realtor      = models.ForeignKey(RealtyMembership, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="apartments", verbose_name="Ответственный риэлтор")

    city         = models.CharField("Город", max_length=120, blank=True, default="")
    district     = models.CharField("Район", max_length=120, blank=True, default="")
    address      = models.CharField("Адрес", max_length=300, blank=True, default="")

    area         = models.DecimalField("Площадь, м²", max_digits=7, decimal_places=1, null=True, blank=True)
    rooms        = models.PositiveSmallIntegerField("Комнат", null=True, blank=True)
    floor        = models.PositiveSmallIntegerField("Этаж", null=True, blank=True)
    floors_total = models.PositiveSmallIntegerField("Этажность дома", null=True, blank=True)
    renovation   = models.CharField("Ремонт", max_length=20, choices=Renovation.choices, blank=True, default="")

    price        = models.DecimalField("Цена продажи (сом)", max_digits=14, decimal_places=0, null=True, blank=True)
    status       = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.FREE)

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
        price = f"{int(self.price)} сом" if self.price is not None else "цена не указана"
        return f"{self.address or 'Без адреса'} — {price}"

    @property
    def main_photo(self):
        return self.photos.first()

    @property
    def whatsapp_phone(self):
        if self.realtor and self.realtor.phone:
            return self.realtor.phone
        return self.agency.phone

    @property
    def whatsapp_url(self):
        digits = "".join(ch for ch in (self.whatsapp_phone or "") if ch.isdigit())
        if not digits:
            return ""
        details = ", ".join(filter(None, [
            self.address or None,
            f"{self.area} м²" if self.area is not None else None,
            f"{int(self.price)} сом" if self.price is not None else None,
        ]))
        text = f"Здравствуйте! Хочу купить квартиру: {details}" if details else "Здравствуйте! Хочу купить квартиру."
        return f"https://wa.me/{digits}?text={urllib.parse.quote(text)}"


class ApartmentPhoto(TimeStampedModel):
    apartment  = models.ForeignKey(Apartment, on_delete=models.CASCADE, related_name="photos")
    photo      = models.ImageField("Фото", upload_to="realestate/apartments/")
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Фото квартиры"
        verbose_name_plural = "Фото квартиры"
        ordering            = ["sort_order", "id"]
