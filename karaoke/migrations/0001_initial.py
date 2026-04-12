from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="KaraokeVenue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200, verbose_name="Название")),
                ("slug", models.SlugField(max_length=220, unique=True)),
                ("tagline", models.CharField(blank=True, default="", max_length=300, verbose_name="Слоган")),
                ("description", models.TextField(blank=True, default="", verbose_name="Описание")),
                ("logo", models.ImageField(blank=True, null=True, upload_to="karaoke/logos/", verbose_name="Логотип")),
                ("cover", models.ImageField(blank=True, null=True, upload_to="karaoke/covers/", verbose_name="Обложка")),
                ("address", models.CharField(blank=True, default="", max_length=300, verbose_name="Адрес")),
                ("phone", models.CharField(blank=True, default="", max_length=50, verbose_name="Телефон")),
                ("whatsapp", models.CharField(blank=True, default="", help_text="996700123456 — без + и пробелов", max_length=30, verbose_name="WhatsApp")),
                ("working_hours", models.CharField(blank=True, default="", max_length=200, verbose_name="Часы работы")),
                ("map_url", models.URLField(blank=True, default="", verbose_name="Ссылка на карту")),
                ("tg_chat_id", models.CharField(blank=True, default="", max_length=50, verbose_name="TG Chat ID")),
                ("tg_thread_id", models.PositiveIntegerField(blank=True, null=True, verbose_name="TG Thread ID")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активно")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
            ],
            options={"verbose_name": "Каraоке-заведение", "verbose_name_plural": "Каraоке-заведения", "ordering": ["sort_order", "name"]},
        ),
        migrations.CreateModel(
            name="RoomCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=100, verbose_name="Название категории")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                ("venue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="room_categories", to="karaoke.karaokevenue")),
            ],
            options={"verbose_name": "Категория кабинок", "verbose_name_plural": "Категории кабинок", "ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="KaraokeRoom",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=150, verbose_name="Название кабинки")),
                ("description", models.TextField(blank=True, default="", verbose_name="Описание")),
                ("capacity", models.PositiveSmallIntegerField(default=6, verbose_name="Вместимость (чел.)")),
                ("price_per_hour", models.DecimalField(decimal_places=0, default=0, max_digits=10, verbose_name="Цена за час (сом)")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активна")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                ("venue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rooms", to="karaoke.karaokevenue")),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="rooms", to="karaoke.roomcategory")),
            ],
            options={"verbose_name": "Кабинка", "verbose_name_plural": "Кабинки", "ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="KaraokeRoomPhoto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("photo", models.ImageField(upload_to="karaoke/rooms/", verbose_name="Фото")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="photos", to="karaoke.karaokeroom")),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="KaraokeBooking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer_name", models.CharField(max_length=200, verbose_name="Имя клиента")),
                ("customer_phone", models.CharField(max_length=50, verbose_name="Телефон")),
                ("booking_date", models.DateField(verbose_name="Дата")),
                ("start_time", models.TimeField(verbose_name="Начало")),
                ("end_time", models.TimeField(verbose_name="Конец")),
                ("guests", models.PositiveSmallIntegerField(default=1, verbose_name="Кол-во гостей")),
                ("notes", models.TextField(blank=True, default="", verbose_name="Примечание")),
                ("status", models.CharField(choices=[("pending", "Ожидает"), ("confirmed", "Подтверждено"), ("cancelled", "Отменено"), ("completed", "Завершено")], default="pending", max_length=20, verbose_name="Статус")),
                ("venue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookings", to="karaoke.karaokevenue")),
                ("room", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="bookings", to="karaoke.karaokeroom")),
            ],
            options={"verbose_name": "Бронирование кабинки", "verbose_name_plural": "Бронирования кабинок", "ordering": ["-booking_date", "-start_time"]},
        ),
        migrations.CreateModel(
            name="KaraokeMenuCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=150, verbose_name="Название")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                ("venue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menu_categories", to="karaoke.karaokevenue")),
            ],
            options={"verbose_name": "Категория меню", "verbose_name_plural": "Категории меню", "ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="KaraokeMenuItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=200, verbose_name="Название")),
                ("description", models.TextField(blank=True, default="", verbose_name="Описание")),
                ("photo", models.ImageField(blank=True, null=True, upload_to="karaoke/menu/", verbose_name="Фото")),
                ("price", models.DecimalField(decimal_places=0, default=0, max_digits=10, verbose_name="Цена (сом)")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активно")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Порядок")),
                ("venue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menu_items", to="karaoke.karaokevenue")),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="items", to="karaoke.karaokemenucategory")),
            ],
            options={"verbose_name": "Позиция меню", "verbose_name_plural": "Позиции меню", "ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="KaraokeMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="karaoke_memberships", to=settings.AUTH_USER_MODEL)),
                ("venue", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="karaoke.karaokevenue")),
            ],
            options={"verbose_name": "Доступ к заведению", "verbose_name_plural": "Доступы к заведениям", "unique_together": {("user", "venue")}},
        ),
    ]
