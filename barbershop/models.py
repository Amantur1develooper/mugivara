from django.conf import settings
from django.db import models
from core.models import TimeStampedModel
import os
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image


def _compress(field, max_side=900, quality=82):
    if not (field and hasattr(field, "file")):
        return False
    try:
        field.file.seek(0)
        img = Image.open(field).convert("RGB")
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=6)
        buf.seek(0)
        name = os.path.splitext(field.name)[0] + ".webp"
        field.save(name, ContentFile(buf.read()), save=False)
        return True
    except Exception:
        return False


class Barbershop(TimeStampedModel):
    name          = models.CharField("Название", max_length=200)
    slug          = models.SlugField(max_length=220, unique=True)
    tagline       = models.CharField("Слоган", max_length=300, blank=True, default="")
    description   = models.TextField("Описание", blank=True, default="")
    logo          = models.ImageField("Логотип", upload_to="barbershop/logos/", blank=True, null=True)
    cover         = models.ImageField("Обложка", upload_to="barbershop/covers/", blank=True, null=True)
    address       = models.CharField("Адрес", max_length=300, blank=True, default="")
    phone         = models.CharField("Телефон", max_length=50, blank=True, default="")
    whatsapp      = models.CharField("WhatsApp (с кодом страны)", max_length=30, blank=True, default="",
                                     help_text="996700123456 — без + и пробелов")
    working_hours = models.CharField("Часы работы", max_length=200, blank=True, default="")
    map_url       = models.URLField("Ссылка на карту", blank=True, default="")
    tg_chat_id    = models.CharField("TG Chat ID", max_length=50, blank=True, default="")
    tg_thread_id  = models.PositiveIntegerField("TG Thread ID", null=True, blank=True)
    is_active     = models.BooleanField("Активен", default=True)
    sort_order    = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Барбершоп"
        verbose_name_plural = "Барбершопы"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        _compress(self.logo)
        _compress(self.cover)
        super().save(*args, **kwargs)


class BarbershopMembership(TimeStampedModel):
    user       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="barbershop_memberships")
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="memberships")

    class Meta:
        verbose_name = "Доступ к барбершопу"
        verbose_name_plural = "Доступы к барбершопам"
        unique_together = ("user", "barbershop")

    def __str__(self):
        return f"{self.user} → {self.barbershop}"


class ServiceCategory(TimeStampedModel):
    barbershop = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="service_categories")
    name       = models.CharField("Категория", max_length=100)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)
    is_active  = models.BooleanField("Активна", default=True)

    class Meta:
        verbose_name = "Категория услуг"
        verbose_name_plural = "Категории услуг"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.barbershop} / {self.name}"


class Service(TimeStampedModel):
    barbershop    = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="services")
    category      = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name="services")
    name          = models.CharField("Название", max_length=200)
    description   = models.TextField("Описание", blank=True, default="")
    price         = models.DecimalField("Цена (сом)", max_digits=10, decimal_places=0, default=0)
    duration_min  = models.PositiveSmallIntegerField("Длительность (мин)", default=30)
    is_active     = models.BooleanField("Активна", default=True)
    sort_order    = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.barbershop} / {self.name}"


class Barber(TimeStampedModel):
    barbershop  = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="barbers")
    name        = models.CharField("Имя", max_length=200)
    photo       = models.ImageField("Фото", upload_to="barbershop/barbers/", blank=True, null=True)
    experience  = models.CharField("Опыт", max_length=100, blank=True, default="",
                                   help_text="Например: 5 лет опыта")
    bio         = models.TextField("Описание", blank=True, default="")
    services    = models.ManyToManyField(Service, blank=True, related_name="barbers",
                                         verbose_name="Услуги", through="BarberService")
    is_active   = models.BooleanField("Активен", default=True)
    sort_order  = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Мастер"
        verbose_name_plural = "Мастера"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.barbershop} / {self.name}"

    def save(self, *args, **kwargs):
        _compress(self.photo)
        super().save(*args, **kwargs)


