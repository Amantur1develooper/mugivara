import os
import urllib.parse
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.utils.translation import gettext_lazy as _
from PIL import Image

from core.models import TimeStampedModel


def _compress_photo(field, max_side=1440, quality=80):
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


class AutoDealership(TimeStampedModel):
    place_category = models.ForeignKey(
        "core.PlaceCategory", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="autosalons",
        verbose_name="Категория платформы",
    )
    name           = models.CharField("Название автосалона", max_length=200)
    name_en        = models.CharField("Название автосалона (EN)", max_length=200, blank=True, default="")
    slug           = models.SlugField(max_length=220, unique=True)
    logo           = models.ImageField("Логотип", upload_to="autosalon/logos/", blank=True, null=True)
    cover          = models.ImageField("Обложка", upload_to="autosalon/covers/", blank=True, null=True)
    description    = models.TextField("Описание", blank=True, default="")
    description_en = models.TextField("Описание (EN)", blank=True, default="")
    phone          = models.CharField(
        "Телефон / WhatsApp автосалона", max_length=50, blank=True, default="",
        help_text="Резервный номер для кнопки «Написать», если у машины не указан отдельный менеджер",
    )
    city           = models.CharField("Город", max_length=120, blank=True, default="")
    address        = models.CharField("Адрес", max_length=300, blank=True, default="")
    work_hours     = models.CharField("Режим работы", max_length=200, blank=True, default="",
                                       help_text="Например: Пн–Вс 09:00–19:00")
    is_active      = models.BooleanField("Активен", default=True)
    sort_order     = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Автосалон"
        verbose_name_plural  = "Автосалоны"
        ordering             = ["sort_order", "name"]

    def __str__(self):
        return self.name

    @property
    def cars_in_stock_count(self):
        return self.cars.filter(is_active=True, status=Car.Status.AVAILABLE).count()

    @property
    def phone_digits(self):
        return "".join(ch for ch in (self.phone or "") if ch.isdigit())


class DealershipMembership(TimeStampedModel):
    class Role(models.TextChoices):
        DIRECTOR = "director", "Директор"
        MANAGER  = "manager", "Менеджер"

    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="autosalon_memberships")
    dealership = models.ForeignKey(AutoDealership, on_delete=models.CASCADE, related_name="memberships")
    role       = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.MANAGER)

    class Meta:
        verbose_name        = "Доступ к автосалону"
        verbose_name_plural  = "Доступы к автосалону"
        unique_together      = ("user", "dealership")

    def __str__(self):
        return f"{self.user} → {self.dealership} ({self.get_role_display()})"


