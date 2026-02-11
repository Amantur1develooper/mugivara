from django.db import models

# Create your models here.
import secrets
from django.db import models
from core.models import Branch, TimeStampedModel

class Table(TimeStampedModel):
    class TableType(models.TextChoices):
        TABLE = "table", "Стол"
        BOOTH = "booth", "Кабинка"
        VIP = "vip", "VIP"

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="tables")
    number = models.CharField(max_length=20)  # "1", "A1"
    type = models.CharField(max_length=10, choices=TableType.choices, default=TableType.TABLE)
    qr_token = models.CharField(max_length=64, unique=True, editable=False)

    def save(self, *args, **kwargs):
        if not self.qr_token:
            self.qr_token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.branch} / стол {self.number}"
    
    class Meta:
        verbose_name = "Стол"
        verbose_name_plural = "Столы"
        
class TableSession(TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name="sessions")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.table} ({self.status})"
