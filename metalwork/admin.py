# -*- coding: utf-8 -*-
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    MetalCategory, MetalCompany, MetalLead, MetalMembership,
    MetalProduct, MetalProductPhoto,
)


class MetalCategoryInline(admin.TabularInline):
    model = MetalCategory
    extra = 1
    fields = ("name", "name_ky", "name_en", "icon", "is_active", "sort_order")


class MetalMembershipInline(admin.TabularInline):
    model = MetalMembership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(MetalCompany)
class MetalCompanyAdmin(admin.ModelAdmin):
    list_display  = ("logo_preview", "name", "city", "products_count", "is_active", "sort_order")
    list_display_links = ("logo_preview", "name")
    list_filter   = ("is_active", "city")
    search_fields = ("name", "city", "address", "phone")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (MetalCategoryInline, MetalMembershipInline)
    fieldsets = (
        ("Основное", {"fields": (
            ("name", "name_ky", "name_en"), "slug", "place_category",
            ("logo", "cover"),
            ("tagline", "tagline_ky", "tagline_en"),
            "description", "description_ky", "description_en",
        )}),
        ("Контакты", {"fields": (
            ("phone", "whatsapp"), ("email", "instagram"),
            ("city", "address"), "work_hours", "map_url", ("lat", "lon"),
        )}),
        ("Показ", {"fields": (("is_active", "sort_order"),)}),
    )

    @admin.display(description="")
    def logo_preview(self, obj):
        src = obj.logo.url if obj.logo else (obj.cover.url if obj.cover else "")
        if not src:
            return "—"
        return format_html(
            '<img src="{}" style="width:46px;height:46px;object-fit:cover;border-radius:10px">', src)

    @admin.display(description="Изделий")
    def products_count(self, obj):
        return obj.products.filter(is_active=True).count()


class MetalProductPhotoInline(admin.TabularInline):
    model = MetalProductPhoto
    extra = 1
    fields = ("photo", "preview", "sort_order")
    readonly_fields = ("preview",)

    @admin.display(description="Как выглядит")
    def preview(self, obj):
        if not obj.photo:
            return "—"
        return format_html('<img src="{}" style="height:70px;border-radius:8px">', obj.photo.url)


@admin.register(MetalProduct)
class MetalProductAdmin(admin.ModelAdmin):
    list_display  = ("photo_preview", "name", "company", "category", "price_label", "is_active", "sort_order")
    list_display_links = ("photo_preview", "name")
    list_filter   = ("company", "category", "is_active", "is_custom")
    list_select_related = ("company", "category")
    search_fields = ("name", "description", "specs")
    list_per_page = 40
    inlines = (MetalProductPhotoInline,)
    fieldsets = (
        ("Основное", {"fields": (
            ("company", "category"),
            ("name", "name_ky", "name_en"),
            "description", "description_ky", "description_en",
            "photo",
        )}),
        ("Характеристики", {
            "description": "По одной в строке, в виде «Название: значение»",
            "fields": ("specs", "specs_ky", "specs_en"),
        }),
        ("Цена", {"fields": (
            ("price", "price_from"),
            ("price_note", "price_note_ky", "price_note_en"),
            "is_custom",
        )}),
        ("Показ", {"fields": (("is_active", "sort_order"),)}),
    )

    @admin.display(description="")
    def photo_preview(self, obj):
        p = obj.main_photo
        if not p:
            return "—"
        return format_html(
            '<img src="{}" style="width:54px;height:54px;object-fit:cover;border-radius:10px">', p.url)

    @admin.display(description="Цена")
    def price_label(self, obj):
        if obj.price is None:
            return "по запросу"
        return ("от " if obj.price_from else "") + obj.price_display


@admin.register(MetalCategory)
class MetalCategoryAdmin(admin.ModelAdmin):
    list_display  = ("name", "company", "icon", "products_count", "is_active", "sort_order")
    list_filter   = ("company", "is_active")
    search_fields = ("name",)

    @admin.display(description="Изделий")
    def products_count(self, obj):
        return obj.products.filter(is_active=True).count()


@admin.register(MetalLead)
class MetalLeadAdmin(admin.ModelAdmin):
    list_display  = ("created_at", "name", "phone", "company", "product", "source", "status")
    list_filter   = ("company", "status", "source")
    list_select_related = ("company", "product")
    search_fields = ("name", "phone", "message")
    list_editable = ("status",)
    date_hierarchy = "created_at"


@admin.register(MetalMembership)
class MetalMembershipAdmin(admin.ModelAdmin):
    list_display  = ("user", "company", "role")
    list_filter   = ("company", "role")
    autocomplete_fields = ("user",)
