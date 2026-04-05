# pharmacy/models.py
from django.db import models
from core.models import TimeStampedModel

class Pharmacy(TimeStampedModel):
    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=220, unique=True)
    logo = models.ImageField(upload_to="pharmacies/logos/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name_ru


class PharmacyBranch(TimeStampedModel):
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name="branches")

    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")

    address = models.CharField(max_length=300, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    is_active = models.BooleanField(default=True)

    cover_photo = models.ImageField(upload_to="pharmacies/branches/covers/", blank=True, null=True)

    def __str__(self):
        return f"{self.pharmacy.name_ru} — {self.name_ru}"


class DrugCategory(TimeStampedModel):
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name="categories")

    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")

    slug = models.SlugField(max_length=220)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("pharmacy", "slug")
        ordering = ("sort_order", "id")

    def __str__(self):
        return self.name_ru


class Drug(TimeStampedModel):
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name="drugs")

    name_ru = models.CharField(max_length=220)
    name_ky = models.CharField(max_length=220, blank=True, default="")
    name_en = models.CharField(max_length=220, blank=True, default="")

    description_ru = models.TextField(blank=True, default="")
    description_ky = models.TextField(blank=True, default="")
    description_en = models.TextField(blank=True, default="")

    photo = models.ImageField(upload_to="pharmacies/drugs/photos/", blank=True, null=True)

    # ссылка на видео-обзор
    youtube_url = models.URLField(blank=True, default="")

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name_ru


class DrugInCategory(TimeStampedModel):
    category = models.ForeignKey(DrugCategory, on_delete=models.CASCADE, related_name="drug_links")
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name="category_links")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("category", "drug")
        ordering = ("sort_order", "id")


class BranchDrug(TimeStampedModel):
    """
    В каждом филиале — своё наличие/цена/доступность.
    """
    branch = models.ForeignKey(PharmacyBranch, on_delete=models.CASCADE, related_name="branch_drugs")
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name="branch_drugs")

    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_available = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("branch", "drug")
        ordering = ("sort_order", "id")
        
        
from django.conf import settings

class PharmacyOrder(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        CONFIRMED = "confirmed", "Подтвержден"
        DONE = "done", "Выдан"
        CANCELLED = "cancelled", "Отменён"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Наличные"
        ONLINE = "online", "Онлайн"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Не оплачено"
        PAID = "paid", "Оплачено"

    branch = models.ForeignKey(PharmacyBranch, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)

    customer_name = models.CharField(max_length=120, blank=True, default="")
    customer_phone = models.CharField(max_length=60, blank=True, default="")
    delivery_address = models.CharField(max_length=300, blank=True, default="")
    comment = models.TextField(blank=True, default="")

    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    payment_method = models.CharField(max_length=12, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    payment_status = models.CharField(max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)

    def __str__(self):
        return f"PhOrder #{self.id} ({self.branch})"


class PharmacyOrderItem(TimeStampedModel):
    order = models.ForeignKey(PharmacyOrder, on_delete=models.CASCADE, related_name="items")
    drug = models.ForeignKey(Drug, on_delete=models.CASCADE, related_name="order_items")

    qty = models.PositiveIntegerField(default=1)
    price_snapshot = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.order_id} - {self.drug_id}"

class PharmacyMembership(models.Model):
    class Role(models.TextChoices):
        OWNER   = "owner",   "Владелец"
        MANAGER = "manager", "Менеджер"

    user     = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pharmacy_memberships")
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name="memberships")
    role     = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.MANAGER)

    class Meta:
        verbose_name        = "Доступ к аптеке"
        verbose_name_plural = "Доступы к аптекам"
        unique_together     = ("user", "pharmacy")

    def __str__(self):
        return f"{self.user} → {self.pharmacy} ({self.role})"
