# -*- coding: utf-8 -*-
"""Металлургия: производства металлоизделий и их каталог.

Отличие от магазина: здесь не кладут в корзину. Двери, щиты и корзины для
кондиционеров делают под размер заказчика, поэтому цена в каталоге —
ориентир («от 32 000»), а покупка начинается с заявки или сообщения в
WhatsApp. Поэтому вместо заказа с суммой тут лид, как в автосалоне.
"""
import os
import urllib.parse
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.utils.translation import get_language, gettext_lazy as _
from PIL import Image, ImageOps

from core.models import TimeStampedModel


def _compress_photo(field, max_side=1440, quality=82):
    """Ужимает фото до max_side и переводит в WebP. True — если получилось."""
    if not (field and hasattr(field, "file")):
        return False
    try:
        field.file.seek(0)
        img = Image.open(field)
        # Телефон почти всегда снимает «в альбом», а как повернуть кадр
        # пишет в EXIF-тег Orientation. Pillow этот тег не применяет, и при
        # пересохранении в WebP он терялся — фото с айфона вставало боком.
        # exif_transpose разворачивает пиксели так, как задумано съёмкой.
        img = ImageOps.exif_transpose(img) or img
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=6)
        buf.seek(0)
        # basename, а не field.name: иначе upload_to подставится дважды
        name = os.path.splitext(os.path.basename(field.name))[0] + ".webp"
        field.save(name, ContentFile(buf.read()), save=False)
        return True
    except Exception:
        return False


def pick_lang(obj, base_field):
    """Значение поля на языке витрины: base_ky / base_en, иначе базовое."""
    lang = (get_language() or "ru")[:2]
    if lang != "ru":
        val = (getattr(obj, f"{base_field}_{lang}", "") or "").strip()
        if val:
            return val
    for name in (f"{base_field}_ru", base_field):
        val = (getattr(obj, name, "") or "").strip()
        if val:
            return val
    return ""


def _digits(raw):
    return "".join(ch for ch in (raw or "") if ch.isdigit())


def _fmt_price(value):
    """1 500 вместо 1500.00 — в каталоге копеек не бывает."""
    if value is None:
        return ""
    return f"{int(value):,}".replace(",", " ")


class MetalCompany(TimeStampedModel):
    place_category = models.ForeignKey(
        "core.PlaceCategory", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="metal_companies",
        verbose_name="Категория платформы",
    )
    name       = models.CharField("Название", max_length=200)
    name_ky    = models.CharField("Название (кырг.)", max_length=200, blank=True, default="")
    name_en    = models.CharField("Название (англ.)", max_length=200, blank=True, default="")
    slug       = models.SlugField(max_length=220, unique=True)
    logo       = models.ImageField("Логотип", upload_to="metalwork/logos/", blank=True, null=True)
    cover      = models.ImageField("Обложка", upload_to="metalwork/covers/", blank=True, null=True)
    tagline    = models.CharField("Короткая строка под названием", max_length=200, blank=True, default="",
                                  help_text="Например: двери, щиты и металлоконструкции на заказ")
    tagline_ky = models.CharField("Короткая строка (кырг.)", max_length=200, blank=True, default="")
    tagline_en = models.CharField("Короткая строка (англ.)", max_length=200, blank=True, default="")
    description    = models.TextField("Описание", blank=True, default="")
    description_ky = models.TextField("Описание (кырг.)", blank=True, default="")
    description_en = models.TextField("Описание (англ.)", blank=True, default="")

    phone      = models.CharField("Телефон", max_length=50, blank=True, default="")
    whatsapp   = models.CharField("WhatsApp", max_length=50, blank=True, default="",
                                  help_text="Если пусто — кнопка «Написать» возьмёт телефон")
    email      = models.EmailField("E-mail", blank=True, default="")
    instagram  = models.CharField("Instagram (ник или ссылка)", max_length=120, blank=True, default="")
    city       = models.CharField("Город", max_length=120, blank=True, default="")
    address    = models.CharField("Адрес", max_length=300, blank=True, default="")
    work_hours = models.CharField("Режим работы", max_length=200, blank=True, default="",
                                  help_text="Например: Пн–Сб 09:00–18:00")
    map_url    = models.URLField("Ссылка на карту", blank=True, default="")
    lat        = models.DecimalField("Широта", max_digits=10, decimal_places=7, null=True, blank=True)
    lon        = models.DecimalField("Долгота", max_digits=10, decimal_places=7, null=True, blank=True)

    is_active  = models.BooleanField("Активно", default=True)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Производство"
        verbose_name_plural = "Металлургия: производства"
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        _compress_photo(self.logo, max_side=512)
        _compress_photo(self.cover, max_side=1600)
        super().save(*args, **kwargs)

    @property
    def contact_digits(self):
        """Номер для кнопки «Написать»: сначала WhatsApp, потом телефон."""
        return _digits(self.whatsapp) or _digits(self.phone)

    @property
    def whatsapp_url(self):
        d = self.contact_digits
        if not d:
            return ""
        text = f"Здравствуйте! Пишу с Webordo по каталогу «{self.name}»."
        return f"https://wa.me/{d}?text={urllib.parse.quote(text)}"

    @property
    def instagram_url(self):
        ig = (self.instagram or "").strip()
        if not ig:
            return ""
        if ig.startswith("http"):
            return ig
        return f"https://instagram.com/{ig.lstrip('@')}"

    @property
    def products_count(self):
        return self.products.filter(is_active=True).count()


