from django.db import models
from core.models import Restaurant, Branch, TimeStampedModel
import os
from io import BytesIO
from django.core.files.base import ContentFile
from PIL import Image

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
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="WEBP", quality=quality, method=6)
        buf.seek(0)
        name = os.path.splitext(field.name)[0] + ".webp"
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

    def save(self, *args, **kwargs):
        _compress_photo(self.photo)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.restaurant.name_ru} — {self.name_ru}"
    class Meta:
        verbose_name = "Блюдо"
        verbose_name_plural = "Блюда"

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
    
class BranchCategory(TimeStampedModel):
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

class BranchItem(TimeStampedModel):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="branch_items")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="branch_items")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_available = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)  # нумерация блюда в филиале
    delivery_available = models.BooleanField(default=True)
    stock = models.IntegerField(null=True, blank=True, default=None)  # None=∞, 0=нет, N=остаток
    
    class Meta:
        verbose_name = "Блюдо Филиал"
        verbose_name_plural = "Блюды Филиал"
        
    def __str__(self):
        return f"{self.branch.name_ru} — {self.item.name_ru} "
    
    
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
    description = models.TextField("Описание", blank=True, default="")
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
    description = models.CharField("Описание", max_length=400, blank=True, default="")
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
