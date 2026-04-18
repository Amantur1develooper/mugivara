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
        self.photo_compression = None
        if self.photo and hasattr(self.photo, 'file'):
            try:
                original_size = self.photo.file.seek(0, 2) or self.photo.file.tell()
                self.photo.file.seek(0)

                img = Image.open(self.photo)
                orig_w, orig_h = img.size
                img = img.convert("RGB")
                img.thumbnail((800, 800), Image.LANCZOS)
                new_w, new_h = img.size

                buf = BytesIO()
                img.save(buf, format="WEBP", quality=82, method=6)
                compressed_size = buf.tell()
                buf.seek(0)

                name = os.path.splitext(self.photo.name)[0] + ".webp"
                self.photo.save(name, ContentFile(buf.read()), save=False)

                self.photo_compression = {
                    "before_kb": round(original_size / 1024, 1),
                    "after_kb":  round(compressed_size / 1024, 1),
                    "saved_pct": round((1 - compressed_size / original_size) * 100) if original_size else 0,
                    "orig_size": f"{orig_w}×{orig_h}",
                    "new_size":  f"{new_w}×{new_h}",
                }
            except Exception:
                pass
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

    class Meta:
        unique_together = ("branch_category", "branch_item")
        ordering = ("sort_order", "id")
        verbose_name = "Порядок блюд внутри конкретной категории филиала."
        verbose_name_plural = "Порядок блюд внутри конкретной категории филиала."
