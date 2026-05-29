from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0024_working_hours'),
    ]

    operations = [
        migrations.AddField(
            model_name='branch',
            name='pos_delivery_fee_enabled',
            field=models.BooleanField(
                default=True,
                verbose_name='Добавлять стоимость доставки в кассе',
                help_text='Автоматически добавлять delivery_fee к заказу при оформлении доставки через кассу',
            ),
        ),
    ]
