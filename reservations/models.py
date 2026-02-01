from django.db import models

# Create your models here.
from django.db import models, transaction
from django.utils import timezone
from django.db.models import Q
from core.models import Branch, TimeStampedModel


class Floor(TimeStampedModel):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="floors")
    name_ru = models.CharField("Название (RU)", max_length=120)
    name_ky = models.CharField("Название (KY)", max_length=120, blank=True, default="")
    name_en = models.CharField("Название (EN)", max_length=120, blank=True, default="")
    sort_order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Этаж"
        verbose_name_plural = "Этажи"

    def __str__(self):
        return f"{self.branch} — {self.name_ru}"


class Place(TimeStampedModel):
    class Type(models.TextChoices):
        TABLE = "table", "Стол"
        CABIN = "cabin", "Кабинка"

    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="places")
    type = models.CharField("Тип", max_length=10, choices=Type.choices, default=Type.TABLE)

    title = models.CharField("Название/Номер", max_length=60)  # например "Стол 7" или "Кабинка A"
    seats = models.PositiveIntegerField("Кол-во мест", default=4)
    is_active = models.BooleanField("Активен", default=True)

    # на будущее: план зала (координаты)
    x = models.PositiveIntegerField("X (план)", default=0)
    y = models.PositiveIntegerField("Y (план)", default=0)

    class Meta:
        ordering = ("type", "title", "id")
        verbose_name = "Место (стол/кабинка)"
        verbose_name_plural = "Места (столы/кабинки)"
        unique_together = ("floor", "title")

    def __str__(self):
        return f"{self.floor} — {self.title}"

class Status(models.TextChoices):
        ACTIVE = "active", "Занято (бронь)"
        CLEARED = "cleared", "Снято"
        CANCELLED = "cancelled", "Отменено"
class Booking(TimeStampedModel):
    
    class Status(models.TextChoices):
        ACTIVE = "active", "Забронировано"
        ARRIVED = "arrived", "Гость пришёл"
        CLEARED = "cleared", "Освободили"
        CANCELLED = "cancelled", "Отменено"

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="bookings")
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="bookings")

    status = models.CharField("Статус", max_length=12, choices=Status.choices, default=Status.ACTIVE)

    customer_name = models.CharField("Имя", max_length=120, blank=True, default="")
    customer_phone = models.CharField("Телефон", max_length=60, blank=True, default="")
    guests_count = models.PositiveIntegerField("Гостей", default=2)
    comment = models.TextField("Комментарий", blank=True, default="")

    # на будущее (если захочешь “по времени”), но сейчас не обязательно
    start_at = models.DateTimeField("Начало", null=True, blank=True)
    end_at = models.DateTimeField("Конец", null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "id")
        verbose_name = "Бронь"
        verbose_name_plural = "Брони"
        constraints = [
            # ВАЖНО: 1 активная бронь на 1 место (Postgres идеально)
            models.UniqueConstraint(
                fields=["place"],
                condition=Q(status__in=["active", "arrived"]),
                name="uniq_active_booking_per_place",
            )
        ]

    def __str__(self):
        return f"#{self.id} {self.branch} — {self.place} ({self.status})"

    @staticmethod
    def create_active_booking(*, branch: Branch, place: Place, **fields):
        """
        Безопасное создание брони (защита от гонок).
        """
        with transaction.atomic():
            locked_place = Place.objects.select_for_update().get(pk=place.pk)
            exists = Booking.objects.filter(place=locked_place, status=Booking.Status.ACTIVE).exists()
            if exists:
                raise ValueError("PLACE_BUSY")
            return Booking.objects.create(branch=branch, place=locked_place, status=Booking.Status.ACTIVE, **fields)
