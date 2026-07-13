from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservations", "0009_alter_booking_options_alter_floor_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="duration_minutes",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name="Длительность сессии (мин)",
            ),
        ),
    ]
