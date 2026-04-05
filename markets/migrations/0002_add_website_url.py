from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("markets", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="market",
            name="website_url",
            field=models.URLField(blank=True, default="", verbose_name="Сайт рынка"),
        ),
    ]
