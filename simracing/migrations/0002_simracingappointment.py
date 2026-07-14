import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("simracing", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SimRacingAppointment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("machine_type", models.CharField(
                    choices=[
                        ("kart_standard", "Стандартный картинг"),
                        ("kart_euro", "Евроспор картинг"),
                        ("simulator", "Автосимулятор"),
                    ],
                    max_length=20,
                    verbose_name="Тип машины",
                )),
                ("quantity",     models.PositiveSmallIntegerField(default=1, verbose_name="Количество заездов")),
                ("appt_date",    models.DateField(verbose_name="Дата")),
                ("appt_time",    models.TimeField(verbose_name="Время")),
                ("customer_name",  models.CharField(blank=True, default="", max_length=200, verbose_name="Имя клиента")),
                ("customer_phone", models.CharField(blank=True, default="", max_length=80,  verbose_name="Телефон")),
                ("total_price",    models.DecimalField(decimal_places=0, default=0, max_digits=10, verbose_name="Итого (сом)")),
                ("duration_minutes", models.PositiveIntegerField(default=0, verbose_name="Длительность (мин)")),
                ("status", models.CharField(
                    choices=[("new", "Новая"), ("confirmed", "Подтверждена"), ("canceled", "Отменена")],
                    default="new",
                    max_length=20,
                    verbose_name="Статус",
                )),
                ("notes",      models.TextField(blank=True, default="", verbose_name="Заметки")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("venue", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="appointments",
                    to="simracing.simracingvenue",
                )),
                ("session_type", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="simracing.sessiontype",
                    verbose_name="Тип сессии",
                )),
            ],
            options={
                "verbose_name": "Предварительная запись",
                "verbose_name_plural": "Предварительные записи",
                "ordering": ["-appt_date", "-appt_time"],
            },
        ),
    ]
