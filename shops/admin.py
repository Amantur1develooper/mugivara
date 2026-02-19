from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Store, StoreBranch, StoreCategory, StoreProduct, StoreStock


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "slug", "is_active")
    search_fields = ("name_ru", "name_ky", "name_en", "slug")
    prepopulated_fields = {"slug": ("name_ru",)}


@admin.register(StoreBranch)
class StoreBranchAdmin(admin.ModelAdmin):
    list_display = ("store", "name_ru", "phone", "is_active")
    list_filter = ("store", "is_active")
    search_fields = ("name_ru", "address", "phone")


@admin.register(StoreCategory)
class StoreCategoryAdmin(admin.ModelAdmin):
    list_display = ("store", "name_ru", "sort_order", "is_active")
    list_filter = ("store", "is_active")
    ordering = ("store", "sort_order", "id")


@admin.register(StoreProduct)
class StoreProductAdmin(admin.ModelAdmin):
    list_display = ("store", "name_ru", "category", "unit", "price", "is_active")
    list_filter = ("store", "category", "unit", "is_active")
    search_fields = ("name_ru", "name_ky", "name_en")


@admin.register(StoreStock)
class StoreStockAdmin(admin.ModelAdmin):
    list_display = ("branch", "product", "qty")
    list_filter = ("branch", "branch__store")
    search_fields = ("product__name_ru", "branch__name_ru")
