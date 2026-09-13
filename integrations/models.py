from django.db import models
from core.models import Branch, TimeStampedModel

class TelegramRecipient(TimeStampedModel):
    class Kind(models.TextChoices):
        USER = "user", "Личка"
        GROUP = "group", "Группа"
        CHANNEL = "channel", "Канал"

    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="tg_recipients")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.USER)
    title = models.CharField(max_length=120, blank=True)   # "Менеджер Айбек", "Группа кухни"
    chat_id = models.CharField(max_length=64)              # может быть -100...
    is_active = models.BooleanField(default=True)

    # опционально: темы в супергруппах (topic)
    message_thread_id = models.PositiveIntegerField(null=True, blank=True)

    # можно гибко отключать уведомления по типу
    notify_new_orders = models.BooleanField(default=True)
    notify_status_changes = models.BooleanField(default=True)

    class Meta:
        unique_together = ("branch", "chat_id")
        ordering = ("-is_active", "kind", "id")

    def __str__(self):
        return f"{self.branch.name_ru} -> {self.chat_id} ({self.kind})"


class ShopTelegramRecipient(TimeStampedModel):
    """Получатель Telegram-уведомлений о заказах магазина (сайт + касса)."""
    class Kind(models.TextChoices):
        USER = "user", "Личка"
        GROUP = "group", "Группа"
        CHANNEL = "channel", "Канал"

    branch = models.ForeignKey(
        "shops.StoreBranch", on_delete=models.CASCADE, related_name="tg_recipients",
        verbose_name="Филиал магазина",
    )
    kind = models.CharField("Тип", max_length=10, choices=Kind.choices, default=Kind.GROUP)
    title = models.CharField("Название", max_length=120, blank=True)
    chat_id = models.CharField("Chat ID", max_length=64)
    is_active = models.BooleanField("Активен", default=True)

    message_thread_id = models.PositiveIntegerField("Topic ID (для супергрупп)", null=True, blank=True)
    notify_new_orders = models.BooleanField("Уведомлять о новых заказах", default=True)

    class Meta:
        unique_together = ("branch", "chat_id")
        ordering = ("-is_active", "kind", "id")
        verbose_name = "Telegram-получатель (магазин)"
        verbose_name_plural = "Telegram-получатели (магазины)"

    def __str__(self):
        return f"{self.branch.name_ru} -> {self.chat_id} ({self.kind})"


class BranchTelegramLink(TimeStampedModel):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="tg_links")
    recipient = models.ForeignKey(TelegramRecipient, on_delete=models.CASCADE, related_name="branch_links")

    notify_orders = models.BooleanField(default=True)
    notify_bookings = models.BooleanField(default=True)

    class Meta:
        unique_together = ("branch", "recipient")

    def __str__(self):
        return f"{self.branch} -> {self.recipient}"
