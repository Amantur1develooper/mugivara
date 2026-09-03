from django.db import models
from django.conf import settings
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image
import os


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Hotel(TimeStampedModel):
    place_category = models.ForeignKey(
        "core.PlaceCategory", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="hotels",
        verbose_name="Категория платформы",
    )
    name_ru = models.CharField("Название (RU)", max_length=200)
    name_ky = models.CharField("Название (KY)", max_length=200, blank=True, default="")
    name_en = models.CharField("Название (EN)", max_length=200, blank=True, default="")
    slug = models.SlugField(max_length=220, unique=True)
    logo = models.ImageField("Логотип", upload_to="hotels/logos/", blank=True, null=True)
    is_active = models.BooleanField("Активен", default=True)
    rating = models.DecimalField("Рейтинг", max_digits=3, decimal_places=1, default=0.0)
    about_ru = models.TextField("О нас", blank=True, default="")
    external_url = models.URLField("Внешний сайт", blank=True, default="")

    class Meta:
        verbose_name = "Отель"
        verbose_name_plural = "Отели"
        ordering = ["-rating", "name_ru"]

    def __str__(self):
        return self.name_ru

    def save(self, *args, **kwargs):
        _compress_image_fields(self, {"logo": ((512, 512), 85)})
        super().save(*args, **kwargs)


class HotelBranch(TimeStampedModel):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="branches")
    name_ru = models.CharField("Название (RU)", max_length=200)
    name_ky = models.CharField("Название (KY)", max_length=200, blank=True, default="")
    name_en = models.CharField("Название (EN)", max_length=200, blank=True, default="")
    address = models.CharField("Адрес", max_length=300, blank=True)
    phone = models.CharField("Телефон", max_length=50, blank=True)
    map_url = models.URLField("Ссылка на карту", blank=True, default="")
    is_active = models.BooleanField("Активен", default=True)
    cover_photo = models.ImageField("Обложка", upload_to="hotels/covers/", blank=True, null=True)
    external_url = models.URLField("Внешний сайт / приложение", blank=True, default="")
    tg_chat_id  = models.CharField("Telegram chat ID", max_length=64, blank=True, default="",
                                    help_text="ID группы/канала для уведомлений о бронях")
    tg_thread_id = models.PositiveIntegerField("Telegram thread ID", null=True, blank=True,
                                                help_text="ID темы (необязательно)")

    class Meta:
        verbose_name = "Филиал отеля"
        verbose_name_plural = "Филиалы отелей"

    def __str__(self):
        return f"{self.hotel.name_ru} — {self.name_ru}"

    def save(self, *args, **kwargs):
        _compress_image_fields(self, {"cover_photo": ((1600, 900), 82)})
        super().save(*args, **kwargs)


class RoomCategory(TimeStampedModel):
    branch = models.ForeignKey(HotelBranch, on_delete=models.CASCADE, related_name="room_categories")
    name_ru = models.CharField("Категория", max_length=100)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Категория номеров"
        verbose_name_plural = "Категории номеров"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name_ru} ({self.branch})"


def _compress_photo(field, max_size=(1200, 900), quality=85):
    if not field or not hasattr(field, "file"):
        return None
    try:
        field.file.seek(0)
        img = Image.open(field).convert("RGB")
        img.thumbnail(max_size, Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=6)
        buf.seek(0)
        name = os.path.splitext(field.name)[0] + ".webp"
        return name, ContentFile(buf.read())
    except Exception:
        return None


def _compress_image_fields(instance, specs):
    """Сжимает новые загрузки в WebP. specs: {"поле": (max_size, quality)}."""
    for fname, (max_size, quality) in specs.items():
        field = getattr(instance, fname, None)
        if field and not getattr(field, "_committed", True):
            result = _compress_photo(field, max_size=max_size, quality=quality)
            if result:
                name, content = result
                field.save(os.path.basename(name), content, save=False)


