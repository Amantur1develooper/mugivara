import secrets
from django.contrib import admin
from .models import Table, TableSession

@admin.action(description="Перегенерировать QR токены (для выбранных столов)")
def regenerate_qr(modeladmin, request, queryset):
    for t in queryset:
        t.qr_token = secrets.token_urlsafe(24)
        t.save(update_fields=["qr_token"])

@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "number", "type", "short_token", "created_at")
    list_filter = ("branch__restaurant", "branch", "type")
    search_fields = ("number", "branch__name", "branch__restaurant__name_ru")
    actions = (regenerate_qr,)

    def short_token(self, obj):
        return obj.qr_token[:10] + "..."
    short_token.short_description = "QR token"

@admin.register(TableSession)
class TableSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "table", "status", "created_at", "closed_at")
    list_filter = ("status", "table__branch__restaurant", "table__branch")
    search_fields = ("table__number", "table__branch__name")
