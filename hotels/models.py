from django.db import models
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image
import os


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Hotel(TimeStampedModel):
    name_ru = models.CharField("Название (RU)", max_length=200)
    name_ky = models.CharField("Название (KY)", max_length=200, blank=True, default="")
    name_en = models.CharField("Название (EN)", max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=220, unique=True)
    logo = models.ImageField("Логотип", upload_to="hotels/logos/", blank=True, null=True)
    is_active = models.BooleanField("Активен", default=True)
    rating = models.DecimalField("Рейтинг", max_digits=3, decimal_places=1, default=0.0)
    about_ru = models.TextField("О нас", blank=True, default="")
    external_url = models.URLField("Внешний сайт", blank=True, default="")

    class Meta:
        verbose_name = "Отель"
        verbose_name_plural = "Отели"
        ordering = ["-rating", "name_ru"]

    def __str__(self):
        return self.name_ru


class HotelBranch(TimeStampedModel):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="branches")
    name_ru = models.CharField("Название (RU)", max_length=200)
    name_ky = models.CharField("Название (KY)", max_length=200, blank=True, default="")
    name_en = models.CharField("Название (EN)", max_length=200, blank=True, default="")
    address = models.CharField("Адрес", max_length=300, blank=True)
    phone = models.CharField("Телефон", max_length=50, blank=True)
    map_url = models.URLField("Ссылка на карту", blank=True, default="")
    is_active = models.BooleanField("Активен", default=True)
    cover_photo = models.ImageField("Обложка", upload_to="hotels/covers/", blank=True, null=True)
    external_url = models.URLField("Внешний сайт / приложение", blank=True, default="")

    class Meta:
        verbose_name = "Филиал отеля"
        verbose_name_plural = "Филиалы отелей"

    def __str__(self):
        return f"{self.hotel.name_ru} — {self.name_ru}"


class RoomCategory(TimeStampedModel):
    branch = models.ForeignKey(HotelBranch, on_delete=models.CASCADE, related_name="room_categories")
    name_ru = models.CharField("Категория", max_length=100)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Категория номеров"
        verbose_name_plural = "Категории номеров"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name_ru} ({self.branch})"


def _compress_photo(field, max_size=(1200, 900), quality=85):
    if not field or not hasattr(field, "file"):
        return None
    try:
        field.file.seek(0)
        img = Image.open(field).convert("RGB")
        img.thumbnail(max_size, Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=6)
        buf.seek(0)
        name = os.path.splitext(field.name)[0] + ".webp"
        return name, ContentFile(buf.read())
    except Exception:
        return None


class Room(TimeStampedModel):
    branch = models.ForeignKey(HotelBranch, on_delete=models.CASCADE, related_name="rooms")
    category = models.ForeignKey(
        RoomCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="rooms",
        verbose_name="Категория",
    )
    name_ru = models.CharField("Название номера", max_length=200)
    description_ru = models.TextField("Описание", blank=True, default="")
    amenities_ru = models.TextField(
        "Что включено",
        blank=True, default="",
        help_text="Каждый пункт с новой строки: WiFi, Завтрак, TV ..."
    )
    price_per_night = models.DecimalField(
        "Базовая цена (1 гость) / ночь (сом)",
        max_digits=10, decimal_places=0, default=0,
    )
    price_per_extra_guest = models.DecimalField(
        "Доплата за каждого доп. гостя / ночь (сом)",
        max_digits=10, decimal_places=0, default=0,
        help_text="Пример: база 2000, доплата 1000 → 1 гость=2000, 2 гостя=3000, 3 гостя=4000",
    )
    max_guests = models.PositiveSmallIntegerField("Макс. гостей", default=2)
    is_available = models.BooleanField("Доступен", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    photo1 = models.ImageField("Фото 1 (главное)", upload_to="hotels/rooms/", blank=True, null=True)
    photo2 = models.ImageField("Фото 2", upload_to="hotels/rooms/", blank=True, null=True)
    photo3 = models.ImageField("Фото 3", upload_to="hotels/rooms/", blank=True, null=True)

    class Meta:
        verbose_name = "Номер"
        verbose_name_plural = "Номера"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name_ru} ({self.branch})"

    def save(self, *args, **kwargs):
        for fname in ("photo1", "photo2", "photo3"):
            result = _compress_photo(getattr(self, fname))
            if result:
                name, content = result
                getattr(self, fname).save(name, content, save=False)
        super().save(*args, **kwargs)

    @property
    def photos(self):
        return [p for p in (self.photo1, self.photo2, self.photo3) if p]

    @property
    def amenities_list(self):
        return [ln.strip() for ln in self.amenities_ru.splitlines() if ln.strip()]
