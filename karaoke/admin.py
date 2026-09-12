from django.contrib import admin
from .models import (KaraokeVenue, RoomCategory, KaraokeRoom, KaraokeRoomPhoto,
                     KaraokeBooking, KaraokeMenuCategory, KaraokeMenuItem, KaraokeMembership)


class RoomPhotoInline(admin.TabularInline):
    model = KaraokeRoomPhoto
    extra = 0


class RoomCategoryInline(admin.TabularInline):
    model = RoomCategory
    extra = 0
    fields = ("name", "name_en", "sort_order")


@admin.register(KaraokeVenue)
class KaraokeVenueAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [RoomCategoryInline]
    fieldsets = (
        (None, {"fields": ("place_category", "name", "name_en", "slug", "is_active", "sort_order")}),
        ("Слоган и описание", {"fields": ("tagline", "tagline_en", "description", "description_en", "logo", "cover")}),
        ("Контакты", {"fields": ("address", "phone", "whatsapp", "working_hours", "map_url")}),
        ("Telegram", {"fields": ("tg_chat_id", "tg_thread_id")}),
    )


@admin.register(KaraokeRoom)
class KaraokeRoomAdmin(admin.ModelAdmin):
    list_display = ("name", "venue", "category", "capacity", "price_per_hour", "is_active")
    inlines = [RoomPhotoInline]
    fields = ("venue", "category", "name", "name_en", "description", "description_en",
              "capacity", "price_per_hour", "is_active", "sort_order")


@admin.register(KaraokeMenuCategory)
class KaraokeMenuCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "venue", "sort_order")
    list_filter  = ("venue",)
    fields = ("venue", "name", "name_en", "sort_order")


@admin.register(KaraokeMenuItem)
class KaraokeMenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "venue", "category", "price", "is_active", "sort_order")
    list_filter  = ("venue", "category", "is_active")
    fields = ("venue", "category", "name", "name_en", "description", "description_en",
              "photo", "price", "cost_price", "is_active", "sort_order")


@admin.register(KaraokeBooking)
class KaraokeBookingAdmin(admin.ModelAdmin):
    list_display = ("room", "booking_date", "start_time", "end_time", "customer_name", "status")
    list_filter = ("status", "booking_date")


@admin.register(KaraokeMembership)
class KaraokeMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "venue")
