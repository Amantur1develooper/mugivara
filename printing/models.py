import secrets
from django.db import models
from core.models import Restaurant


class RestaurantPrintConfig(models.Model):
    """Настройки одного агента печати.

    Агент — это программа на ноутбуке в конкретной точке. Раньше запись была
    одна на ресторан, поэтому второй принтер во второй точке подключить было
    некуда. Теперь записей может быть несколько: у каждой свой токен, свой
    набор филиалов и свои принтеры.
    """
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="print_configs"
    )
    name = models.CharField(
        "Название кассы", max_length=100, blank=True, default="",
        help_text="Чтобы различать агенты: «Касса на Чуй», «Кухня на Датке»",
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
    # Принтер стоит в конкретной точке, а настройки печати — одни на ресторан.
    # Пока филиал был один, разницы не было; с двумя точками заказы второго
    # филиала уезжали на единственный агент и печатались в первом. Здесь
    # перечислены филиалы, чьи заказы этот агент печатает.
    branches = models.ManyToManyField(
        "core.Branch", blank=True,
        related_name="print_configs",
        verbose_name="Филиалы, заказы которых печатает агент",
        help_text="Снимите галочку с филиала, где принтера нет, — его чеки "
                  "не будут выходить на чужой точке",
    )

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def serves(self, branch):
        """Печатает ли этот агент заказы указанного филиала.

        Пустой список трактуем как «все филиалы»: так ведут себя настройки,
        заведённые до разделения по точкам, и молча выключать им печать нельзя.
        """
        if branch is None:
            return True
        ids = set(self.branches.values_list("id", flat=True))
        return (not ids) or (branch.id in ids)

    def served_branch_ids(self):
        """id обслуживаемых филиалов; пустой набор — значит все."""
        return set(self.branches.values_list("id", flat=True))

    def is_agent_online(self):
        if not self.last_heartbeat:
            return False
        from django.utils import timezone
        return (timezone.now() - self.last_heartbeat).total_seconds() < 300

    def __str__(self):
        label = self.name or ", ".join(self.branches.values_list("name_ru", flat=True))
        return f"{self.restaurant.name_ru} — печать ({label})" if label else \
               f"{self.restaurant.name_ru} — печать"

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
    # Устройство стоит в конкретной точке. Группа («кухня», «бар») общая на
    # ресторан — её выбирают у категорий меню, и дублировать по филиалам было
    # бы только путаницей, — а вот имя принтера в Windows у каждой точки своё.
    branch = models.ForeignKey(
        "core.Branch", null=True, blank=True,
        on_delete=models.CASCADE, related_name="printers",
        verbose_name="Филиал",
        help_text="Где физически стоит это устройство",
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
        where = f" ({self.branch.name_ru})" if self.branch_id else ""
        return f"{self.group.display_name}{where} → {self.windows_name}"


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
    # Филиал, где пробили заказ. Без него очередь была общей на ресторан,
    # и агент одной точки забирал чеки другой.
    branch = models.ForeignKey(
        "core.Branch", null=True, blank=True,
        on_delete=models.CASCADE, related_name="print_jobs",
        verbose_name="Филиал",
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
