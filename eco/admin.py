from django.contrib import admin
from .models import EcoProject, EcoService


class EcoServiceInline(admin.TabularInline):
    model   = EcoService
    extra   = 1
    fields  = ("name", "description", "price", "price_note", "is_active", "sort_order")
    ordering = ("sort_order", "id")


@admin.register(EcoProject)
class EcoProjectAdmin(admin.ModelAdmin):
    list_display        = ("id", "name", "phone", "working_hours", "is_active", "sort_order")
    list_editable       = ("is_active", "sort_order")
    search_fields       = ("name", "address", "phone")
    prepopulated_fields = {"slug": ("name",)}
    inlines             = [EcoServiceInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "is_active", "sort_order")}),
        ("Контакты", {"fields": ("address", "phone", "working_hours", "map_url")}),
        ("Описание и медиа", {"fields": ("description", "logo")}),
    )
