from django.conf import settings
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


class EcoMembership(models.Model):
    """Привязка пользователя к эко-проекту — даёт доступ к заявкам в кабинете."""
    user    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="eco_memberships", verbose_name="Пользователь")
    project = models.ForeignKey(EcoProject, on_delete=models.CASCADE,
                                related_name="memberships", verbose_name="Проект")

    class Meta:
        verbose_name        = "Доступ к эко-проекту"
        verbose_name_plural = "Доступы к эко-проектам"
        unique_together     = [("user", "project")]

    def __str__(self):
        return f"{self.user} → {self.project}"


class EcoApplication(TimeStampedModel):
    """Заявка на эко-услугу, поданная через сайт."""

    class Status(models.TextChoices):
        NEW        = "new",        "Новая"
        IN_WORK    = "in_work",    "В работе"
        DONE       = "done",       "Выполнена"
        CANCELLED  = "cancelled",  "Отменена"

    project      = models.ForeignKey(EcoProject, on_delete=models.CASCADE,
                                     related_name="applications", verbose_name="Проект")
    service      = models.ForeignKey(EcoService, on_delete=models.SET_NULL,
                                     null=True, blank=True,
                                     related_name="applications", verbose_name="Услуга")
    service_name = models.CharField("Название услуги", max_length=300)
    fio          = models.CharField("ФИО", max_length=300)
    phone        = models.CharField("Телефон", max_length=50, blank=True, default="")
    address      = models.CharField("Адрес / район", max_length=500)
    comment      = models.TextField("Комментарий", blank=True, default="")
    status       = models.CharField("Статус", max_length=20,
                                    choices=Status.choices, default=Status.NEW)

    class Meta:
        verbose_name        = "Заявка"
        verbose_name_plural = "Заявки"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.fio} — {self.service_name}"
