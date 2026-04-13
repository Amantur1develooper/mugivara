from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0017_add_adbanner"),
    ]

    operations = [
        migrations.AddField(
            model_name="adbanner",
            name="button_text",
            field=models.CharField(
                blank=True, default="",
                help_text="Например: Купить, Перейти, Подробнее. Оставь пустым — кнопки не будет.",
                max_length=60, verbose_name="Текст кнопки",
            ),
        ),
        migrations.AddField(
            model_name="adbanner",
            name="button_style",
            field=models.CharField(
                choices=[("primary", "Синяя"), ("success", "Зелёная"), ("danger", "Красная"), ("dark", "Тёмная"), ("white", "Белая")],
                default="primary", max_length=20, verbose_name="Цвет кнопки",
            ),
        ),
    ]