class Room(TimeStampedModel):
    branch = models.ForeignKey(HotelBranch, on_delete=models.CASCADE, related_name="rooms")
    category = models.ForeignKey(
        RoomCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="rooms",
        verbose_name="Категория",
    )
    name_ru = models.CharField("Название номера", max_length=200)
    description_ru = models.TextField("Описание", blank=True, default="")
    amenities_ru = models.TextField(
        "Что включено",
        blank=True, default="",
        help_text="Каждый пункт с новой строки: WiFi, Завтрак, TV ..."
    )
    price_per_night = models.DecimalField(
        "Базовая цена (1 гость) / ночь (сом)",
        max_digits=10, decimal_places=0, default=0,
    )
    price_per_extra_guest = models.DecimalField(
        "Доплата за каждого доп. гостя / ночь (сом)",
        max_digits=10, decimal_places=0, default=0,
        help_text="Пример: база 2000, доплата 1000 → 1 гость=2000, 2 гостя=3000, 3 гостя=4000",
    )
    max_guests = models.PositiveSmallIntegerField("Макс. гостей", default=2)
    is_available = models.BooleanField("Доступен", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    public_code = models.CharField("Код для QR", max_length=12, unique=True, blank=True, null=True,
                                   help_text="Ссылка/QR для гостя: заказ услуг в номер, вызов сотрудника")

    photo1 = models.ImageField("Фото 1 (главное)", upload_to="hotels/rooms/", blank=True, null=True)
    photo2 = models.ImageField("Фото 2", upload_to="hotels/rooms/", blank=True, null=True)
    photo3 = models.ImageField("Фото 3", upload_to="hotels/rooms/", blank=True, null=True)

    class Meta:
        verbose_name = "Номер"
        verbose_name_plural = "Номера"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name_ru} ({self.branch})"

    def save(self, *args, **kwargs):
        if not self.public_code:
            self.public_code = self._gen_code()
        _compress_image_fields(self, {
            "photo1": ((1600, 1200), 82),
            "photo2": ((1600, 1200), 82),
            "photo3": ((1600, 1200), 82),
        })
        super().save(*args, **kwargs)

    @staticmethod
    def _gen_code():
        from django.utils.crypto import get_random_string
        alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
        for _ in range(10):
            code = get_random_string(7, alphabet)
            if not Room.objects.filter(public_code=code).exists():
                return code
        return get_random_string(10, alphabet)

    @property
    def photos(self):
        return [p for p in (self.photo1, self.photo2, self.photo3) if p]

    @property
    def amenities_list(self):
        return [ln.strip() for ln in self.amenities_ru.splitlines() if ln.strip()]

    # ── занятость номера (шахматка ↔ публичная часть) ────────────────────────

    # статусы, при которых номер считается занятым для публичной брони
    _BLOCKING_STATUSES = ("new", "confirmed", "checkedin")

    def _blocking_bookings(self):
        """Активные брони/заселения номера (не отменённые, не завершённые), с датами."""
        return [
            b for b in self.bookings.all()
            if b.status in self._BLOCKING_STATUSES and b.checkin_date and b.checkout_date
        ]

    def occupied_on(self, day):
        """Бронь, занимающая номер на дату `day` (или None)."""
        for b in self._blocking_bookings():
            if b.checkin_date <= day < b.checkout_date:
                return b
        # физически заселён и ещё не выписан
        for b in self.bookings.all():
            if b.actual_checkin_at and not b.actual_checkout_at:
                return b
        return None

    def is_free_between(self, checkin, checkout):
        """Свободен ли номер на весь период [checkin, checkout)."""
        if not self.is_available:
            return False
        for b in self._blocking_bookings():
            if b.checkin_date < checkout and b.checkout_date > checkin:
                return False
        for b in self.bookings.all():
            if b.actual_checkin_at and not b.actual_checkout_at:
                return False
        return True

    @property
    def public_available(self):
        """Показывать ли номер как доступный для брони на витрине (на сегодня)."""
        from datetime import date
        return self.is_available and self.occupied_on(date.today()) is None

    @property
    def busy_until(self):
        """Дата, до которой номер занят текущей бронёй (для подписи на витрине)."""
        from datetime import date
        b = self.occupied_on(date.today())
        return b.checkout_date if b else None


class HotelService(TimeStampedModel):
    branch      = models.ForeignKey(HotelBranch, on_delete=models.CASCADE, related_name="services")
    name_ru     = models.CharField("Название", max_length=200)
    description_ru = models.TextField("Описание", blank=True, default="")
    price       = models.DecimalField("Цена (сом)", max_digits=10, decimal_places=0, default=0)
    photo1      = models.ImageField("Фото 1", upload_to="hotels/services/", blank=True, null=True)
    photo2      = models.ImageField("Фото 2", upload_to="hotels/services/", blank=True, null=True)
    photo3      = models.ImageField("Фото 3", upload_to="hotels/services/", blank=True, null=True)
    is_active     = models.BooleanField("Активна", default=True)
    show_in_room  = models.BooleanField("Показывать гостям в номере (QR)", default=True,
                                        help_text="Услуга доступна для заказа на странице номера по QR")
    sort_order    = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Услуга отеля"
        verbose_name_plural = "Услуги отеля"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name_ru} ({self.branch})"

    def save(self, *args, **kwargs):
        _compress_image_fields(self, {
            "photo1": ((1400, 1050), 82),
            "photo2": ((1400, 1050), 82),
            "photo3": ((1400, 1050), 82),
        })
        super().save(*args, **kwargs)

    @property
    def photos(self):
        return [p for p in (self.photo1, self.photo2, self.photo3) if p]


