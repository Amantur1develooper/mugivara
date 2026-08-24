from django.contrib import admin
from .models import RealtyAgency, RealtyMembership, Apartment, ApartmentPhoto


class ApartmentPhotoInline(admin.TabularInline):
    model = ApartmentPhoto
    extra = 1
    fields = ("photo", "sort_order")
    ordering = ("sort_order", "id")


@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display  = ("id", "address", "agency", "realtor", "price", "currency", "status", "is_active", "sort_order")
    list_filter   = ("agency", "status", "renovation", "is_active")
    search_fields = ("address", "city", "district")
    list_editable = ("status", "is_active", "sort_order")
    inlines       = [ApartmentPhotoInline]
    fieldsets = (
        (None, {"fields": ("agency", "realtor", "status", "is_active", "sort_order")}),
        ("Адрес", {"fields": ("city", "district", "address")}),
        ("Параметры", {"fields": ("area", "rooms", "floor", "floors_total", "renovation")}),
        ("Цена и описание", {"fields": ("price", "price_per_sqm", "currency", "description")}),
        ("Обзоры", {"fields": ("review_url_1", "review_url_2")}),
    )


class RealtyMembershipInline(admin.TabularInline):
    model = RealtyMembership
    extra = 1
    fields = ("user", "role", "phone")
    autocomplete_fields = ("user",)


@admin.register(RealtyAgency)
class RealtyAgencyAdmin(admin.ModelAdmin):
    list_display        = ("id", "name", "phone", "is_active", "sort_order")
    list_editable        = ("is_active", "sort_order")
    search_fields        = ("name", "address", "phone")
    prepopulated_fields  = {"slug": ("name",)}
    inlines              = [RealtyMembershipInline]
    fieldsets = (
        (None, {"fields": ("place_category", "name", "slug", "is_active", "sort_order")}),
        ("Контакты", {"fields": ("address", "phone")}),
        ("Описание и медиа", {"fields": ("description", "logo", "cover")}),
    )


@admin.register(RealtyMembership)
class RealtyMembershipAdmin(admin.ModelAdmin):
    list_display  = ("user", "agency", "role", "phone")
    list_filter   = ("agency", "role")
    autocomplete_fields = ("user",)


@admin.register(ApartmentPhoto)
class ApartmentPhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "apartment", "sort_order")
    list_filter  = ("apartment__agency",)