class MetalMembership(TimeStampedModel):
    class Role(models.TextChoices):
        DIRECTOR = "director", "Директор"
        MANAGER  = "manager", "Менеджер"

    user    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="metalwork_memberships")
    company = models.ForeignKey(MetalCompany, on_delete=models.CASCADE, related_name="memberships")
    role    = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.MANAGER)

    class Meta:
        verbose_name = "Доступ к производству"
        verbose_name_plural = "Металлургия: доступы"
        unique_together = ("user", "company")

    def __str__(self):
        return f"{self.user} → {self.company} ({self.get_role_display()})"


class MetalCategory(TimeStampedModel):
    company    = models.ForeignKey(MetalCompany, on_delete=models.CASCADE, related_name="categories")
    name       = models.CharField("Название", max_length=200)
    name_ky    = models.CharField("Название (кырг.)", max_length=200, blank=True, default="")
    name_en    = models.CharField("Название (англ.)", max_length=200, blank=True, default="")
    icon       = models.CharField("Иконка (эмодзи)", max_length=8, blank=True, default="",
                                  help_text="Одним символом: 🚪, 🧯, ⚡")
    is_active  = models.BooleanField("Активна", default=True)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Раздел каталога"
        verbose_name_plural = "Металлургия: разделы каталога"
        ordering = ["sort_order", "id"]
        unique_together = ("company", "name")

    def __str__(self):
        return f"{self.company.name} / {self.name}"

    @property
    def title(self):
        return pick_lang(self, "name")

    @property
    def anchor(self):
        return f"cat-{self.id}"


