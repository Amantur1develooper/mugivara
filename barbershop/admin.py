from django.contrib import admin
from .models import (Barbershop, BarbershopMembership, ServiceCategory, Service,
                     Barber, BarberSchedule, BarberService, Appointment)

@admin.register(Barbershop)
class BarbershopAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "phone", "is_active"]
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("place_category", "name", "name_en", "slug", "is_active")}),
        ("Слоган и описание", {"fields": ("tagline", "tagline_en", "description", "description_en", "logo", "cover")}),
        ("Контакты", {"fields": ("address", "phone", "whatsapp", "working_hours", "map_url")}),
        ("Telegram", {"fields": ("tg_chat_id", "tg_thread_id")}),
    )

@admin.register(BarbershopMembership)
class BarbershopMembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "barbershop"]

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "barbershop", "sort_order", "is_active"]
    fields = ["barbershop", "name", "name_en", "sort_order", "is_active"]

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["name", "barbershop", "category", "price", "duration_min", "is_active"]
    fields = ["barbershop", "category", "name", "name_en", "description", "description_en",
              "price", "duration_min", "is_active", "sort_order"]

@admin.register(Barber)
class BarberAdmin(admin.ModelAdmin):
    list_display = ["name", "barbershop", "experience", "is_active"]

@admin.register(BarberSchedule)
class BarberScheduleAdmin(admin.ModelAdmin):
    list_display = ["barber", "weekday", "start_time", "end_time", "is_working"]

@admin.register(BarberService)
class BarberServiceAdmin(admin.ModelAdmin):
    list_display = ["barber", "service"]

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["id", "customer_name", "service_name", "barber_name", "appt_date", "appt_time", "status", "is_paid"]
    list_filter = ["status", "source", "is_paid", "appt_date"]
    search_fields = ["customer_name", "customer_phone", "service_name"]
