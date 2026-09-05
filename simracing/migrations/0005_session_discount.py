from django.db import migrations, models


def backfill_base_price(apps, schema_editor):
    Session = apps.get_model("simracing", "Session")
    Session.objects.update(base_price=models.F("price"))


class Migration(migrations.Migration):

    dependencies = [
        ("simracing", "0004_simracingvenue_place_category_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="base_price",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=8,
                                      verbose_name="Цена по прайсу (сом)"),
        ),
        migrations.AddField(
            model_name="session",
            name="discount_type",
            field=models.CharField(choices=[("none", "Без скидки"), ("percent", "Процент"),
                                            ("amount", "Сумма")],
                                   default="none", max_length=10, verbose_name="Тип скидки"),
        ),
        migrations.AddField(
            model_name="session",
            name="discount_value",
            field=models.DecimalField(decimal_places=0, default=0,
                                      help_text="Проценты (0–100) или сумма в сомах",
                                      max_digits=8, verbose_name="Размер скидки"),
        ),
        migrations.AddField(
            model_name="session",
            name="discount_reason",
            field=models.CharField(blank=True, default="", max_length=200,
                                   verbose_name="Причина скидки"),
        ),
        migrations.AlterField(
            model_name="session",
            name="price",
            field=models.DecimalField(decimal_places=0, default=0, max_digits=8,
                                      verbose_name="Цена к оплате (сом)"),
        ),
        migrations.RunPython(backfill_base_price, migrations.RunPython.noop),
    ]
