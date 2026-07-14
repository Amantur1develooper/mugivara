from django.contrib import admin
from .models import SimRacingVenue, SimRacingMembership, Machine, SessionType, Session


@admin.register(SimRacingVenue)
class SimRacingVenueAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("name", "venue", "type", "is_active", "sort_order")
    list_filter = ("venue", "type", "is_active")


@admin.register(SessionType)
class SessionTypeAdmin(admin.ModelAdmin):
    list_display = ("venue", "machine_type", "duration_minutes", "price", "is_active")
    list_filter = ("venue", "machine_type")


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("id", "machine", "duration_minutes", "price", "status", "started_at")
    list_filter = ("status", "machine__venue")
    date_hierarchy = "started_at"


admin.site.register(SimRacingMembership)
