from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Agency",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200, verbose_name="Название агентства")),
                ("slug", models.SlugField(max_length=220, unique=True)),
                ("tagline", models.CharField(blank=True, default="", max_length=300, verbose_name="Слоган")),
                ("description", models.TextField(blank=True, default="", verbose_name="Описание")),
                ("logo", models.ImageField(blank=True, null=True, upload_to="agency/logos/", verbose_name="Логотип")),
                ("cover", models.ImageField(blank=True, null=True, upload_to="agency/covers/", verbose_name="Обложка")),
                ("website", models.URLField(blank=True, default="", verbose_name="Сайт")),
                ("phone", models.CharField(blank=True, default="", max_length=50, verbose_name="Телефон / WhatsApp")),
                ("email", models.EmailField(blank=True, default="", verbose_name="Email")),
                ("address", models.CharField(blank=True, default="", max_length=300, verbose_name="Адрес")),
                ("tg_chat_id", models.CharField(blank=True, default="", help_text="ID чата/группы Telegram для заявок. Пример: -1001234567890", max_length=50, verbose_name="TG Chat ID")),
                ("tg_thread_id", models.PositiveIntegerField(blank=True, null=True, verbose_name="TG Thread ID (топик)")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активно")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
            ],
            options={
                "verbose_name": "IT Агентство",
                "verbose_name_plural": "IT Агентства",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="AgencyService",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("service_type", models.CharField(choices=[("dev", "Разработка"), ("design", "Дизайн"), ("seo", "SEO / Маркетинг"), ("mobile", "Мобильные приложения"), ("ai", "AI / Автоматизация"), ("devops", "DevOps / Облако"), ("support", "Поддержка"), ("other", "Другое")], default="dev", max_length=20, verbose_name="Тип услуги")),
                ("name", models.CharField(max_length=300, verbose_name="Название услуги")),
                ("description", models.TextField(blank=True, default="", verbose_name="Описание")),
                ("photo", models.ImageField(blank=True, null=True, upload_to="agency/services/", verbose_name="Фото / Превью")),
                ("tech_stack", models.CharField(blank=True, default="", help_text="Например: React, Django, PostgreSQL", max_length=500, verbose_name="Стек технологий")),
                ("price", models.DecimalField(decimal_places=0, default=0, max_digits=12, verbose_name="Цена (сом)")),
                ("price_note", models.CharField(blank=True, default="", help_text="Например: от, за проект, за час", max_length=100, verbose_name="Примечание к цене")),
                ("delivery_days", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Срок (дней)")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                ("agency", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="services", to="agency.agency", verbose_name="Агентство")),
            ],
            options={
                "verbose_name": "Услуга агентства",
                "verbose_name_plural": "Услуги агентств",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.CreateModel(
            name="AgencyMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("agency", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="agency.agency", verbose_name="Агентство")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="agency_memberships", to=settings.AUTH_USER_MODEL, verbose_name="Пользователь")),
            ],
            options={
                "verbose_name": "Доступ к агентству",
                "verbose_name_plural": "Доступы к агентствам",
                "unique_together": {("user", "agency")},
            },
        ),
    ]
