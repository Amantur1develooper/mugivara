from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("karaoke", "0002_karaokemenuitem_cost_price"),
    ]

    operations = [
        migrations.CreateModel(
            name="KaraokeOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order_date", models.DateField(verbose_name="Дата заказа")),
                ("comment", models.CharField(blank=True, default="", max_length=300, verbose_name="Примечание")),
                ("total_amount", models.DecimalField(decimal_places=0, default=0, max_digits=10, verbose_name="Итого")),
                ("venue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="food_orders", to="karaoke.karaokevenue")),
                ("booking", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="food_orders", to="karaoke.karaokebooking")),
                ("room", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="food_orders", to="karaoke.karaokeroom")),
            ],
            options={"verbose_name": "Заказ еды", "verbose_name_plural": "Заказы еды", "ordering": ["-order_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="KaraokeOrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("qty", models.PositiveSmallIntegerField(default=1, verbose_name="Кол-во")),
                ("price_snapshot", models.DecimalField(decimal_places=0, default=0, max_digits=10, verbose_name="Цена на момент заказа")),
                ("line_total", models.DecimalField(decimal_places=0, default=0, max_digits=10, verbose_name="Сумма")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="karaoke.karaokeorder")),
                ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="order_items", to="karaoke.karaokemenuitem")),
            ],
            options={"verbose_name": "Позиция заказа", "verbose_name_plural": "Позиции заказа"},
        ),
    ]
