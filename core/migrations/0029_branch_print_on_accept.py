from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0028_place_categories_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="branch",
            name="print_on_accept",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Если включено — кухонный чек печатается не сразу при заказе через QR, "
                    "а только после того как кассир/официант нажмёт «Принять заказ» в панели столов."
                ),
                verbose_name="Печать только после подтверждения кассиром",
            ),
        ),
    ]
