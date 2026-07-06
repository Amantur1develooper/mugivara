import secrets
from django.db import models
from core.models import Restaurant


class RestaurantPrintConfig(models.Model):
    """Настройки облачной печати для ресторана."""
    restaurant = models.OneToOneField(
        Restaurant, on_delete=models.CASCADE, related_name="print_config"
    )
    enabled = models.BooleanField("Печать включена", default=False)
    token = models.CharField(max_length=64, unique=True, editable=False)
    last_heartbeat = models.DateTimeField("Последний heartbeat", null=True, blank=True)
    receipt_printer_group = models.ForeignKey(
        "PrinterGroup",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="Принтер для итоговых чеков",
        help_text="Этот принтер будет получать чеки при закрытии стола/заказа",
    )

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def is_agent_online(self):
        if not self.last_heartbeat:
            return False
        from django.utils import timezone
        return (timezone.now() - self.last_heartbeat).total_seconds() < 300

    def __str__(self):
        return f"{self.restaurant.name_ru} — печать"

    class Meta:
        verbose_name = "Настройки печати"
        verbose_name_plural = "Настройки печати"


class PrinterGroup(models.Model):
    """Группа принтеров (кухня, бар, салат и т.д.)."""
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="printer_groups"
    )
    name = models.CharField("Код группы", max_length=30)   # "kitchen", "bar"
    display_name = models.CharField("Название", max_length=100)  # "Кухня", "Бар"

    class Meta:
        unique_together = ("restaurant", "name")
        verbose_name = "Группа принтеров"
        verbose_name_plural = "Группы принтеров"

    def __str__(self):
        return f"{self.restaurant.name_ru}: {self.display_name}"


class Printer(models.Model):
    """Физический принтер, привязанный к группе."""
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="printers"
    )
    group = models.ForeignKey(
        PrinterGroup, on_delete=models.CASCADE, related_name="printers"
    )
    windows_name = models.CharField(
        "Имя принтера в Windows", max_length=200,
        help_text="Точное имя как в списке принтеров Windows"
    )
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Принтер"
        verbose_name_plural = "Принтеры"

    def __str__(self):
        return f"{self.group.display_name} → {self.windows_name}"


class PrintJob(models.Model):
    """Задание на печать, агент забирает и печатает."""
    class Status(models.TextChoices):
        NEW        = "new",        "Новый"
        PROCESSING = "processing", "Печатается"
        PRINTED    = "printed",    "Напечатан"
        ERROR      = "error",      "Ошибка"

    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="print_jobs"
    )
    order_id = models.IntegerField("ID заказа", null=True, blank=True)
    group = models.ForeignKey(
        PrinterGroup, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="jobs"
    )
    content = models.TextField("Содержимое (plain text)")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEW
    )
    retries = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    printed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Задание печати"
        verbose_name_plural = "Задания печати"

    def __str__(self):
        return f"Job #{self.id} [{self.status}] order={self.order_id}"