class Car(TimeStampedModel):
    class Condition(models.TextChoices):
        NEW  = "new", _("Новый")
        USED = "used", _("С пробегом")

    class BodyType(models.TextChoices):
        SEDAN     = "sedan", _("Седан")
        HATCHBACK = "hatchback", _("Хэтчбек")
        SUV       = "suv", _("Внедорожник")
        CROSSOVER = "crossover", _("Кроссовер")
        MINIVAN   = "minivan", _("Минивэн")
        PICKUP    = "pickup", _("Пикап")
        COUPE     = "coupe", _("Купе")
        WAGON     = "wagon", _("Универсал")
        CONVERTIBLE = "convertible", _("Кабриолет")

    class FuelType(models.TextChoices):
        PETROL   = "petrol", _("Бензин")
        DIESEL   = "diesel", _("Дизель")
        HYBRID   = "hybrid", _("Гибрид")
        ELECTRIC = "electric", _("Электро")
        GAS      = "gas", _("Газ")

    class Transmission(models.TextChoices):
        MANUAL    = "manual", _("Механика")
        AUTOMATIC = "automatic", _("Автомат")
        ROBOT     = "robot", _("Робот")
        CVT       = "cvt", _("Вариатор")

    class DriveType(models.TextChoices):
        FWD = "fwd", _("Передний")
        RWD = "rwd", _("Задний")
        AWD = "awd", _("Полный")

    class Status(models.TextChoices):
        AVAILABLE = "available", _("В наличии")
        RESERVED  = "reserved", _("Забронирована")
        SOLD      = "sold", _("Продана")
        HIDDEN    = "hidden", _("Снята с продажи")

    class Currency(models.TextChoices):
        KGS = "KGS", "сом"
        USD = "USD", "$"

    dealership = models.ForeignKey(AutoDealership, on_delete=models.CASCADE, related_name="cars")
    manager    = models.ForeignKey(DealershipMembership, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="cars", verbose_name="Ответственный менеджер")

    brand         = models.CharField("Марка", max_length=100)
    model_name    = models.CharField("Модель", max_length=100)
    generation    = models.CharField("Поколение / комплектация", max_length=150, blank=True, default="")
    year          = models.PositiveSmallIntegerField("Год выпуска")
    condition     = models.CharField("Состояние", max_length=10, choices=Condition.choices, default=Condition.USED)
    body_type     = models.CharField("Тип кузова", max_length=20, choices=BodyType.choices, blank=True, default="")
    mileage_km    = models.PositiveIntegerField("Пробег, км", null=True, blank=True)
    fuel_type     = models.CharField("Топливо", max_length=10, choices=FuelType.choices, blank=True, default="")
    transmission  = models.CharField("Коробка передач", max_length=12, choices=Transmission.choices, blank=True, default="")
    drive_type    = models.CharField("Привод", max_length=5, choices=DriveType.choices, blank=True, default="")
    engine_volume = models.DecimalField("Объём двигателя, л", max_digits=3, decimal_places=1, null=True, blank=True)
    power_hp      = models.PositiveSmallIntegerField("Мощность, л.с.", null=True, blank=True)
    color         = models.CharField("Цвет", max_length=60, blank=True, default="")
    vin           = models.CharField("VIN-номер", max_length=32, blank=True, default="",
                                      help_text="Виден только в кабинете салона, не показывается публично")

    price     = models.DecimalField("Цена", max_digits=14, decimal_places=2, null=True, blank=True)
    currency  = models.CharField("Валюта", max_length=3, choices=Currency.choices, default=Currency.KGS)
    status    = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.AVAILABLE)

    description    = models.TextField("Описание", blank=True, default="")
    description_en = models.TextField("Описание (EN)", blank=True, default="")
    is_active      = models.BooleanField("Активна", default=True)
    sort_order     = models.PositiveSmallIntegerField("Порядок", default=0)
    sold_at        = models.DateTimeField("Продана когда", null=True, blank=True)

    class Meta:
        verbose_name        = "Автомобиль"
        verbose_name_plural  = "Автомобили"
        ordering             = ["-created_at"]

    def __str__(self):
        price = self.price_display or "цена не указана"
        return f"{self.brand} {self.model_name} ({self.year}) — {price}"

    @property
    def title(self):
        return f"{self.brand} {self.model_name}"

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
    def mileage_display(self):
        if self.condition == self.Condition.NEW:
            return ""
        if not self.mileage_km:
            return ""
        return f"{self.mileage_km:,}".replace(",", " ") + " км"

    @property
    def whatsapp_url(self):
        digits = "".join(ch for ch in (self.dealership.phone or "") if ch.isdigit())
        if not digits:
            return ""
        details = ", ".join(filter(None, [
            self.title,
            str(self.year),
            self.price_display or None,
        ]))
        text = f"Здравствуйте! Интересует автомобиль: {details}" if details else "Здравствуйте! Интересует автомобиль."
        return f"https://wa.me/{digits}?text={urllib.parse.quote(text)}"


class CarPhoto(TimeStampedModel):
    car        = models.ForeignKey(Car, on_delete=models.CASCADE, related_name="photos")
    photo      = models.ImageField("Фото", upload_to="autosalon/cars/")
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    def save(self, *args, **kwargs):
        _compress_photo(self.photo)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name        = "Фото автомобиля"
        verbose_name_plural  = "Фото автомобиля"
        ordering             = ["sort_order", "id"]


class Lead(TimeStampedModel):
    """Заявка клиента — персистентный лид, в отличие от простого редиректа в WhatsApp:
    видна в кабинете салона, можно отследить статус и не потерять контакт."""

    class Status(models.TextChoices):
        NEW        = "new", _("Новая")
        CONTACTED  = "contacted", _("Связались")
        WON        = "won", _("Сделка")
        LOST       = "lost", _("Отказ")

    class Source(models.TextChoices):
        CAR_PAGE   = "car_page", _("Страница автомобиля")
        DEALERSHIP = "dealership", _("Страница автосалона")

    dealership = models.ForeignKey(AutoDealership, on_delete=models.CASCADE, related_name="leads")
    car        = models.ForeignKey(Car, on_delete=models.SET_NULL, null=True, blank=True, related_name="leads")
    name       = models.CharField("Имя", max_length=120, blank=True, default="")
    phone      = models.CharField("Телефон", max_length=50)
    message    = models.TextField("Сообщение", blank=True, default="")
    source     = models.CharField("Источник", max_length=20, choices=Source.choices, default=Source.CAR_PAGE)
    status     = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW)
    manager    = models.ForeignKey(DealershipMembership, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="leads", verbose_name="Ответственный менеджер")
    note       = models.TextField("Заметка менеджера", blank=True, default="")

    class Meta:
        verbose_name        = "Лид"
        verbose_name_plural  = "Лиды"
        ordering             = ["-created_at"]

    def __str__(self):
        return f"{self.name or self.phone} — {self.dealership} ({self.get_status_display()})"

    @property
    def phone_digits(self):
        return "".join(ch for ch in (self.phone or "") if ch.isdigit())