WEEKDAY_CHOICES = [
    (0, "Понедельник"), (1, "Вторник"), (2, "Среда"),
    (3, "Четверг"), (4, "Пятница"), (5, "Суббота"), (6, "Воскресенье"),
]


class BarberSchedule(TimeStampedModel):
    barber     = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name="schedules")
    weekday    = models.PositiveSmallIntegerField("День недели", choices=WEEKDAY_CHOICES)
    start_time = models.TimeField("Начало работы", default="09:00")
    end_time   = models.TimeField("Конец работы", default="20:00")
    is_working = models.BooleanField("Рабочий день", default=True)

    class Meta:
        verbose_name = "График мастера"
        verbose_name_plural = "Графики мастеров"
        unique_together = ("barber", "weekday")
        ordering = ["weekday"]

    def __str__(self):
        return f"{self.barber.name} / {self.get_weekday_display()}"


class BarberService(TimeStampedModel):
    barber  = models.ForeignKey(Barber, on_delete=models.CASCADE, related_name="barber_services")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="barber_services")

    class Meta:
        verbose_name = "Услуга мастера"
        verbose_name_plural = "Услуги мастера"
        unique_together = ("barber", "service")

    def __str__(self):
        return f"{self.barber.name} → {self.service.name}"


APPOINTMENT_STATUS = [
    ("new",       "Новая"),
    ("confirmed", "Подтверждена"),
    ("done",      "Выполнена"),
    ("cancelled", "Отменена"),
    ("no_show",   "Не пришёл"),
]

PAYMENT_METHOD = [
    ("cash",     "Наличные"),
    ("transfer", "Перевод"),
    ("card",     "Карта"),
    ("other",    "Другое"),
]

SOURCE_CHOICES = [
    ("online",  "Онлайн"),
    ("offline", "Офлайн / Касса"),
]


class Appointment(TimeStampedModel):
    barbershop      = models.ForeignKey(Barbershop, on_delete=models.CASCADE, related_name="appointments")
    barber          = models.ForeignKey(Barber, on_delete=models.SET_NULL, null=True, related_name="appointments")
    service         = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, related_name="appointments")
    service_name    = models.CharField("Услуга (снимок)", max_length=200, blank=True, default="")
    barber_name     = models.CharField("Мастер (снимок)", max_length=200, blank=True, default="")
    price_snapshot  = models.DecimalField("Цена", max_digits=10, decimal_places=0, default=0)
    duration_min    = models.PositiveSmallIntegerField("Длительность (мин)", default=30)
    customer_name   = models.CharField("Имя клиента", max_length=200)
    customer_phone  = models.CharField("Телефон", max_length=50, blank=True, default="")
    appt_date       = models.DateField("Дата")
    appt_time       = models.TimeField("Время")
    status          = models.CharField("Статус", max_length=20, choices=APPOINTMENT_STATUS, default="new")
    source          = models.CharField("Источник", max_length=10, choices=SOURCE_CHOICES, default="online")
    is_paid         = models.BooleanField("Оплачено", default=False)
    payment_method  = models.CharField("Способ оплаты", max_length=20, choices=PAYMENT_METHOD,
                                        blank=True, default="")
    comment         = models.TextField("Комментарий клиента", blank=True, default="")
    notes           = models.TextField("Заметки администратора", blank=True, default="")

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        ordering = ["-appt_date", "-appt_time"]

    def __str__(self):
        return f"#{self.id} {self.customer_name} → {self.service_name} {self.appt_date} {self.appt_time}"

    def save(self, *args, **kwargs):
        if self.service and not self.service_name:
            self.service_name = self.service.name
        if self.barber and not self.barber_name:
            self.barber_name = self.barber.name
        if self.service and not self.price_snapshot:
            self.price_snapshot = self.service.price
        if self.service and not self.duration_min:
            self.duration_min = self.service.duration_min
        super().save(*args, **kwargs)
