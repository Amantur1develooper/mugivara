from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0005_hotelbooking_rooms_count'),
    ]

    operations = [
        migrations.CreateModel(
            name='HotelService',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name_ru', models.CharField(max_length=200, verbose_name='Название')),
                ('description_ru', models.TextField(blank=True, default='', verbose_name='Описание')),
                ('price', models.DecimalField(decimal_places=0, default=0, max_digits=10, verbose_name='Цена (сом)')),
                ('photo1', models.ImageField(blank=True, null=True, upload_to='hotels/services/', verbose_name='Фото 1')),
                ('photo2', models.ImageField(blank=True, null=True, upload_to='hotels/services/', verbose_name='Фото 2')),
                ('photo3', models.ImageField(blank=True, null=True, upload_to='hotels/services/', verbose_name='Фото 3')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активна')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='services', to='hotels.hotelbranch')),
            ],
            options={'verbose_name': 'Услуга отеля', 'verbose_name_plural': 'Услуги отеля', 'ordering': ['sort_order', 'id']},
        ),
        migrations.CreateModel(
            name='HotelServiceSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('label', models.CharField(help_text='Пример: 10:00 – 12:00', max_length=100, verbose_name='Сеанс')),
                ('is_active', models.BooleanField(default=True, verbose_name='Активен')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='Порядок')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='hotels.hotelservice')),
            ],
            options={'ordering': ['sort_order', 'id']},
        ),
        migrations.CreateModel(
            name='HotelServiceBooking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('booking_date', models.CharField(blank=True, max_length=20, verbose_name='Дата')),
                ('customer_name', models.CharField(max_length=200, verbose_name='Имя')),
                ('customer_phone', models.CharField(max_length=50, verbose_name='Телефон')),
                ('comment', models.TextField(blank=True, default='', verbose_name='Комментарий')),
                ('status', models.CharField(choices=[('new', 'Новая'), ('confirmed', 'Подтверждена'), ('cancelled', 'Отменена')], default='new', max_length=20, verbose_name='Статус')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookings', to='hotels.hotelservice')),
                ('session', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings', to='hotels.hotelservicesession')),
            ],
            options={'verbose_name': 'Бронь услуги', 'verbose_name_plural': 'Брони услуг', 'ordering': ['-created_at']},
        ),
    ]
