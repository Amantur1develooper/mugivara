from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.contrib import admin
from .models import BranchStaffToken
from .models import Floor, Place, Booking
from django.utils.safestring import mark_safe

# -----------------------------
# Inlines
# -----------------------------
class PlaceInline(admin.TabularInline):
    model = Place
    extra = 0
    fields = ("title", "type", "seats",'token', "x", "y", "photo_preview", "photo", "is_active")
    readonly_fields = ("photo_preview",)
    ordering = ("id",)

    @admin.display(description="Фото")
    def photo_preview(self, obj: Place):
        if obj and obj.photo:
            return format_html(
                '<img src="{}" style="height:50px; width:50px; object-fit:cover; border-radius:8px;" />',
                obj.photo.url,
            )
        return "—"
# /s/<token>/bookings/

# -----------------------------
# Floor Admin
# -----------------------------
@admin.register(Floor)
class FloorAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "name_ru", "sort_order", "is_active", "places_count", "created_at", "updated_at")
    list_filter = ("branch", "is_active")
    search_fields = ("name_ru", "name_ky", "name_en", "branch__name")
    list_editable = ("sort_order", "is_active")
    ordering = ("sort_order", "id")
    inlines = (PlaceInline,)

    # если в TimeStampedModel поля называются иначе — поменяй тут
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Основное", {"fields": ("branch", "name_ru", "name_ky", "name_en")}),
        ("Настройки", {"fields": ("sort_order", "is_active")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("branch").prefetch_related("places")

    @admin.display(description="Мест")
    def places_count(self, obj: Floor):
        return obj.places.count()


# -----------------------------
# Place Admin
# -----------------------------
@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ("id", "title",'token',"type", "seats", "floor", "branch", "is_active", "photo_thumb", "created_at")
    list_filter = ("type", "is_active", "floor__branch", "floor")
    search_fields = ("title", "floor__name_ru", "floor__branch__name")
    list_editable = ("is_active",)
    ordering = ("floor__sort_order", "id")

    # если Floor/Branch большие — удобно включить автокомплит
    autocomplete_fields = ("floor",)

    readonly_fields = ("photo_thumb_big", "created_at", "updated_at")

    fieldsets = (
        ("Основное", {"fields": ("floor", 'token', "title", "type", "seats", "is_active")}),
        ("План зала", {"fields": ("x", "y")}),
        ("Фото", {"fields": ("photo_thumb_big", "photo")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )
    def open_menu_link(self, obj):
        if not obj.token:
            return "-"
        return mark_safe(f'<a href="/t/{obj.token}/menu/" target="_blank">Открыть меню</a>')
    open_menu_link.short_description = "Меню стола"
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("floor", "floor__branch")

    @admin.display(description="Филиал")
    def branch(self, obj: Place):
        return obj.floor.branch

    @admin.display(description="Фото")
    def photo_thumb(self, obj: Place):
        if obj.photo:
            return format_html(
                '<img src="{}" style="height:40px; width:40px; object-fit:cover; border-radius:8px;" />',
                obj.photo.url,
            )
        return "—"

    @admin.display(description="Превью")
    def photo_thumb_big(self, obj: Place):
        if obj.photo:
            return format_html(
                '<img src="{}" style="max-height:220px; width:auto; object-fit:cover; border-radius:14px;" />',
                obj.photo.url,
            )
        return "—"


# -----------------------------
# Booking Admin Form (валидатор)
# -----------------------------
class BookingAdminForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        place = cleaned.get("place")
        branch = cleaned.get("branch")

        if place:
            real_branch = place.floor.branch
            # если админ выбрал филиал вручную и он не совпал — покажем ошибку
            if branch and branch != real_branch:
                self.add_error("branch", "Филиал должен совпадать с филиалом выбранного места (стола/кабинки).")
        return cleaned


# -----------------------------
# Booking Admin
# -----------------------------
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    form = BookingAdminForm

    list_display = (
        "id",
        "branch",
        "floor",
        "place",
        "status",
        "customer_name",
        "customer_phone",
        "guests_count",
        "started_at",
        "created_at",
    )
    list_filter = ("status", "branch", "place__floor", "started_at")
    search_fields = ("customer_name", "customer_phone", "place__title", "branch__name")
    date_hierarchy = "started_at"
    ordering = ("-id",)

    autocomplete_fields = ("place", "branch")

    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Место", {"fields": ("place", "branch")}),
        ("Клиент", {"fields": ("customer_name", "customer_phone", "guests_count", "comment")}),
        ("Статус/время", {"fields": ("status", "started_at")}),
        ("Служебное", {"fields": ("created_at", "updated_at")}),
    )

    actions = ("mark_arrived", "mark_closed", "mark_canceled", "mark_active")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("branch", "place", "place__floor")

    @admin.display(description="Этаж")
    def floor(self, obj: Booking):
        return obj.place.floor

    # --- Авто-выставление branch по месту ---
    def save_model(self, request, obj: Booking, form, change):
        if obj.place:
            obj.branch = obj.place.floor.branch
        super().save_model(request, obj, form, change)

    # --- Actions ---
    @admin.action(description="Статус → Гость пришёл")
    def mark_arrived(self, request, queryset):
        queryset.update(status=Booking.Status.ARRIVED)

    @admin.action(description="Статус → Закрыта")
    def mark_closed(self, request, queryset):
        queryset.update(status=Booking.Status.CLOSED)

    @admin.action(description="Статус → Отменена")
    def mark_canceled(self, request, queryset):
        queryset.update(status=Booking.Status.CANCELED)

    @admin.action(description="Статус → Активна")
    def mark_active(self, request, queryset):
        queryset.update(status=Booking.Status.ACTIVE)
        


@admin.register(BranchStaffToken)
class BranchStaffTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "title", "is_active", "token", "created_at")
    list_filter = ("branch", "is_active")
    search_fields = ("title", "token", "branch__name_ru")
