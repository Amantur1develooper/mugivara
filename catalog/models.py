from decimal import Decimal

from django.db import models
from django.utils.translation import get_language
from core.models import Restaurant, Branch, TimeStampedModel
import os
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def pick_lang(obj, base_field):
    """Значение поля на языке витрины: base_field_ky / _en, иначе base_field.

    Повторяет логику шаблонного тега {% t %}, но нужна и в Python — состав
    конструктора уезжает в шаблон уже готовыми строками.
    """
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


class MenuSet(TimeStampedModel):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="menu_sets")
    name = models.CharField(max_length=200)  # "Основное", "Завтраки", ...
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.restaurant}: {self.name}"
    class Meta:
        verbose_name = "Меню сет"
        verbose_name_plural = "Меню сеты"
        
class Category(TimeStampedModel):
    menu_set = models.ForeignKey(MenuSet, on_delete=models.CASCADE, related_name="categories")
    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    photo = models.ImageField(
        "Фото категории", upload_to="categories/photos/", blank=True, null=True,
        help_text="Обложка раздела меню. Показывается в оформлении, которое её поддерживает.",
    )

    def save(self, *args, **kwargs):
        _compress_photo(self.photo)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.menu_set.name}: {self.name_ru}"
    class Meta:
        verbose_name = "Категории"
        verbose_name_plural = "Категории"
        
def _compress_photo(field, max_side=900, quality=82):
    """Resize to max_side×max_side, convert to WebP. Returns True if processed."""
    if not (field and hasattr(field, 'file')):
        return False
    try:
        field.file.seek(0)
        img = Image.open(field)
        # Телефон почти всегда снимает «в альбом», а как повернуть кадр
        # пишет в EXIF-тег Orientation. Pillow этот тег не применяет, и при
        # пересохранении в WebP он терялся — фото с айфона вставало боком.
        # exif_transpose разворачивает пиксели так, как задумано съёмкой.
        # Формат запоминаем до поворота: exif_transpose отдаёт новую картинку
        # с format=None, поэтому проверка ниже не срабатывала и готовый webp
        # пересжимался при каждом сохранении блюда.
        was_webp = (img.format or "").upper() == "WEBP"
        img = ImageOps.exif_transpose(img) or img
        # Уже готовый лёгкий WebP не трогаем: повторное кодирование не уменьшает
        # файл, а качество съедает (и нередко делает его даже тяжелее).
        if was_webp and max(img.size) <= max_side:
            return False
        # Прозрачный фон сохраняем: блюдо «вырезанное» из фона красиво ложится
        # на любую подложку. convert("RGB") залил бы альфу чёрным.
        has_alpha = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        )
        img = img.convert("RGBA" if has_alpha else "RGB")
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=6)
        buf.seek(0)
        # basename, не field.name — иначе upload_to подставится дважды: field.name
        # уже содержит префикс (например "items/photos/x.jpg") после первого
        # сохранения, а field.save() сам заново применяет upload_to к имени.
        name = os.path.splitext(os.path.basename(field.name))[0] + ".webp"
        field.save(name, ContentFile(buf.read()), save=False)
        return True
    except Exception:
        return False


class Item(TimeStampedModel):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="items")

    name_ru = models.CharField(max_length=200)
    name_ky = models.CharField(max_length=200, blank=True, default="")
    name_en = models.CharField(max_length=200, blank=True, default="")
    
    description_ru = models.TextField(blank=True, default="")
    description_ky = models.TextField(blank=True, default="")
    description_en = models.TextField(blank=True, default="")
    
    photo = models.ImageField(upload_to="items/photos/", blank=True, null=True)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    order_count = models.PositiveIntegerField("Кол-во заказов", default=0, db_index=True)
    rating      = models.DecimalField("Рейтинг", max_digits=3, decimal_places=1, default=1.0)

    calories = models.PositiveSmallIntegerField("Калории, ккал", null=True, blank=True)
    protein  = models.DecimalField("Белки, г", max_digits=5, decimal_places=1, null=True, blank=True)
    fat      = models.DecimalField("Жиры, г", max_digits=5, decimal_places=1, null=True, blank=True)
    carbs    = models.DecimalField("Углеводы, г", max_digits=5, decimal_places=1, null=True, blank=True)

    def save(self, *args, **kwargs):
        _compress_photo(self.photo)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.restaurant.name_ru} — {self.name_ru}"
    class Meta:
        verbose_name = "Блюдо"
        verbose_name_plural = "Блюда"
        unique_together = ("restaurant", "name_ru")

