from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0016_add_performance_indexes"),
    ]

    operations = [
        migrations.CreateModel(
            name="AdBanner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(blank=True, default="", max_length=200, verbose_name="Заголовок / alt")),
                ("image_desktop", models.ImageField(blank=True, null=True, upload_to="ads/desktop/", verbose_name="Фото для ПК (широкий баннер, ~2560×192)")),
                ("image_tablet", models.ImageField(blank=True, null=True, upload_to="ads/tablet/", verbose_name="Фото для планшета (~840×345)")),
                ("image_mobile", models.ImageField(blank=True, null=True, upload_to="ads/mobile/", verbose_name="Фото для телефона (~850×192)")),
                ("button_text", models.CharField(blank=True, default="", help_text="Например: Купить, Перейти, Подробнее", max_length=60, verbose_name="Текст кнопки")),
                ("button_url", models.URLField(blank=True, default="", verbose_name="Ссылка кнопки")),
                ("button_style", models.CharField(choices=[("primary", "Синяя (основная)"), ("success", "Зелёная"), ("danger", "Красная"), ("dark", "Тёмная")], default="primary", max_length=20, verbose_name="Стиль кнопки")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
            ],
            options={
                "verbose_name": "Рекламный баннер",
                "verbose_name_plural": "Рекламные баннеры",
                "ordering": ["sort_order"],
            },
        ),
    ]
