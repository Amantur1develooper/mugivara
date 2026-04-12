from django.contrib import admin
from .models import (KaraokeVenue, RoomCategory, KaraokeRoom, KaraokeRoomPhoto,
                     KaraokeBooking, KaraokeMenuCategory, KaraokeMenuItem, KaraokeMembership)


class RoomPhotoInline(admin.TabularInline):
    model = KaraokeRoomPhoto
    extra = 0


class RoomCategoryInline(admin.TabularInline):
    model = RoomCategory
    extra = 0


@admin.register(KaraokeVenue)
class KaraokeVenueAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [RoomCategoryInline]


@admin.register(KaraokeRoom)
class KaraokeRoomAdmin(admin.ModelAdmin):
    list_display = ("name", "venue", "category", "capacity", "price_per_hour", "is_active")
    inlines = [RoomPhotoInline]


@admin.register(KaraokeBooking)
class KaraokeBookingAdmin(admin.ModelAdmin):
    list_display = ("room", "booking_date", "start_time", "end_time", "customer_name", "status")
    list_filter = ("status", "booking_date")


@admin.register(KaraokeMembership)
class KaraokeMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "venue")
