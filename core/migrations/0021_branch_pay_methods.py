from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_banner"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="pay_cash_enabled",
            field=models.BooleanField(default=True, verbose_name="Наличные (касса)"),
        ),
        migrations.AddField(
            model_name="branch",
            name="pay_online_enabled",
            field=models.BooleanField(default=True, verbose_name="Онлайн / карта (касса)"),
        ),
    ]
