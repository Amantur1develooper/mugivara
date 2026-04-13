from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0018_adbanner_button"),
    ]

    operations = [
        migrations.DeleteModel(
            name="AdBanner",
        ),
        migrations.CreateModel(
            name="Banner",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="Название")),
                ("image_wide", models.ImageField(blank=True, null=True, upload_to="banners/wide/", verbose_name="ПК — широкий (2560×192)")),
                ("image_tablet", models.ImageField(blank=True, null=True, upload_to="banners/tablet/", verbose_name="Планшет (840×345)")),
                ("image_mobile", models.ImageField(blank=True, null=True, upload_to="banners/mobile/", verbose_name="Телефон (850×192)")),
                ("link_url", models.URLField(blank=True, default="", verbose_name="Ссылка")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                ("click_count", models.PositiveIntegerField(default=0, editable=False, verbose_name="Кликов")),
            ],
            options={
                "verbose_name": "Баннер",
                "verbose_name_plural": "Баннеры",
                "ordering": ["sort_order"],
            },
        ),
    ]
