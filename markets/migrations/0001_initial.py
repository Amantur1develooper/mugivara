from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Market",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name_ru", models.CharField(max_length=200, verbose_name="Название")),
                ("slug", models.SlugField(max_length=220, unique=True)),
                ("description_ru", models.TextField(blank=True, default="", verbose_name="Описание")),
                ("address", models.CharField(blank=True, default="", max_length=300, verbose_name="Адрес")),
                ("working_hours", models.CharField(blank=True, default="", help_text="Пример: Пн–Вс: 08:00–20:00", max_length=200, verbose_name="Часы работы")),
                ("phone", models.CharField(blank=True, default="", max_length=50, verbose_name="Номер WhatsApp / телефон")),
                ("map_url", models.URLField(blank=True, default="", verbose_name="Ссылка на карту")),
                ("logo", models.ImageField(blank=True, null=True, upload_to="markets/logos/", verbose_name="Логотип / главное фото")),
                ("photo1", models.ImageField(blank=True, null=True, upload_to="markets/photos/", verbose_name="Фото 1")),
                ("photo2", models.ImageField(blank=True, null=True, upload_to="markets/photos/", verbose_name="Фото 2")),
                ("photo3", models.ImageField(blank=True, null=True, upload_to="markets/photos/", verbose_name="Фото 3")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
            ],
            options={
                "verbose_name": "Рынок",
                "verbose_name_plural": "Рынки",
                "ordering": ["sort_order", "name_ru"],
            },
        ),
    ]
