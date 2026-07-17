import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("simracing", "0002_simracingappointment"),
    ]

    operations = [
        migrations.CreateModel(
            name="SimRacingPrintConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("enabled", models.BooleanField(default=False, verbose_name="Печать включена")),
                ("token", models.CharField(editable=False, max_length=64, unique=True)),
                ("windows_printer", models.CharField(blank=True, default="", max_length=200,
                                                      verbose_name="Имя принтера в Windows")),
                ("last_heartbeat", models.DateTimeField(blank=True, null=True,
                                                         verbose_name="Последний heartbeat")),
                ("print_mode", models.CharField(
                    choices=[("image", "Картинка (рекомендуется)"), ("text", "Текст (ESC/POS)")],
                    default="image", max_length=10, verbose_name="Режим печати")),
                ("codepage", models.CharField(default="cp866", max_length=20,
                                               verbose_name="Кодовая страница")),
                ("venue", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="print_config",
                    to="simracing.simracingvenue",
                )),
            ],
            options={"verbose_name": "Настройки печати (симрейсинг)",
                     "verbose_name_plural": "Настройки печати (симрейсинг)"},
        ),
        migrations.CreateModel(
            name="SimRacingPrintJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("content", models.TextField(verbose_name="Содержимое (plain text)")),
                ("status", models.CharField(
                    choices=[("new", "Новый"), ("processing", "Печатается"),
                             ("printed", "Напечатан"), ("error", "Ошибка")],
                    default="new", max_length=20)),
                ("retries", models.PositiveSmallIntegerField(default=0)),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("printed_at", models.DateTimeField(blank=True, null=True)),
                ("venue", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="print_jobs",
                    to="simracing.simracingvenue",
                )),
                ("session", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="print_jobs",
                    to="simracing.session",
                )),
                ("appt", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="print_jobs",
                    to="simracing.simracingappointment",
                )),
            ],
            options={"ordering": ["created_at"],
                     "verbose_name": "Задание печати (симрейсинг)",
                     "verbose_name_plural": "Задания печати (симрейсинг)"},
        ),
    ]