class HotelServiceSession(TimeStampedModel):
    service    = models.ForeignKey(HotelService, on_delete=models.CASCADE, related_name="sessions")
    label      = models.CharField("Сеанс", max_length=100, help_text="Пример: 10:00 – 12:00")
    is_active  = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.service.name_ru} — {self.label}"


class HotelServiceBooking(TimeStampedModel):
    class Status(models.TextChoices):
        NEW       = "new",       "Новая"
        CONFIRMED = "confirmed", "Подтверждена"
        CANCELLED = "cancelled", "Отменена"

    service       = models.ForeignKey(HotelService, on_delete=models.CASCADE, related_name="bookings")
    session       = models.ForeignKey(HotelServiceSession, on_delete=models.SET_NULL, null=True, blank=True, related_name="bookings")
    booking_date  = models.CharField("Дата", max_length=20, blank=True)
    customer_name = models.CharField("Имя", max_length=200)
    customer_phone= models.CharField("Телефон", max_length=50)
    comment       = models.TextField("Комментарий", blank=True, default="")
    status        = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW)

    class Meta:
        verbose_name = "Бронь услуги"
        verbose_name_plural = "Брони услуг"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.id} {self.customer_name} → {self.service.name_ru}"


class HotelMembership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER   = "owner",   "Владелец"
        MANAGER = "manager", "Менеджер"

    user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hotel_memberships")
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name="memberships")
    role  = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.MANAGER)

    class Meta:
        verbose_name = "Доступ к отелю"
        verbose_name_plural = "Доступы к отелям"
        unique_together = ("user", "hotel")

    def __str__(self):
        return f"{self.user} → {self.hotel} ({self.role})"


class HotelBooking(TimeStampedModel):
    class Status(models.TextChoices):
        NEW       = "new",       "Новая"
        CONFIRMED = "confirmed", "Подтверждена"
        CHECKEDIN = "checkedin", "Заселён"
        CANCELLED = "cancelled", "Отменена"
        COMPLETED = "completed", "Завершена"

    class BookType(models.TextChoices):
        BOOKING = "booking", "Бронирование"
        CHECKIN = "checkin", "Заселение"

    branch          = models.ForeignKey(HotelBranch, on_delete=models.CASCADE, related_name="bookings")
    room            = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, related_name="bookings")
    book_type       = models.CharField("Тип", max_length=10, choices=BookType.choices, default=BookType.BOOKING)
    customer_name   = models.CharField("Имя", max_length=200)
    customer_phone  = models.CharField("Телефон", max_length=50)
    checkin_date    = models.DateField("Дата заезда", null=True, blank=True)
    checkout_date   = models.DateField("Дата выезда", null=True, blank=True)
    nights          = models.PositiveSmallIntegerField("Ночей", default=1)
    guests          = models.PositiveSmallIntegerField("Гостей", default=1)
    rooms_count     = models.PositiveSmallIntegerField("Кол-во номеров", default=1)
    price_per_night = models.DecimalField("Цена/ночь", max_digits=10, decimal_places=0, default=0)
    total           = models.DecimalField("Итого", max_digits=12, decimal_places=0, default=0)
    comment         = models.TextField("Комментарий", blank=True)
    status          = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW)

    actual_checkin_at  = models.DateTimeField("Фактически заселён", null=True, blank=True)
    actual_checkout_at = models.DateTimeField("Фактически выселен", null=True, blank=True)

    class Meta:
        verbose_name = "Бронирование"
        verbose_name_plural = "Бронирования"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.id} {self.customer_name} → {self.room}"

    @property
    def is_in_house(self):
        return bool(self.actual_checkin_at and not self.actual_checkout_at)

    def save(self, *args, **kwargs):
        if self.checkin_date and not self.checkout_date:
            from datetime import timedelta
            self.checkout_date = self.checkin_date + timedelta(days=self.nights or 1)
        super().save(*args, **kwargs)


class RoomRequest(TimeStampedModel):
    """Заявка гостя из номера: услуга(и) в номер или вызов сотрудника. Уходит в TG-группу отеля."""
    class Kind(models.TextChoices):
        SERVICE = "service", "Услуги в номер"
        LOBBY   = "lobby",   "Вызов сотрудника"

    class Status(models.TextChoices):
        NEW  = "new",  "Новая"
        DONE = "done", "Выполнена"

    branch     = models.ForeignKey(HotelBranch, on_delete=models.CASCADE, related_name="room_requests")
    room       = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="requests")
    kind       = models.CharField("Тип", max_length=10, choices=Kind.choices, default=Kind.SERVICE)
    services   = models.ManyToManyField(HotelService, blank=True, related_name="room_requests",
                                        verbose_name="Услуги")
    guest_name = models.CharField("Имя гостя", max_length=120, blank=True)
    comment    = models.CharField("Комментарий", max_length=500, blank=True)
    total      = models.DecimalField("Сумма", max_digits=12, decimal_places=0, default=0)
    status     = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.NEW)

    class Meta:
        verbose_name = "Заявка из номера"
        verbose_name_plural = "Заявки из номеров"
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.id} {self.get_kind_display()} — {self.room}"