class ItemCategory(TimeStampedModel):
    """Блюдо может быть в нескольких категориях в рамках одного MenuSet."""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="item_categories")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="item_categories")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("item", "category")
        ordering = ("sort_order", "id")
        verbose_name = "категория блюд в сете"
        verbose_name_plural = "категория блюд в сете"
    def __str__(self):
        # было: return self.category  (это объект, не строка)
        return f"{self.category.name_ru} ← {self.item.name_ru}"

class BranchMenuSet(TimeStampedModel):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="branch_menu_sets")
    menu_set = models.ForeignKey(MenuSet, on_delete=models.CASCADE, related_name="branch_menu_sets")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("branch", "menu_set")
        
    def __str__(self):
        # было: return (self.branch + '-' + self.menu_set)  (объекты)
        return f"{self.branch.name_ru} — {self.menu_set.name}"
    
class ServingWindowMixin(models.Model):
    """Часы подачи: «завтраки до 11:00», «бизнес-ланч с 12 до 15».

    Пусто — подаём весь день. Если конец меньше начала, окно переходит через
    полночь: ночное меню с 22:00 до 04:00 — обычное дело.
    """
    available_from = models.TimeField(
        "Подаём с", null=True, blank=True,
        help_text="Оставьте пустым, если доступно весь день",
    )
    available_to = models.TimeField(
        "Подаём до", null=True, blank=True,
        help_text="Например, завтраки — до 11:00",
    )

    class Meta:
        abstract = True

    @property
    def has_serving_window(self):
        return bool(self.available_from or self.available_to)

    def is_servable_at(self, moment):
        """Подаём ли в это время суток."""
        start, end = self.available_from, self.available_to
        if not (start or end):
            return True
        if start and end:
            if start <= end:
                return start <= moment <= end
            return moment >= start or moment <= end     # окно через полночь
        if start:
            return moment >= start
        return moment <= end

    @property
    def serving_window_text(self):
        """«до 11:00», «с 12:00», «с 12:00 до 15:00»."""
        start, end = self.available_from, self.available_to
        if start and end:
            return f"с {start:%H:%M} до {end:%H:%M}"
        if start:
            return f"с {start:%H:%M}"
        if end:
            return f"до {end:%H:%M}"
        return ""


class BranchCategory(ServingWindowMixin, TimeStampedModel):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="branch_categories")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="branch_categories")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    printer_group = models.ForeignKey(
        "printing.PrinterGroup",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="branch_categories",
        verbose_name="Принтер (группа)",
    )

    class Meta:
        unique_together = ("branch", "category")
        ordering = ("sort_order", "id")
        verbose_name = "Категория филилла"
        verbose_name_plural = "Категория филила"
        
    def __str__(self):
        return (self.branch.name_ru + '-' + self.category.name_ru )

class BranchItem(ServingWindowMixin, TimeStampedModel):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="branch_items")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="branch_items")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_available = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)  # нумерация блюда в филиале
    delivery_available = models.BooleanField(default=True)
    stock = models.IntegerField(null=True, blank=True, default=None)  # None=∞, 0=нет, N=остаток

    # ── Акция / скидка ──────────────────────────────────────────────────────
    old_price = models.DecimalField(
        "Старая цена (до акции)", max_digits=10, decimal_places=2,
        null=True, blank=True, default=None,
        help_text="Заполните, чтобы запустить акцию: укажите прежнюю цену, а в поле "
                   "«Цена» — новую. На сайте старая цена покажется зачёркнутой, "
                   "новая — выделенной, на карточке появится бейдж.",
    )
    promo_label = models.CharField(
        "Текст бейджа", max_length=20, blank=True, default="",
        help_text="Например «Акция» или «Скидка». Если оставить пустым — «Акция».",
    )
    label = models.CharField(
        "Метка на карточке", max_length=20, blank=True, default="",
        help_text="Например «Хит», «Новинка», «Острое». Показывается без скидки; "
                  "если запущена акция, бейдж акции важнее.",
    )

    class Meta:
        verbose_name = "Блюдо Филиал"
        verbose_name_plural = "Блюды Филиал"
        unique_together = ("branch", "item")

    def __str__(self):
        return f"{self.branch.name_ru} — {self.item.name_ru} "

    @property
    def is_on_promo(self):
        return self.old_price is not None and self.old_price > self.price

    @property
    def discount_pct(self):
        if not self.is_on_promo:
            return 0
        return int(round((1 - self.price / self.old_price) * 100))

    @property
    def promo_badge_text(self):
        from django.utils.translation import gettext
        return self.promo_label.strip() or gettext("Акция")

    @property
    def badge_text(self):
        """Что показать на карточке: бейдж акции важнее обычной метки."""
        if self.is_on_promo:
            return self.promo_badge_text
        return self.label.strip()

    # ── Размеры ──────────────────────────────────────────────────────────────

    def size_list(self):
        """Активные размеры по порядку. Пусто — у блюда один размер.

        Результат запоминаем на объекте: шаблон карточки спрашивает
        размеры несколько раз подряд (есть ли они, какой по умолчанию,
        цена от), и без этого каждая проверка шла бы в базу отдельно.
        """
        if not hasattr(self, "_size_list_cache"):
            self._size_list_cache = [z for z in self.sizes.all() if z.is_active]
        return self._size_list_cache

    @property
    def has_sizes(self):
        return bool(self.size_list())

    def default_size(self):
        """Размер, выбранный заранее: помеченный, иначе самый дешёвый."""
        sizes = self.size_list()
        if not sizes:
            return None
        for z in sizes:
            if z.is_default:
                return z
        return min(sizes, key=lambda z: z.price)

    @property
    def price_from(self):
        """Цена, которую показываем на карточке: за размер по умолчанию."""
        z = self.default_size()
        return z.price if z else self.price
    
    
