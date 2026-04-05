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


def _compress_photo(image_field, size=(1200, 800), quality=85):
    """Сжимает фото в WebP. Возвращает ContentFile или None."""
    try:
        img = Image.open(image_field)
        img = img.convert("RGB")
        img.thumbnail(size, Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=quality)
        name = os.path.splitext(os.path.basename(image_field.name))[0] + ".webp"
        return ContentFile(buf.getvalue(), name=name)
    except Exception:
        return None


class Market(TimeStampedModel):
    name_ru        = models.CharField("Название", max_length=200)
    slug           = models.SlugField(max_length=220, unique=True)
    description_ru = models.TextField("Описание", blank=True, default="")
    address        = models.CharField("Адрес", max_length=300, blank=True, default="")
    working_hours  = models.CharField("Часы работы", max_length=200, blank=True, default="",
                                      help_text="Пример: Пн–Вс: 08:00–20:00")
    phone          = models.CharField("Номер WhatsApp / телефон", max_length=50, blank=True, default="")
    map_url        = models.URLField("Ссылка на карту", blank=True, default="")
    website_url    = models.URLField("Сайт рынка", blank=True, default="")
    logo           = models.ImageField("Логотип / главное фото", upload_to="markets/logos/", blank=True, null=True)
    photo1         = models.ImageField("Фото 1", upload_to="markets/photos/", blank=True, null=True)
    photo2         = models.ImageField("Фото 2", upload_to="markets/photos/", blank=True, null=True)
    photo3         = models.ImageField("Фото 3", upload_to="markets/photos/", blank=True, null=True)
    is_active      = models.BooleanField("Активен", default=True)
    sort_order     = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Рынок"
        verbose_name_plural = "Рынки"
        ordering            = ["sort_order", "name_ru"]

    def __str__(self):
        return self.name_ru

    @property
    def photos(self):
        return [f for f in (self.photo1, self.photo2, self.photo3) if f]

    @property
    def whatsapp_url(self):
        if not self.phone:
            return None
        digits = "".join(c for c in self.phone if c.isdigit())
        return f"https://wa.me/{digits}"

    def save(self, *args, **kwargs):
        # Compress logo
        if self.logo and hasattr(self.logo, "file"):
            try:
                self.logo.file.seek(0)
                compressed = _compress_photo(self.logo, size=(600, 600))
                if compressed:
                    self.logo.save(compressed.name, compressed, save=False)
            except Exception:
                pass

        for fname in ("photo1", "photo2", "photo3"):
            field = getattr(self, fname)
            if field and hasattr(field, "file"):
                try:
                    field.file.seek(0)
                    compressed = _compress_photo(field, size=(1200, 800))
                    if compressed:
                        getattr(self, fname).save(compressed.name, compressed, save=False)
                except Exception:
                    pass

        super().save(*args, **kwargs)