# ─────────────────────────────────────────────────────────────────────────────
#  ФИНАНСЫ / ДДС (движение денежных средств) — отдельно по каждому филиалу
# ─────────────────────────────────────────────────────────────────────────────

class FinanceAccount(TimeStampedModel):
    """Счёт / касса филиала: наличные, расчётный счёт, карта…"""
    class Kind(models.TextChoices):
        CASH  = "cash",  "Наличная касса"
        BANK  = "bank",  "Расчётный счёт"
        CARD  = "card",  "Карта"
        OTHER = "other", "Другое"

    branch          = models.ForeignKey(HotelBranch, on_delete=models.CASCADE, related_name="fin_accounts")
    name            = models.CharField("Название", max_length=100)
    kind            = models.CharField("Тип", max_length=10, choices=Kind.choices, default=Kind.CASH)
    opening_balance = models.DecimalField("Начальный остаток", max_digits=14, decimal_places=2, default=0)
    is_default      = models.BooleanField("Касса по умолчанию", default=False,
                                          help_text="Сюда зачисляется автодоход от броней")
    is_active       = models.BooleanField("Активен", default=True)
    sort_order      = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Счёт / касса"
        verbose_name_plural = "Счета / кассы"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name} ({self.branch})"

    def balance_on(self, until=None):
        """Остаток на счёте (опц. на дату включительно)."""
        from django.db.models import Sum
        out_q = self.txns.all()
        in_q  = self.txns_in.all()
        if until:
            out_q = out_q.filter(date__lte=until)
            in_q  = in_q.filter(date__lte=until)

        def _s(qs, kind):
            return qs.filter(kind=kind).aggregate(s=Sum("amount"))["s"] or 0

        inc    = _s(out_q, FinanceTxn.Kind.INCOME)
        exp    = _s(out_q, FinanceTxn.Kind.EXPENSE)
        tr_out = _s(out_q, FinanceTxn.Kind.TRANSFER)
        tr_in  = _s(in_q,  FinanceTxn.Kind.TRANSFER)
        return self.opening_balance + inc - exp - tr_out + tr_in

    @property
    def balance(self):
        return self.balance_on()


class FinanceCategory(TimeStampedModel):
    """Статья дохода / расхода."""
    class Flow(models.TextChoices):
        IN  = "in",  "Доход"
        OUT = "out", "Расход"

    branch     = models.ForeignKey(HotelBranch, on_delete=models.CASCADE, related_name="fin_categories")
    name       = models.CharField("Статья", max_length=120)
    flow       = models.CharField("Тип", max_length=3, choices=Flow.choices, default=Flow.OUT)
    is_active  = models.BooleanField("Активна", default=True)
    sort_order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Статья ДДС"
        verbose_name_plural = "Статьи ДДС"
        ordering = ["flow", "sort_order", "id"]

    def __str__(self):
        return f"{self.get_flow_display()}: {self.name}"


class FinanceTxn(TimeStampedModel):
    """Операция ДДС: приход, расход или перевод между счетами."""
    class Kind(models.TextChoices):
        INCOME   = "income",   "Приход"
        EXPENSE  = "expense",  "Расход"
        TRANSFER = "transfer", "Перевод"

    branch     = models.ForeignKey(HotelBranch, on_delete=models.CASCADE, related_name="fin_txns")
    kind       = models.CharField("Тип", max_length=10, choices=Kind.choices)
    date       = models.DateField("Дата")
    amount     = models.DecimalField("Сумма", max_digits=14, decimal_places=2)
    account    = models.ForeignKey(FinanceAccount, on_delete=models.PROTECT, related_name="txns",
                                   verbose_name="Счёт (откуда / куда)")
    to_account = models.ForeignKey(FinanceAccount, on_delete=models.PROTECT, related_name="txns_in",
                                   null=True, blank=True, verbose_name="Счёт зачисления (для перевода)")
    category   = models.ForeignKey(FinanceCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="txns", verbose_name="Статья")
    comment    = models.CharField("Комментарий", max_length=255, blank=True)
    booking    = models.ForeignKey(HotelBooking, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="fin_txns", verbose_name="Бронь")
    is_auto    = models.BooleanField("Автооперация", default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="+")

    class Meta:
        verbose_name = "Операция ДДС"
        verbose_name_plural = "Операции ДДС"
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount} ({self.date})"
