from django.db import models
import re
from core.models import TimeStampedModel


class EcoProject(TimeStampedModel):
    name          = models.CharField("Название", max_length=200)
    slug          = models.SlugField(max_length=220, unique=True)
    description   = models.TextField("Описание", blank=True, default="")
    address       = models.CharField("Адрес", max_length=300, blank=True, default="")
    phone         = models.CharField("Телефон / WhatsApp", max_length=50, blank=True, default="")
    working_hours = models.CharField("Часы работы", max_length=200, blank=True, default="",
                                     help_text="Пример: Пн–Вс: 08:00–20:00")
    map_url       = models.URLField("Ссылка на карту", blank=True, default="")
    logo          = models.ImageField("Логотип / фото", upload_to="eco/logos/", blank=True, null=True)
    is_active     = models.BooleanField("Активен", default=True)
    sort_order    = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Эко-проект"
        verbose_name_plural = "Эко-проекты"
        ordering            = ["sort_order", "name"]

    def __str__(self):
        return self.name

    @property
    def whatsapp_digits(self):
        return re.sub(r"\D", "", self.phone or "")

    @property
    def whatsapp_url(self):
        d = self.whatsapp_digits
        return f"https://wa.me/{d}" if d else None


class EcoService(TimeStampedModel):
    project     = models.ForeignKey(EcoProject, on_delete=models.CASCADE, related_name="services",
                                    verbose_name="Проект")
    name        = models.CharField("Название услуги", max_length=300)
    description = models.TextField("Описание услуги", blank=True, default="")
    price       = models.DecimalField("Цена (сом)", max_digits=10, decimal_places=0, default=0)
    price_note  = models.CharField("Примечание к цене", max_length=100, blank=True, default="",
                                   help_text="Например: за вывоз, за кг, бесплатно")
    is_active   = models.BooleanField("Активна", default=True)
    sort_order  = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Услуга"
        verbose_name_plural = "Услуги"
        ordering            = ["sort_order", "id"]

    def __str__(self):
        return f"{self.project}: {self.name}"
