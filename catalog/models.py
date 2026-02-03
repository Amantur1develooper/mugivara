from django.db import models

# Create your models here.
from django.db import models
from core.models import Restaurant, Branch, TimeStampedModel

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

    def __str__(self):
        # чтобы везде (админка, селекты) было видно кому принадлежит
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
    sort_order = models.PositiveIntegerField(default=0)  # нумерация категории в филиале
    is_active = models.BooleanField(default=True)

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

    class Meta:
        unique_together = ("branch", "item")
        ordering = ("sort_order", "id")
        verbose_name = "Филиал"
        verbose_name_plural = "Филиал"
    def __str__(self):
        # было: return (self.branch.name_ru + '-')  (без item)
        return f"{self.branch.name_ru} — {self.item.name_ru} "
    
class BranchCategoryItem(TimeStampedModel):
    """Порядок блюд внутри конкретной категории филиала."""
    branch_category = models.ForeignKey(BranchCategory, on_delete=models.CASCADE, related_name="items_in_category")
    branch_item = models.ForeignKey(BranchItem, on_delete=models.CASCADE, related_name="categories_in_branch")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("branch_category", "branch_item")
        ordering = ("sort_order", "id")
        verbose_name = "Порядок блюд внутри конкретной категории филиала."
        verbose_name_plural = "Порядок блюд внутри конкретной категории филиала."
