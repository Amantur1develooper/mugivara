from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Floor, Place, Booking


@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "name_ru", "sort_order", "is_active")
    list_filter = ("branch__restaurant", "branch", "is_active")
    search_fields = ("name_ru", "name_ky", "name_en", "branch__name_ru")
    ordering = ("branch", "sort_order", "id")


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ("id", "floor", "type", "title", "seats", "is_active")
    list_filter = ("floor__branch__restaurant", "floor__branch", "floor", "type", "is_active")
    search_fields = ("title", "floor__name_ru", "floor__branch__name_ru")
    ordering = ("floor", "type", "title", "id")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "place", "status", "guests_count", "customer_phone", "created_at")
    list_filter = ("branch__restaurant", "branch", "status")
    search_fields = ("customer_name", "customer_phone", "place__title")
    ordering = ("-created_at",)

    actions = ("mark_cleared", "mark_active", "mark_cancelled")

    @admin.action(description="Снять бронь (освободить)")
    def mark_cleared(self, request, queryset):
        queryset.update(status=Booking.Status.CLEARED)

    @admin.action(description="Вернуть в занято (активно)")
    def mark_active(self, request, queryset):
        queryset.update(status=Booking.Status.ACTIVE)

    @admin.action(description="Отменить")
    def mark_cancelled(self, request, queryset):
        queryset.update(status=Booking.Status.CANCELLED)
