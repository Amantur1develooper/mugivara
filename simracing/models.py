from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from io import BytesIO
import os
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


class SimRacingVenue(models.Model):
    name         = models.CharField("Название", max_length=200)
    slug         = models.SlugField(max_length=220, unique=True)
    tagline      = models.CharField("Слоган", max_length=300, blank=True, default="")
    description  = models.TextField("Описание", blank=True, default="")
    logo         = models.ImageField("Логотип", upload_to="simracing/logos/", blank=True, null=True)
    cover        = models.ImageField("Обложка", upload_to="simracing/covers/", blank=True, null=True)
    address      = models.CharField("Адрес", max_length=300, blank=True, default="")
    phone        = models.CharField("Телефон", max_length=50, blank=True, default="")
    whatsapp     = models.CharField("WhatsApp", max_length=30, blank=True, default="",
                                    help_text="996700123456 — без + и пробелов")
    working_hours = models.CharField("Часы работы", max_length=200, blank=True, default="")
    map_url      = models.URLField("Ссылка на карту", blank=True, default="")
    tg_chat_id   = models.CharField("TG Chat ID", max_length=50, blank=True, default="")
    tg_thread_id = models.PositiveIntegerField("TG Thread ID", null=True, blank=True)
    is_active    = models.BooleanField("Активен", default=True)
    sort_order   = models.PositiveSmallIntegerField("Порядок", default=0)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Симрейсинг-площадка"
        verbose_name_plural = "Симрейсинг-площадки"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        _compress(self.logo)
        _compress(self.cover)
        super().save(*args, **kwargs)


class SimRacingMembership(models.Model):
    user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="simracing_memberships")
    venue = models.ForeignKey(SimRacingVenue, on_delete=models.CASCADE, related_name="memberships")

    class Meta:
        verbose_name = "Доступ к симрейсингу"
        verbose_name_plural = "Доступы к симрейсингу"
        unique_together = ("user", "venue")

    def __str__(self):
        return f"{self.user} → {self.venue}"


class Machine(models.Model):
    class Type(models.TextChoices):
        KART_STANDARD = "kart_standard", "Стандартный картинг"
        KART_EURO     = "kart_euro",     "Евроспор картинг"
        SIMULATOR     = "simulator",     "Автосимулятор"

    venue      = models.ForeignKey(SimRacingVenue, on_delete=models.CASCADE, related_name="machines")
    name       = models.CharField("Название", max_length=120)
    type       = models.CharField("Тип", max_length=20, choices=Type.choices, default=Type.KART_STANDARD)
    photo      = models.ImageField("Фото", upload_to="simracing/machines/", blank=True, null=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active  = models.BooleanField("В работе", default=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Машина"
        verbose_name_plural = "Машины"

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"

    def save(self, *args, **kwargs):
        _compress(self.photo)
        super().save(*args, **kwargs)

    @property
    def active_session(self):
        return self.sessions.filter(status=Session.Status.ACTIVE).first()


class SessionType(models.Model):
    """Прайс-лист: тип машины + длительность → цена"""
    venue          = models.ForeignKey(SimRacingVenue, on_delete=models.CASCADE, related_name="session_types")
    machine_type   = models.CharField("Тип машины", max_length=20, choices=Machine.Type.choices)
    duration_minutes = models.PositiveIntegerField("Длительность (мин)")
    price          = models.DecimalField("Цена (сом)", max_digits=8, decimal_places=0, default=0)
    sort_order     = models.PositiveIntegerField("Порядок", default=0)
    is_active      = models.BooleanField("Активен", default=True)

    class Meta:
        ordering = ["machine_type", "sort_order", "duration_minutes"]
        unique_together = [["venue", "machine_type", "duration_minutes"]]
        verbose_name = "Тип сессии (прайс)"
        verbose_name_plural = "Прайс-лист"

    def __str__(self):
        return f"{self.get_machine_type_display()} — {self.duration_minutes} мин — {self.price} сом"


class Session(models.Model):
    class Status(models.TextChoices):
        ACTIVE   = "active",   "Активна"
        DONE     = "done",     "Завершена"
        CANCELED = "canceled", "Отменена"

    venue        = models.ForeignKey(SimRacingVenue, on_delete=models.CASCADE, related_name="sessions")
    machine      = models.ForeignKey(Machine, on_delete=models.CASCADE, related_name="sessions")
    session_type = models.ForeignKey(SessionType, on_delete=models.SET_NULL, null=True, blank=True,
                                     verbose_name="Тип сессии")

    customer_name  = models.CharField("Имя клиента", max_length=200, blank=True, default="")
    customer_phone = models.CharField("Телефон", max_length=80, blank=True, default="")

    duration_minutes = models.PositiveIntegerField("Длительность (мин)")
    price            = models.DecimalField("Цена (сом)", max_digits=8, decimal_places=0, default=0)
    machine_type_snapshot = models.CharField(max_length=20, blank=True, default="")
    source           = models.CharField("Источник", max_length=10,
                                        choices=[("online","Онлайн"),("offline","Касса")],
                                        default="online")

    status     = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField("Начало", default=timezone.now)
    ended_at   = models.DateTimeField("Конец (фактический)", null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Сессия"
        verbose_name_plural = "Сессии"

    def __str__(self):
        return f"#{self.id} {self.machine.name} {self.duration_minutes}мин"

    def save(self, *args, **kwargs):
        if self.machine_id and not self.machine_type_snapshot:
            self.machine_type_snapshot = self.machine.type
        super().save(*args, **kwargs)

    @property
    def ends_at(self):
        from datetime import timedelta
        return self.started_at + timedelta(minutes=self.duration_minutes)

    @property
    def is_overtime(self):
        return self.status == self.Status.ACTIVE and timezone.now() > self.ends_at

    @property
    def remaining_seconds(self):
        if self.status != self.Status.ACTIVE:
            return 0
        delta = self.ends_at - timezone.now()
        return max(0, int(delta.total_seconds()))
