from django.conf import settings
from django.db import models
from core.models import TimeStampedModel


SERVICE_TYPE_CHOICES = [
    ("dev",     "Разработка"),
    ("design",  "Дизайн"),
    ("seo",     "SEO / Маркетинг"),
    ("mobile",  "Мобильные приложения"),
    ("ai",      "AI / Автоматизация"),
    ("devops",  "DevOps / Облако"),
    ("support", "Поддержка"),
    ("other",   "Другое"),
]


class Agency(TimeStampedModel):
    name          = models.CharField("Название агентства", max_length=200)
    slug          = models.SlugField(max_length=220, unique=True)
    tagline       = models.CharField("Слоган", max_length=300, blank=True, default="")
    description   = models.TextField("Описание", blank=True, default="")
    logo          = models.ImageField("Логотип", upload_to="agency/logos/", blank=True, null=True)
    cover         = models.ImageField("Обложка", upload_to="agency/covers/", blank=True, null=True)
    website       = models.URLField("Сайт", blank=True, default="")
    phone         = models.CharField("Телефон / WhatsApp", max_length=50, blank=True, default="")
    email         = models.EmailField("Email", blank=True, default="")
    address       = models.CharField("Адрес", max_length=300, blank=True, default="")
    tg_chat_id    = models.CharField("TG Chat ID", max_length=50, blank=True, default="",
                                     help_text="ID чата/группы Telegram для заявок. Пример: -1001234567890")
    tg_thread_id  = models.PositiveIntegerField("TG Thread ID (топик)", null=True, blank=True)
    is_active     = models.BooleanField("Активно", default=True)
    sort_order    = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "IT Агентство"
        verbose_name_plural = "IT Агентства"
        ordering            = ["sort_order", "name"]

    def __str__(self):
        return self.name


class AgencyService(TimeStampedModel):
    agency       = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name="services",
                                     verbose_name="Агентство")
    service_type = models.CharField("Тип услуги", max_length=20, choices=SERVICE_TYPE_CHOICES, default="dev")
    name         = models.CharField("Название услуги", max_length=300)
    description  = models.TextField("Описание", blank=True, default="")
    photo        = models.ImageField("Фото / Превью", upload_to="agency/services/", blank=True, null=True)
    tech_stack   = models.CharField("Стек технологий", max_length=500, blank=True, default="",
                                    help_text="Например: React, Django, PostgreSQL")
    price        = models.DecimalField("Цена (сом)", max_digits=12, decimal_places=0, default=0)
    price_note   = models.CharField("Примечание к цене", max_length=100, blank=True, default="",
                                    help_text="Например: от, за проект, за час")
    delivery_days = models.PositiveSmallIntegerField("Срок (дней)", null=True, blank=True)
    is_active    = models.BooleanField("Активна", default=True)
    sort_order   = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Услуга агентства"
        verbose_name_plural = "Услуги агентств"
        ordering            = ["sort_order", "id"]

    def __str__(self):
        return f"{self.agency}: {self.name}"


class AgencyMembership(TimeStampedModel):
    """Доступ пользователя к личному кабинету агентства."""
    user   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="agency_memberships")
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE, related_name="memberships")

    class Meta:
        verbose_name        = "Доступ к агентству"
        verbose_name_plural = "Доступы к агентствам"
        unique_together     = ("user", "agency")

    def __str__(self):
        return f"{self.user} → {self.agency}"
