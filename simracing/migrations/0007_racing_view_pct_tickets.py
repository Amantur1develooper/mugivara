from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("simracing", "0006_membership_racing_view"),
    ]

    operations = [
        migrations.AlterField(
            model_name="simracingmembership",
            name="racing_account",
            field=models.BooleanField(
                default=False,
                help_text="Ограниченный показ: в истории и отчёте видна только часть билетов "
                          "(самые дешёвые), но их цена показывается полностью — без урезания.",
                verbose_name="Гоночный аккаунт"),
        ),
        migrations.AlterField(
            model_name="simracingmembership",
            name="racing_view_pct",
            field=models.PositiveSmallIntegerField(
                default=40,
                help_text="Только для гоночного аккаунта. 40 = показывать 4 из 10 самых "
                          "дешёвых завершённых сессий, остальные скрыты целиком.",
                verbose_name="Показывать % билетов"),
        ),
    ]
