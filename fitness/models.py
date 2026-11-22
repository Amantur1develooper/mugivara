# -*- coding: utf-8 -*-
"""Фитнес-клуб: клиенты, абонементы, тренеры, заявки, касса, расходы.

Устройство повторяет рабочую программу клуба (клиент → абонемент →
посещения → платежи), но добавляет то, чего в ней не было: тренеров с
расписанием, заявки с воронкой, расходы и две группы в Telegram.

Отдельно стоит отметить начало абонемента: клиент покупает его сегодня, а
ходить начинает когда захочет, поэтому по умолчанию абонемент лежит
неактивированным и отсчёт срока начинается с первого посещения.
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


def _compress(field):
    """Сжимает загруженную картинку.

    Берём готовую функцию барбершопа: там уже учтён поворот с айфона по
    EXIF, из-за которого фото вставало боком.
    """
    try:
        from barbershop.models import _compress as shrink
        return shrink(field)
    except Exception:
        return False


# ── Клуб и доступы ──────────────────────────────────────────────────────────

class FitnessClub(TimeStampedModel):
    place_category = models.ForeignKey(
        "core.PlaceCategory", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="fitness_clubs",
        verbose_name="Категория платформы",
    )
    name        = models.CharField("Название", max_length=200)
    name_en     = models.CharField("Название (EN)", max_length=200, blank=True, default="")
    slug        = models.SlugField(max_length=220, unique=True)
    tagline     = models.CharField("Слоган", max_length=300, blank=True, default="")
    tagline_en  = models.CharField("Слоган (EN)", max_length=300, blank=True, default="")
    description = models.TextField("Описание", blank=True, default="")
    description_en = models.TextField("Описание (EN)", blank=True, default="")
    logo        = models.ImageField("Логотип", upload_to="fitness/logos/", blank=True, null=True)
    cover       = models.ImageField("Обложка", upload_to="fitness/covers/", blank=True, null=True)
    address     = models.CharField("Адрес", max_length=300, blank=True, default="")
    phone       = models.CharField("Телефон", max_length=50, blank=True, default="")
    whatsapp    = models.CharField("WhatsApp (с кодом страны)", max_length=30, blank=True, default="",
                                   help_text="996700123456 — без + и пробелов")
    working_hours = models.CharField("Часы работы", max_length=200, blank=True, default="")
    instagram   = models.CharField("Instagram", max_length=120, blank=True, default="")
    map_url     = models.URLField("Ссылка на карту", blank=True, default="")

    # Две группы: в одну летят заявки с сайта, в другую — всё по залу
    # (приход клиента, продажи, расходы). Вперемешку это читать невозможно.
    tg_leads_chat_id   = models.CharField("TG заявки — Chat ID", max_length=50, blank=True, default="")
    tg_leads_thread_id = models.PositiveIntegerField("TG заявки — Topic ID", null=True, blank=True)
    tg_gym_chat_id     = models.CharField("TG зал — Chat ID", max_length=50, blank=True, default="")
    tg_gym_thread_id   = models.PositiveIntegerField("TG зал — Topic ID", null=True, blank=True)

    is_active  = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Фитнес-клуб"
        verbose_name_plural = "Фитнес-клубы"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        _compress(self.logo)
        _compress(self.cover)
        super().save(*args, **kwargs)


class ClubStaff(TimeStampedModel):
    """Доступ к клубу и уровень прав.

    Три уровня: администратор видит всё, кассир — продажи и приход, тренер
    — только своих клиентов и своё расписание.
    """
    class Role(models.TextChoices):
        ADMIN   = "admin", "Администратор"
        CASHIER = "cashier", "Кассир"
        TRAINER = "trainer", "Тренер"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="fitness_staff")
    club = models.ForeignKey(FitnessClub, on_delete=models.CASCADE, related_name="staff")
    role = models.CharField("Уровень доступа", max_length=12,
                            choices=Role.choices, default=Role.CASHIER)
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Сотрудник клуба"
        verbose_name_plural = "Сотрудники клуба"
        unique_together = ("user", "club")

    def __str__(self):
        return f"{self.user} → {self.club} ({self.get_role_display()})"


# ── Секции и тренеры ────────────────────────────────────────────────────────

class Section(TimeStampedModel):
    """Направление клуба: тренажёрный зал, бокс, йога."""
    club        = models.ForeignKey(FitnessClub, on_delete=models.CASCADE, related_name="sections")
    name        = models.CharField("Название", max_length=150)
    name_en     = models.CharField("Название (EN)", max_length=150, blank=True, default="")
    description = models.TextField("Описание", blank=True, default="")
    description_en = models.TextField("Описание (EN)", blank=True, default="")
    photo       = models.ImageField("Фото", upload_to="fitness/sections/", blank=True, null=True)
    price_from  = models.DecimalField("Цена от (сом)", max_digits=10, decimal_places=0, default=0)
    is_active   = models.BooleanField("Активна", default=True)
    sort_order  = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Секция"
        verbose_name_plural = "Секции"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.club.name} — {self.name}"

    def save(self, *args, **kwargs):
        _compress(self.photo)
        super().save(*args, **kwargs)


class Trainer(TimeStampedModel):
    club     = models.ForeignKey(FitnessClub, on_delete=models.CASCADE, related_name="trainers")
    # Связь с пользователем нужна, чтобы тренер мог войти и видеть своё
    user     = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="fitness_trainer")
    name     = models.CharField("Имя", max_length=150)
    photo    = models.ImageField("Фото", upload_to="fitness/trainers/", blank=True, null=True)
    bio      = models.TextField("О тренере", blank=True, default="")
    bio_en   = models.TextField("О тренере (EN)", blank=True, default="")
    sections = models.ManyToManyField(Section, blank=True, related_name="trainers",
                                      verbose_name="Секции")
    experience_years = models.PositiveSmallIntegerField("Опыт, лет", default=0)
    price_per_session = models.DecimalField("Цена тренировки (сом)", max_digits=10,
                                            decimal_places=0, default=0)
    phone      = models.CharField("Телефон", max_length=50, blank=True, default="")
    is_active  = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Тренер"
        verbose_name_plural = "Тренеры"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name} ({self.club.name})"

    def save(self, *args, **kwargs):
        _compress(self.photo)
        super().save(*args, **kwargs)


class TrainerSchedule(TimeStampedModel):
    """Когда тренер работает — по дням недели."""
    trainer   = models.ForeignKey(Trainer, on_delete=models.CASCADE, related_name="schedule")
    weekday   = models.PositiveSmallIntegerField("День недели", choices=[
        (0, "Понедельник"), (1, "Вторник"), (2, "Среда"), (3, "Четверг"),
        (4, "Пятница"), (5, "Суббота"), (6, "Воскресенье"),
    ])
    time_from = models.TimeField("С")
    time_to   = models.TimeField("До")
    is_active = models.BooleanField("Работает", default=True)

    class Meta:
        verbose_name = "Рабочий день тренера"
        verbose_name_plural = "Расписание тренеров"
        ordering = ["weekday", "time_from"]
        unique_together = ("trainer", "weekday", "time_from")

    def __str__(self):
        return f"{self.trainer.name}: {self.get_weekday_display()} {self.time_from:%H:%M}–{self.time_to:%H:%M}"


# ── Абонементы и клиенты ────────────────────────────────────────────────────

class MembershipPlan(TimeStampedModel):
    """Вид абонемента: сколько посещений и на сколько дней."""
    club          = models.ForeignKey(FitnessClub, on_delete=models.CASCADE, related_name="plans")
    section       = models.ForeignKey(Section, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="plans", verbose_name="Секция")
    name          = models.CharField("Название", max_length=150)
    visits_number = models.PositiveIntegerField("Количество посещений", default=12,
                                                help_text="0 — без ограничения по числу посещений")
    validity_days = models.PositiveIntegerField("Срок действия, дней", default=30)
    price         = models.DecimalField("Цена (сом)", max_digits=10, decimal_places=0, default=0)
    description   = models.TextField("Описание", blank=True, default="")
    is_active     = models.BooleanField("Активен", default=True)
    sort_order    = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Вид абонемента"
        verbose_name_plural = "Виды абонементов"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.name} — {self.price} сом"


class Member(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = "m", "Мужской"
        FEMALE = "f", "Женский"

    club       = models.ForeignKey(FitnessClub, on_delete=models.CASCADE, related_name="members")
    full_name  = models.CharField("ФИО", max_length=200)
    phone      = models.CharField("Телефон", max_length=30, blank=True, default="")
    birth_date = models.DateField("Дата рождения", null=True, blank=True)
    gender     = models.CharField("Пол", max_length=1, choices=Gender.choices, blank=True, default="")
    photo      = models.ImageField("Фото", upload_to="fitness/members/", blank=True, null=True)
    card_id    = models.CharField("Номер карты", max_length=50, blank=True, default="",
                                  help_text="Карта доступа, если выдаётся")
    notes      = models.TextField("Примечания", blank=True, default="")
    is_active  = models.BooleanField("Активен", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "Клиент клуба"
        verbose_name_plural = "Клиенты клуба"
        ordering = ["full_name"]
        indexes = [models.Index(fields=["club", "phone"]),
                   models.Index(fields=["club", "card_id"])]

    def __str__(self):
        return self.full_name

    def save(self, *args, **kwargs):
        _compress(self.photo)
        super().save(*args, **kwargs)

    def active_membership(self):
        """Абонемент, по которому сейчас можно пройти."""
        today = timezone.localdate()
        for m in self.memberships.filter(is_active=True).order_by("end_date", "id"):
            if m.is_usable(today):
                return m
        return None

    @property
    def debt_total(self):
        return sum((m.debt_amount for m in self.memberships.all()), 0)


class Membership(TimeStampedModel):
    """Купленный абонемент.

    start_date пустая, пока клиент не пришёл: срок считается с первого
    посещения. Так клиент не теряет дни, пока собирается начать, а клуб не
    спорит с ним об этом.
    """
    member     = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="memberships")
    plan       = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name="memberships")
    trainer    = models.ForeignKey(Trainer, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="memberships", verbose_name="Персональный тренер")
    purchase_date = models.DateField("Дата покупки", default=timezone.localdate)
    start_date = models.DateField("Дата начала", null=True, blank=True,
                                  help_text="Пусто — активируется с первого посещения")
    end_date   = models.DateField("Дата окончания", null=True, blank=True)
    remaining_visits = models.PositiveIntegerField("Осталось посещений", default=0)
    is_active  = models.BooleanField("Активен", default=True)

    price          = models.DecimalField("Цена", max_digits=10, decimal_places=0, default=0)
    discount_amount = models.DecimalField("Скидка", max_digits=10, decimal_places=0, default=0)
    paid_amount    = models.DecimalField("Оплачено", max_digits=10, decimal_places=0, default=0)
    debt_amount    = models.DecimalField("Долг", max_digits=10, decimal_places=0, default=0)

    is_frozen   = models.BooleanField("Заморожен", default=False)
    freeze_start = models.DateField("Заморозка с", null=True, blank=True)
    freeze_days  = models.PositiveIntegerField("Дней заморозки", default=0)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "Абонемент"
        verbose_name_plural = "Абонементы"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.member.full_name} — {self.plan.name}"

    @property
    def activated(self):
        return self.start_date is not None

    def is_usable(self, today=None):
        """Можно ли пройти по этому абонементу сегодня."""
        today = today or timezone.localdate()
        if not self.is_active or self.is_frozen:
            return False
        if self.plan.visits_number and self.remaining_visits <= 0:
            return False
        if not self.activated:
            return True          # ещё не начат — первое посещение его откроет
        return self.end_date is None or self.end_date >= today

    def activate(self, day=None):
        """Открывает абонемент: с этого дня идёт срок."""
        day = day or timezone.localdate()
        if self.activated:
            return False
        self.start_date = day
        self.end_date = day + timedelta(days=self.plan.validity_days or 0)
        self.save(update_fields=["start_date", "end_date", "updated_at"])
        return True

    @property
    def days_left(self):
        if not self.end_date:
            return None
        return (self.end_date - timezone.localdate()).days


class Visit(TimeStampedModel):
    """Приход клиента в зал — и удачный, и отказ."""
    club       = models.ForeignKey(FitnessClub, on_delete=models.CASCADE, related_name="visits")
    member     = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="visits")
    membership = models.ForeignKey(Membership, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="visits")
    trainer    = models.ForeignKey(Trainer, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="visits", verbose_name="С тренером")
    visit_time = models.DateTimeField("Время", default=timezone.now)
    success    = models.BooleanField("Пропущен", default=True)
    reason     = models.CharField("Причина отказа", max_length=200, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "Посещение"
        verbose_name_plural = "Посещения"
        ordering = ["-visit_time"]
        indexes = [models.Index(fields=["club", "visit_time"])]

    def __str__(self):
        who = self.member.full_name if self.member else "неизвестный"
        return f"{who} — {self.visit_time:%d.%m %H:%M}"


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Наличные"
        CARD = "card", "Карта"
        ONLINE = "online", "Перевод"

    class Kind(models.TextChoices):
        MEMBERSHIP = "membership", "Абонемент"
        SESSION = "session", "Тренировка"
        CARD_SALE = "card", "Карта доступа"
        DEBT = "debt", "Погашение долга"
        OTHER = "other", "Прочее"

    club       = models.ForeignKey(FitnessClub, on_delete=models.CASCADE, related_name="payments")
    member     = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="payments")
    membership = models.ForeignKey(Membership, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="payments")
    amount     = models.DecimalField("Сумма", max_digits=10, decimal_places=0)
    method     = models.CharField("Способ", max_length=10, choices=Method.choices, default=Method.CASH)
    kind       = models.CharField("За что", max_length=12, choices=Kind.choices, default=Kind.MEMBERSHIP)
    note       = models.CharField("Примечание", max_length=300, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "Платёж"
        verbose_name_plural = "Платежи"
        ordering = ["-id"]
        indexes = [models.Index(fields=["club", "created_at"])]

    def __str__(self):
        return f"{self.amount} сом — {self.get_kind_display()}"


class Expense(TimeStampedModel):
    """Расходы клуба: коммуналка, ремонт, зарплата, инвентарь."""
    class Category(models.TextChoices):
        UTILITIES = "utilities", "Коммунальные"
        REPAIR    = "repair", "Ремонт"
        SALARY    = "salary", "Зарплата"
        EQUIPMENT = "equipment", "Инвентарь"
        RENT      = "rent", "Аренда"
        MARKETING = "marketing", "Реклама"
        OTHER     = "other", "Прочее"

    club       = models.ForeignKey(FitnessClub, on_delete=models.CASCADE, related_name="expenses")
    category   = models.CharField("Категория", max_length=12, choices=Category.choices,
                                  default=Category.OTHER)
    amount     = models.DecimalField("Сумма", max_digits=12, decimal_places=0)
    spent_on   = models.DateField("Дата", default=timezone.localdate)
    note       = models.CharField("На что", max_length=300, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "Расход"
        verbose_name_plural = "Расходы"
        ordering = ["-spent_on", "-id"]
        indexes = [models.Index(fields=["club", "spent_on"])]

    def __str__(self):
        return f"{self.get_category_display()} — {self.amount} сом"


# ── Заявки (CRM) и запись к тренеру ─────────────────────────────────────────

class Lead(TimeStampedModel):
    """Заявка с сайта или звонка — и её путь до продажи."""
    class Status(models.TextChoices):
        NEW      = "new", "Новая"
        WORKING  = "working", "В работе"
        BOOKED   = "booked", "Записан"
        CAME     = "came", "Пришёл"
        SOLD     = "sold", "Купил"
        LOST     = "lost", "Отказ"

    class Source(models.TextChoices):
        SITE   = "site", "Сайт"
        PHONE  = "phone", "Звонок"
        INSTA  = "insta", "Instagram"
        WALKIN = "walkin", "Пришёл сам"
        OTHER  = "other", "Другое"

    club    = models.ForeignKey(FitnessClub, on_delete=models.CASCADE, related_name="leads")
    name    = models.CharField("Имя", max_length=150, blank=True, default="")
    phone   = models.CharField("Телефон", max_length=30)
    source  = models.CharField("Источник", max_length=10, choices=Source.choices, default=Source.SITE)
    section = models.ForeignKey(Section, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="leads", verbose_name="Интересует секция")
    trainer = models.ForeignKey(Trainer, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="leads", verbose_name="К тренеру")
    status  = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.NEW)
    comment = models.TextField("Комментарий", blank=True, default="")
    # Когда перезвонить: без этого заявки теряются молча
    next_contact_at = models.DateTimeField("Связаться", null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="fitness_leads",
                                    verbose_name="Ответственный")
    member  = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="leads", verbose_name="Стал клиентом")
    tg_messages = models.JSONField("Сообщения в Telegram", default=dict, blank=True)

    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Заявки"
        ordering = ["-id"]
        indexes = [models.Index(fields=["club", "status"])]

    def __str__(self):
        return f"{self.name or 'Без имени'} · {self.phone} ({self.get_status_display()})"


class LeadNote(TimeStampedModel):
    """Что сделали по заявке — история звонков и договорённостей."""
    lead    = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="notes")
    text    = models.TextField("Что сделали")
    author  = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "Запись по заявке"
        verbose_name_plural = "Записи по заявкам"
        ordering = ["-id"]

    def __str__(self):
        return f"{self.lead_id}: {self.text[:40]}"


class TrainerBooking(TimeStampedModel):
    """Запись к тренеру — из неё складывается шахматка."""
    class Status(models.TextChoices):
        NEW       = "new", "Новая"
        CONFIRMED = "confirmed", "Подтверждена"
        CAME      = "came", "Пришёл"
        NO_SHOW   = "no_show", "Не пришёл"
        CANCELLED = "cancelled", "Отменена"

    club    = models.ForeignKey(FitnessClub, on_delete=models.CASCADE, related_name="bookings")
    trainer = models.ForeignKey(Trainer, on_delete=models.CASCADE, related_name="bookings")
    member  = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="bookings")
    lead    = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="bookings")
    client_name = models.CharField("Имя", max_length=150, blank=True, default="")
    phone   = models.CharField("Телефон", max_length=30, blank=True, default="")
    date    = models.DateField("Дата")
    time_from = models.TimeField("Время")
    duration_min = models.PositiveSmallIntegerField("Длительность, мин", default=60)
    status  = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.NEW)
    comment = models.CharField("Комментарий", max_length=300, blank=True, default="")
    price   = models.DecimalField("Стоимость", max_digits=10, decimal_places=0, default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    tg_messages = models.JSONField("Сообщения в Telegram", default=dict, blank=True)

    class Meta:
        verbose_name = "Запись к тренеру"
        verbose_name_plural = "Записи к тренерам"
        ordering = ["date", "time_from"]
        indexes = [models.Index(fields=["club", "date"]),
                   models.Index(fields=["trainer", "date"])]

    def __str__(self):
        return f"{self.trainer.name} · {self.date:%d.%m} {self.time_from:%H:%M} · {self.who}"

    @property
    def who(self):
        if self.member_id:
            return self.member.full_name
        return self.client_name or self.phone or "Гость"

    @property
    def time_to(self):
        from datetime import datetime, timedelta as _td
        base = datetime.combine(self.date, self.time_from)
        return (base + _td(minutes=self.duration_min or 60)).time()
