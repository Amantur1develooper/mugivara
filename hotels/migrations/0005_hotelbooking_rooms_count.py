from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0004_add_tg_fields_to_hotelbranch'),
    ]

    operations = [
        migrations.AddField(
            model_name='hotelbooking',
            name='rooms_count',
            field=models.PositiveSmallIntegerField(default=1, verbose_name='Кол-во номеров'),
        ),
    ]
