from django.contrib import admin

from .models import AutoDealership, DealershipMembership, Car, CarPhoto, Lead


class CarPhotoInline(admin.TabularInline):
    model = CarPhoto
    extra = 1


@admin.register(AutoDealership)
class AutoDealershipAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "phone", "is_active", "cars_in_stock_count")
    list_filter = ("is_active", "city")
    search_fields = ("name", "city", "address", "phone")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(DealershipMembership)
class DealershipMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "dealership", "role")
    list_filter = ("dealership", "role")
    search_fields = ("user__username", "dealership__name")


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ("__str__", "dealership", "status", "condition", "year", "price", "is_active")
    list_filter = ("dealership", "status", "condition", "body_type", "fuel_type", "transmission", "is_active")
    search_fields = ("brand", "model_name", "vin")
    inlines = [CarPhotoInline]


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("__str__", "dealership", "car", "phone", "status", "source", "created_at")
    list_filter = ("dealership", "status", "source")
    search_fields = ("name", "phone", "message")
