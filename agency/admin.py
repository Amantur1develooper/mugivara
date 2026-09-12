from django.contrib import admin
from .models import Agency, AgencyService, AgencyMembership


class AgencyServiceInline(admin.TabularInline):
    model = AgencyService
    extra = 0
    fields = ("service_type", "name", "name_en", "description", "description_en",
              "photo", "tech_stack", "price", "price_note", "delivery_days",
              "is_active", "sort_order")


@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [AgencyServiceInline]
    fieldsets = (
        (None, {"fields": ("place_category", "name", "name_en", "slug", "is_active", "sort_order")}),
        ("Слоган и описание", {"fields": ("tagline", "tagline_en", "description", "description_en", "logo", "cover")}),
        ("Контакты", {"fields": ("website", "phone", "email", "address")}),
        ("Telegram", {"fields": ("tg_chat_id", "tg_thread_id")}),
    )


@admin.register(AgencyMembership)
class AgencyMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "agency")