class BranchItemSize(TimeStampedModel):
    """Размер блюда со своей ценой: «30 см», «0,5 л», «большая порция».

    Цена указывается полная, а не надбавка: так её проще держать в голове
    и видно в списке, сколько стоит каждый вариант. У блюда без размеров
    всё работает как раньше — цена берётся из самого блюда филиала.
    """
    branch_item = models.ForeignKey(BranchItem, on_delete=models.CASCADE,
                                    related_name="sizes")
    name = models.CharField("Размер", max_length=60)
    name_ky = models.CharField("Размер (кырг.)", max_length=60, blank=True, default="")
    name_en = models.CharField("Размер (англ.)", max_length=60, blank=True, default="")
    price = models.DecimalField("Цена (сом)", max_digits=10, decimal_places=2, default=0)
    # Во сколько раз этот размер расходует больше продуктов, чем техкарта.
    # Техкарта у блюда одна, а теста на сорокасантиметровую пиццу уходит
    # больше: без множителя склад списывал бы одинаково на любой размер.
    tc_factor = models.DecimalField(
        "Расход по техкарте, ×", max_digits=6, decimal_places=3,
        default=Decimal("1"),
        help_text="1 — как в техкарте. Для 40 см при техкарте на 30 см — около 1.6")
    is_default = models.BooleanField("По умолчанию", default=False)
    is_active = models.BooleanField("Активен", default=True)
    sort_order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Размер блюда"
        verbose_name_plural = "Размеры блюд"

    def __str__(self):
        return f"{self.branch_item} — {self.name}"


class BranchCategoryItem(TimeStampedModel):
    """Порядок блюд внутри конкретной категории филиала."""
    branch_category = models.ForeignKey(BranchCategory, on_delete=models.CASCADE, related_name="items_in_category")
    branch_item = models.ForeignKey(BranchItem, on_delete=models.CASCADE, related_name="categories_in_branch")
    sort_order = models.PositiveIntegerField(default=0)
    printer_group = models.ForeignKey(
        "printing.PrinterGroup",
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="category_items",
        verbose_name="Принтер блюда",
    )

    class Meta:
        unique_together = ("branch_category", "branch_item")
        ordering = ("sort_order", "id")
        verbose_name = "Порядок блюд внутри конкретной категории филиала."
        verbose_name_plural = "Порядок блюд внутри конкретной категории филиала."


# ── КОНСТРУКТОР БЛЮД ──────────────────────────────────────────────────────────

class DishConstructor(TimeStampedModel):
    """Конструктор: «Собери свой бургер», «Собери свою пиццу» и т.п."""
    branch      = models.ForeignKey("core.Branch", on_delete=models.CASCADE, related_name="dish_constructors")
    name        = models.CharField("Название", max_length=200)
    name_ky     = models.CharField("Название (кырг.)", max_length=200, blank=True, default="")
    name_en     = models.CharField("Название (англ.)", max_length=200, blank=True, default="")
    description = models.TextField("Описание", blank=True, default="")
    description_ky = models.TextField("Описание (кырг.)", blank=True, default="")
    description_en = models.TextField("Описание (англ.)", blank=True, default="")
    photo       = models.ImageField("Фото", upload_to="constructors/", blank=True, null=True)
    base_price  = models.DecimalField("Базовая цена (сом)", max_digits=10, decimal_places=0, default=0,
                                      help_text="Цена без учёта доп. ингредиентов")
    is_active   = models.BooleanField("Активен", default=True)
    sort_order  = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Конструктор блюда"
        verbose_name_plural = "Конструкторы блюд"

    def save(self, *args, **kwargs):
        _compress_photo(self.photo)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.branch} / {self.name}"


