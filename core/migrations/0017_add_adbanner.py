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
                ("title", models.CharField(blank=True, default="", max_length=200, verbose_name="Название (для себя)")),
                ("image_desktop", models.ImageField(blank=True, null=True, upload_to="ads/desktop/", verbose_name="Фото для ПК (широкий баннер, ~2560×192)")),
                ("image_tablet", models.ImageField(blank=True, null=True, upload_to="ads/tablet/", verbose_name="Фото для планшета (~840×345)")),
                ("image_mobile", models.ImageField(blank=True, null=True, upload_to="ads/mobile/", verbose_name="Фото для телефона (~850×192)")),
                ("link_url", models.URLField(blank=True, default="", verbose_name="Ссылка (куда ведёт баннер)")),
                ("click_count", models.PositiveIntegerField(default=0, editable=False, verbose_name="Переходов всего")),
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
