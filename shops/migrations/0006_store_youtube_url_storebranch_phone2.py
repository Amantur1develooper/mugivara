from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shops", "0005_storemembership"),
    ]

    operations = [
        migrations.AddField(
            model_name="store",
            name="youtube_url",
            field=models.URLField(blank=True, default="", verbose_name="YouTube канал"),
        ),
        migrations.AddField(
            model_name="storebranch",
            name="phone2",
            field=models.CharField(blank=True, default="", max_length=32, verbose_name="WhatsApp 2"),
        ),
    ]
