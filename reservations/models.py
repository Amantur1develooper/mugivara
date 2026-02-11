from django.db import models, transaction
from django.utils import timezone
from core.models import Branch, TimeStampedModel
import secrets
from core.models import Branch


class Floor(TimeStampedModel):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="floors")
    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
        
    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Этаж"
        verbose_name_plural = "Этажы"

    def __str__(self):
        return f"{self.branch} — {self.name_ru}"


class Place(TimeStampedModel):
    class Type(models.TextChoices):
        TABLE = "table", "Стол"
        CABIN = "cabin", "Кабинка"

    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="places")
    title = models.CharField(max_length=120)  # "Стол 1", "VIP 2"
    type = models.CharField(max_length=10, choices=Type.choices, default=Type.TABLE)
    seats = models.PositiveIntegerField(default=2)

    # для плана зала (если нужно)
    x = models.IntegerField(default=40)
    y = models.IntegerField(default=40)
    photo = models.ImageField(upload_to="places/photos/", blank=True, null=True)
    token = models.CharField(max_length=32, default="", blank=True, )
    is_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(10)[:20]
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Место"
        verbose_name_plural = "Место"
        constraints = [
            models.UniqueConstraint(fields=["token"], name="uniq_place_token"),
        ]
        
    def __str__(self):
        return self.title


class Booking(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активна"
        ARRIVED = "arrived", "Гость пришёл"
        CLOSED = "closed", "Закрыта"
        CANCELED = "canceled", "Отменена"

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="bookings")
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="bookings")

    customer_name = models.CharField(max_length=200, blank=True, default="")
    customer_phone = models.CharField(max_length=80, blank=True, default="")
    guests_count = models.PositiveIntegerField(default=2)
    comment = models.CharField(max_length=300, blank=True, default="")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ("-id",)
        verbose_name = "Бронь"
        verbose_name_plural = "Брони"

    @classmethod
    def create_active_booking(cls, *, branch, place, customer_name="", customer_phone="", guests_count=2, comment=""):
        """
        ✅ Делает бронь “занято для всех”, пока админ/кассир не снимет статус.
        ✅ Защита от гонок: select_for_update.
        """
        with transaction.atomic():
            # блокируем место на время проверки/создания
            cls.objects.select_for_update().filter(branch=branch, place=place)

            busy_exists = cls.objects.filter(
                branch=branch,
                place=place,
                status__in=[cls.Status.ACTIVE, cls.Status.ARRIVED],
            ).exists()

            if busy_exists:
                raise ValueError("PLACE_BUSY")

            return cls.objects.create(
                branch=branch,
                place=place,
                customer_name=customer_name,
                customer_phone=customer_phone,
                guests_count=guests_count,
                comment=comment,
                status=cls.Status.ACTIVE,
            )

    def __str__(self):
        return f"#{self.id} {self.branch_id} {self.place_id} {self.status}"


class BranchStaffToken(models.Model):
    
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="staff_tokens")
    title = models.CharField(max_length=120)  # например "Кассир Айгерим"
    token = models.CharField(max_length=64, unique=True, db_index=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.branch_id} | {self.title}"
