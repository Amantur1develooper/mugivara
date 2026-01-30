from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from core.models import Branch, TimeStampedModel
from tables.models import Table

class Reservation(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        CONFIRMED = "confirmed", "Подтверждено"
        CANCELLED = "cancelled", "Отменено"
        NO_SHOW = "no_show", "Не пришли"

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="reservations")
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, blank=True)

    # Можно оставить как инфо для истории (но блокировка НЕ зависит от времени)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)

    guests = models.PositiveIntegerField(default=2)
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=50)
    comment = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # ВАЖНО: пока released_at пустой — стол занят
    released_at = models.DateTimeField(null=True, blank=True)

    def clean(self):
        super().clean()
        if self.table_id:
            qs = Reservation.objects.filter(
                table_id=self.table_id,
                released_at__isnull=True,
            ).exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError({"table": "Этот стол уже забронирован и занят до снятия брони админом/кассиром."})

    @property
    def is_locked(self) -> bool:
        return self.table_id is not None and self.released_at is None and self.status in {self.Status.PENDING, self.Status.CONFIRMED}

    def release(self):
        self.released_at = timezone.now()
        # можно помечать статусом отменено, чтобы закрыть бронь
        if self.status != self.Status.CANCELLED:
            self.status = self.Status.CANCELLED
        self.save(update_fields=["released_at", "status"])
