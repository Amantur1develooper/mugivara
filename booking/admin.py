from django.contrib import admin
from django.utils import timezone
from .models import Reservation

@admin.action(description="Снять бронь (освободить стол)")
def release_reservations(modeladmin, request, queryset):
    now = timezone.now()
    for r in queryset:
        if r.released_at is None:
            r.released_at = now
            r.status = Reservation.Status.CANCELLED
            r.save(update_fields=["released_at", "status"])

@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "table", "name", "phone", "status", "is_locked", "created_at", "released_at")
    list_filter = ("status", "branch__restaurant", "branch", "released_at")
    search_fields = ("name", "phone", "comment", "table__number")
    actions = (release_reservations,)

    def is_locked(self, obj):
        return obj.is_locked
    is_locked.boolean = True
    is_locked.short_description = "Стол занят"
