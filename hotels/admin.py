from django.contrib import admin
from .models import Hotel, HotelBranch, RoomCategory, Room


class RoomCategoryInline(admin.TabularInline):
    model = RoomCategory
    extra = 1
    fields = ("name_ru", "sort_order")


class RoomInline(admin.TabularInline):
    model = Room
    extra = 0
    fields = ("name_ru", "category", "price_per_night", "max_guests", "is_available", "sort_order")
    show_change_link = True


class HotelBranchInline(admin.TabularInline):
    model = HotelBranch
    extra = 0
    fields = ("name_ru", "address", "phone", "is_active", "external_url")
    show_change_link = True


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ("id", "name_ru", "slug", "rating", "is_active")
    list_editable = ("rating", "is_active")
    search_fields = ("name_ru", "slug")
    prepopulated_fields = {"slug": ("name_ru",)}
    inlines = (HotelBranchInline,)
    fieldsets = (
        (None, {"fields": ("name_ru", "name_ky", "name_en", "slug", "logo", "is_active", "rating")}),
        ("О нас", {"fields": ("about_ru", "external_url")}),
    )


@admin.register(HotelBranch)
class HotelBranchAdmin(admin.ModelAdmin):
    list_display = ("id", "hotel", "name_ru", "address", "phone", "is_active")
    list_filter = ("hotel", "is_active")
    search_fields = ("name_ru", "hotel__name_ru", "address")
    inlines = (RoomCategoryInline, RoomInline)


@admin.register(RoomCategory)
class RoomCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name_ru", "branch", "sort_order")
    list_filter = ("branch__hotel",)
    search_fields = ("name_ru",)


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("id", "name_ru", "branch", "category", "price_per_night", "price_per_extra_guest", "max_guests", "is_available")
    list_filter = ("branch__hotel", "is_available")
    list_editable = ("is_available", "price_per_night", "price_per_extra_guest")
    search_fields = ("name_ru", "branch__name_ru")
    fieldsets = (
        (None, {"fields": ("branch", "category", "name_ru", "price_per_night", "price_per_extra_guest", "max_guests", "is_available", "sort_order")}),
        ("Описание", {"fields": ("description_ru", "amenities_ru")}),
        ("Фотографии", {"fields": ("photo1", "photo2", "photo3")}),
    )
