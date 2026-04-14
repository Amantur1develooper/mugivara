from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("karaoke", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="karaokemenuitem",
            name="cost_price",
            field=models.DecimalField(
                decimal_places=0,
                default=0,
                max_digits=10,
                verbose_name="Себестоимость (сом)",
            ),
        ),
    ]