class ConstructorGroup(TimeStampedModel):
    """Шаг конструктора: «Булочка», «Котлета», «Соус»."""
    constructor = models.ForeignKey(DishConstructor, on_delete=models.CASCADE, related_name="groups")
    name        = models.CharField("Название шага", max_length=200)
    name_ky     = models.CharField("Название шага (кырг.)", max_length=200, blank=True, default="")
    name_en     = models.CharField("Название шага (англ.)", max_length=200, blank=True, default="")
    min_select  = models.PositiveSmallIntegerField("Минимум выбора", default=1)
    max_select  = models.PositiveSmallIntegerField("Максимум выбора", default=1,
                                                    help_text="0 = без лимита")
    sort_order  = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Группа конструктора"
        verbose_name_plural = "Группы конструктора"

    def __str__(self):
        return f"{self.constructor.name} / {self.name}"


class ConstructorIngredient(TimeStampedModel):
    """Позиция внутри категории конструктора. Может ссылаться на блюдо из меню."""
    group       = models.ForeignKey(ConstructorGroup, on_delete=models.CASCADE, related_name="ingredients")
    # Привязка к блюду из меню (если задана — имя/фото/цена берутся оттуда)
    branch_item = models.ForeignKey(
        "catalog.BranchItem", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+", verbose_name="Блюдо из меню"
    )
    # Ручные поля (используются когда branch_item не задан)
    name        = models.CharField("Название", max_length=200, blank=True, default="")
    name_ky     = models.CharField("Название (кырг.)", max_length=200, blank=True, default="")
    name_en     = models.CharField("Название (англ.)", max_length=200, blank=True, default="")
    description = models.CharField("Описание", max_length=400, blank=True, default="")
    description_ky = models.CharField("Описание (кырг.)", max_length=400, blank=True, default="")
    description_en = models.CharField("Описание (англ.)", max_length=400, blank=True, default="")
    price       = models.DecimalField("Цена (сом)", max_digits=10, decimal_places=0, default=0)
    photo       = models.ImageField("Фото", upload_to="constructors/ingredients/", blank=True, null=True)
    is_active   = models.BooleanField("Активен", default=True)
    sort_order  = models.PositiveSmallIntegerField("Порядок", default=0)

    # Связь со складом: какой ингредиент списывать и в каком количестве на 1 шт
    warehouse_ingredient = models.ForeignKey(
        "techcards.Ingredient",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="constructor_lines",
        verbose_name="Ингредиент склада",
        help_text="Какой ингредиент списывать при закрытии заказа",
    )
    write_off_qty = models.DecimalField(
        "Кол-во списания (на 1 шт)",
        max_digits=10, decimal_places=3,
        default=1,
        help_text="Сколько единиц ингредиента списывать за каждую единицу этой позиции",
    )

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Позиция конструктора"
        verbose_name_plural = "Позиции конструктора"

    def save(self, *args, **kwargs):
        _compress_photo(self.photo)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.group.name} / {self.display_name}"

    @property
    def display_name(self):
        if self.branch_item_id:
            return self.branch_item.item.name_ru
        return self.name

    @property
    def display_description(self):
        if self.branch_item_id:
            return self.branch_item.item.description_ru or ""
        return self.description

    @property
    def display_price(self):
        if self.branch_item_id:
            return self.branch_item.price
        return self.price

    @property
    def display_photo_url(self):
        photo = self.branch_item.item.photo if self.branch_item_id else self.photo
        return photo.url if photo else ""

    # ── витрина на трёх языках ───────────────────────────────────────────
    # display_name/display_description остаются русскими: из них собирается
    # состав заказа и кухонный чек, и повар не должен получать тикет на
    # английском только потому, что гость переключил язык витрины.
    @property
    def display_name_i18n(self):
        if self.branch_item_id:
            return pick_lang(self.branch_item.item, "name") or self.display_name
        return pick_lang(self, "name") or self.name

    @property
    def display_description_i18n(self):
        if self.branch_item_id:
            return pick_lang(self.branch_item.item, "description") or ""
        return pick_lang(self, "description") or ""
