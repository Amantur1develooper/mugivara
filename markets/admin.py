from django.contrib import admin
from .models import Market


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display  = ("id", "name_ru", "address", "phone", "working_hours", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")
    search_fields = ("name_ru", "address")
    prepopulated_fields = {"slug": ("name_ru",)}
    fieldsets = (
        (None, {"fields": ("name_ru", "slug", "is_active", "sort_order")}),
        ("Контакты", {"fields": ("address", "phone", "working_hours", "map_url", "website_url")}),
        ("Описание", {"fields": ("description_ru",)}),
        ("Медиа", {"fields": ("logo", "photo1", "photo2", "photo3")}),
    )
