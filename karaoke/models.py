from django.conf import settings
from django.db import models
from core.models import TimeStampedModel


BOOKING_STATUS = [
    ("pending",   "Ожидает"),
    ("confirmed", "Подтверждено"),
    ("cancelled", "Отменено"),
    ("completed", "Завершено"),
]

ORDER_STATUS = [
    ("new",      "Новый"),
    ("sent",     "Отправлен в WhatsApp"),
    ("done",     "Выполнен"),
]


# ── ЗАВЕДЕНИЕ ──────────────────────────────────────────────────────────────────

class KaraokeVenue(TimeStampedModel):
    name          = models.CharField("Название", max_length=200)
    slug          = models.SlugField(max_length=220, unique=True)
    tagline       = models.CharField("Слоган", max_length=300, blank=True, default="")
    description   = models.TextField("Описание", blank=True, default="")
    logo          = models.ImageField("Логотип", upload_to="karaoke/logos/", blank=True, null=True)
    cover         = models.ImageField("Обложка", upload_to="karaoke/covers/", blank=True, null=True)
    address       = models.CharField("Адрес", max_length=300, blank=True, default="")
    phone         = models.CharField("Телефон", max_length=50, blank=True, default="")
    whatsapp      = models.CharField("WhatsApp (с кодом страны)", max_length=30, blank=True, default="",
                                     help_text="996700123456 — без + и пробелов")
    working_hours = models.CharField("Часы работы", max_length=200, blank=True, default="")
    map_url       = models.URLField("Ссылка на карту", blank=True, default="")
    tg_chat_id    = models.CharField("TG Chat ID", max_length=50, blank=True, default="")
    tg_thread_id  = models.PositiveIntegerField("TG Thread ID", null=True, blank=True)
    is_active     = models.BooleanField("Активно", default=True)
    sort_order    = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Каraоке-заведение"
        verbose_name_plural = "Каraоке-заведения"
        ordering            = ["sort_order", "name"]

    def __str__(self):
        return self.name


# ── КАТЕГОРИЯ КАБИНОК ──────────────────────────────────────────────────────────

class RoomCategory(TimeStampedModel):
    venue      = models.ForeignKey(KaraokeVenue, on_delete=models.CASCADE, related_name="room_categories")
    name       = models.CharField("Название категории", max_length=100)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Категория кабинок"
        verbose_name_plural = "Категории кабинок"
        ordering            = ["sort_order", "id"]

    def __str__(self):
        return f"{self.venue} / {self.name}"


# ── КАБИНКА ────────────────────────────────────────────────────────────────────

class KaraokeRoom(TimeStampedModel):
    venue          = models.ForeignKey(KaraokeVenue, on_delete=models.CASCADE, related_name="rooms")
    category       = models.ForeignKey(RoomCategory, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name="rooms")
    name           = models.CharField("Название кабинки", max_length=150)
    description    = models.TextField("Описание", blank=True, default="")
    capacity       = models.PositiveSmallIntegerField("Вместимость (чел.)", default=6)
    price_per_hour = models.DecimalField("Цена за час (сом)", max_digits=10, decimal_places=0, default=0)
    is_active      = models.BooleanField("Активна", default=True)
    sort_order     = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Кабинка"
        verbose_name_plural = "Кабинки"
        ordering            = ["sort_order", "id"]

    def __str__(self):
        return f"{self.venue} / {self.name}"

    @property
    def main_photo(self):
        return self.photos.first()


class KaraokeRoomPhoto(TimeStampedModel):
    room       = models.ForeignKey(KaraokeRoom, on_delete=models.CASCADE, related_name="photos")
    photo      = models.ImageField("Фото", upload_to="karaoke/rooms/")
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["sort_order", "id"]


# ── БРОНИРОВАНИЕ ───────────────────────────────────────────────────────────────

class KaraokeBooking(TimeStampedModel):
    venue          = models.ForeignKey(KaraokeVenue, on_delete=models.CASCADE, related_name="bookings")
    room           = models.ForeignKey(KaraokeRoom, on_delete=models.CASCADE, related_name="bookings")
    customer_name  = models.CharField("Имя клиента", max_length=200)
    customer_phone = models.CharField("Телефон", max_length=50)
    booking_date   = models.DateField("Дата")
    start_time     = models.TimeField("Начало")
    end_time       = models.TimeField("Конец")
    guests         = models.PositiveSmallIntegerField("Кол-во гостей", default=1)
    notes          = models.TextField("Примечание", blank=True, default="")
    status         = models.CharField("Статус", max_length=20, choices=BOOKING_STATUS, default="pending")

    class Meta:
        verbose_name        = "Бронирование кабинки"
        verbose_name_plural = "Бронирования кабинок"
        ordering            = ["-booking_date", "-start_time"]

    def __str__(self):
        return f"{self.room} {self.booking_date} {self.start_time}–{self.end_time}"

    @property
    def duration_hours(self):
        from datetime import datetime, date
        dt_start = datetime.combine(date.today(), self.start_time)
        dt_end   = datetime.combine(date.today(), self.end_time)
        delta = dt_end - dt_start
        return round(delta.seconds / 3600, 1)


# ── МЕНЮ ───────────────────────────────────────────────────────────────────────

class KaraokeMenuCategory(TimeStampedModel):
    venue      = models.ForeignKey(KaraokeVenue, on_delete=models.CASCADE, related_name="menu_categories")
    name       = models.CharField("Название", max_length=150)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Категория меню"
        verbose_name_plural = "Категории меню"
        ordering            = ["sort_order", "id"]

    def __str__(self):
        return f"{self.venue} / {self.name}"


class KaraokeMenuItem(TimeStampedModel):
    venue       = models.ForeignKey(KaraokeVenue, on_delete=models.CASCADE, related_name="menu_items")
    category    = models.ForeignKey(KaraokeMenuCategory, on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="items")
    name        = models.CharField("Название", max_length=200)
    description = models.TextField("Описание", blank=True, default="")
    photo       = models.ImageField("Фото", upload_to="karaoke/menu/", blank=True, null=True)
    price       = models.DecimalField("Цена (сом)", max_digits=10, decimal_places=0, default=0)
    is_active   = models.BooleanField("Активно", default=True)
    sort_order  = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name        = "Позиция меню"
        verbose_name_plural = "Позиции меню"
        ordering            = ["sort_order", "id"]

    def __str__(self):
        return f"{self.venue} / {self.name}"


# ── ДОСТУП ВЛАДЕЛЬЦА ───────────────────────────────────────────────────────────

class KaraokeMembership(TimeStampedModel):
    user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="karaoke_memberships")
    venue = models.ForeignKey(KaraokeVenue, on_delete=models.CASCADE, related_name="memberships")

    class Meta:
        verbose_name        = "Доступ к заведению"
        verbose_name_plural = "Доступы к заведениям"
        unique_together     = ("user", "venue")

    def __str__(self):
        return f"{self.user} → {self.venue}"
