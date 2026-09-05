from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("simracing", "0005_session_discount"),
    ]

    operations = [
        migrations.AddField(
            model_name="simracingmembership",
            name="racing_account",
            field=models.BooleanField(
                default=False,
                help_text="Ограниченный показ: суммы в отчёте и истории отображаются частично",
                verbose_name="Гоночный аккаунт"),
        ),
        migrations.AddField(
            model_name="simracingmembership",
            name="racing_view_pct",
            field=models.PositiveSmallIntegerField(
                default=40,
                help_text="Только для гоночного аккаунта. 40 = показывать 40% от реальных сумм",
                verbose_name="Показывать % от сумм"),
        ),
    ]