class MetalProduct(TimeStampedModel):
    company     = models.ForeignKey(MetalCompany, on_delete=models.CASCADE, related_name="products")
    category    = models.ForeignKey(MetalCategory, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="products", verbose_name="Раздел")
    name        = models.CharField("Название", max_length=200)
    name_ky     = models.CharField("Название (кырг.)", max_length=200, blank=True, default="")
    name_en     = models.CharField("Название (англ.)", max_length=200, blank=True, default="")
    description    = models.TextField("Описание", blank=True, default="")
    description_ky = models.TextField("Описание (кырг.)", blank=True, default="")
    description_en = models.TextField("Описание (англ.)", blank=True, default="")

    # Характеристики — по строке «Название: значение». Так их заполняет
    # владелец в кабинете, а витрина рисует из них таблицу. Отдельная таблица
    # строк дала бы то же самое ценой формы на двадцать полей.
    specs    = models.TextField(
        "Характеристики", blank=True, default="",
        help_text="По одной в строке, в виде «Название: значение». Например: Высота полотна: 2050 мм",
    )
    specs_ky = models.TextField("Характеристики (кырг.)", blank=True, default="")
    specs_en = models.TextField("Характеристики (англ.)", blank=True, default="")

    price      = models.DecimalField("Цена, сом", max_digits=12, decimal_places=2, null=True, blank=True,
                                     help_text="Пусто — покажем «Цена по запросу»")
    price_from = models.BooleanField("Цена «от»", default=True,
                                     help_text="Изделие делают по размеру, точную сумму считают по проекту")
    price_note = models.CharField("Приписка к цене", max_length=120, blank=True, default="",
                                  help_text="Например: без монтажа")
    price_note_ky = models.CharField("Приписка к цене (кырг.)", max_length=120, blank=True, default="")
    price_note_en = models.CharField("Приписка к цене (англ.)", max_length=120, blank=True, default="")

    photo      = models.ImageField("Главное фото", upload_to="metalwork/products/", blank=True, null=True)
    is_custom  = models.BooleanField("Размер и вид согласовываются по проекту", default=True)
    is_active  = models.BooleanField("Показывать в каталоге", default=True)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Изделие"
        verbose_name_plural = "Металлургия: изделия"
        ordering = ["sort_order", "id"]
        indexes = [models.Index(fields=["company", "is_active"], name="metal_product_active_idx")]

    def __str__(self):
        return f"{self.company.name} / {self.name}"

    def save(self, *args, **kwargs):
        _compress_photo(self.photo)
        super().save(*args, **kwargs)

    # ── витрина ──────────────────────────────────────────────────────────
    @property
    def title(self):
        return pick_lang(self, "name")

    @property
    def text(self):
        return pick_lang(self, "description")

    @property
    def note(self):
        return pick_lang(self, "price_note")

    @property
    def spec_rows(self):
        """[(«Высота полотна», «2050 мм»), …] — из текста по строкам.

        Строка без двоеточия — не характеристика, а отдельная фраза
        («Нестандартные размеры по проекту»), её отдаём без названия.
        """
        rows = []
        for line in (pick_lang(self, "specs") or "").splitlines():
            line = line.strip()
            if not line:
                continue
            name, sep, value = line.partition(":")
            if sep and value.strip():
                rows.append((name.strip(), value.strip()))
            else:
                rows.append(("", line))
        return rows

    @property
    def price_display(self):
        if self.price is None:
            return ""
        return f"{_fmt_price(self.price)} сом"

    @property
    def main_photo(self):
        if self.photo:
            return self.photo
        first = self.photos.first()
        return first.photo if first else None

    @property
    def gallery(self):
        """Главное фото первым, затем остальные — так открывается просмотрщик."""
        urls = []
        if self.photo:
            urls.append(self.photo.url)
        urls += [p.photo.url for p in self.photos.all() if p.photo]
        return urls

    @property
    def whatsapp_url(self):
        d = self.company.contact_digits
        if not d:
            return ""
        parts = [self.title]
        if self.price_display:
            parts.append(("от " if self.price_from else "") + self.price_display)
        text = "Здравствуйте! Интересует: " + ", ".join(p for p in parts if p)
        return f"https://wa.me/{d}?text={urllib.parse.quote(text)}"


class MetalProductPhoto(TimeStampedModel):
    product    = models.ForeignKey(MetalProduct, on_delete=models.CASCADE, related_name="photos")
    photo      = models.ImageField("Фото", upload_to="metalwork/products/")
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Фото изделия"
        verbose_name_plural = "Фото изделия"
        ordering = ["sort_order", "id"]

    def save(self, *args, **kwargs):
        _compress_photo(self.photo)
        super().save(*args, **kwargs)


class MetalLead(TimeStampedModel):
    """Заявка с витрины. В отличие от перехода в WhatsApp её видно в кабинете:
    контакт не теряется, даже если менеджер не успел ответить в мессенджере."""

    class Status(models.TextChoices):
        NEW       = "new", _("Новая")
        CONTACTED = "contacted", _("Связались")
        WON       = "won", _("Сделка")
        LOST      = "lost", _("Отказ")

    class Source(models.TextChoices):
        PRODUCT = "product", _("Страница изделия")
        COMPANY = "company", _("Страница производства")

    company = models.ForeignKey(MetalCompany, on_delete=models.CASCADE, related_name="leads")
    product = models.ForeignKey(MetalProduct, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="leads", verbose_name="Изделие")
    name    = models.CharField("Имя", max_length=120, blank=True, default="")
    phone   = models.CharField("Телефон", max_length=50)
    message = models.TextField("Сообщение", blank=True, default="")
    source  = models.CharField("Источник", max_length=20, choices=Source.choices, default=Source.PRODUCT)
    status  = models.CharField("Статус", max_length=20, choices=Status.choices, default=Status.NEW)
    note    = models.TextField("Заметка менеджера", blank=True, default="")

    class Meta:
        verbose_name = "Заявка"
        verbose_name_plural = "Металлургия: заявки"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name or self.phone} — {self.company} ({self.get_status_display()})"

    @property
    def phone_digits(self):
        return _digits(self.phone)
