from django.contrib import admin
from .models import RestaurantPrintConfig, PrinterGroup, Printer, PrintJob


@admin.register(RestaurantPrintConfig)
class RestaurantPrintConfigAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "enabled", "token", "last_heartbeat")
    readonly_fields = ("token",)


class PrinterInline(admin.TabularInline):
    model = Printer
    extra = 1


@admin.register(PrinterGroup)
class PrinterGroupAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "name", "display_name")
    list_filter = ("restaurant",)
    inlines = [PrinterInline]


@admin.register(PrintJob)
class PrintJobAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurant", "order_id", "group", "status", "retries", "created_at", "printed_at")
    list_filter = ("status", "restaurant")
    readonly_fields = ("created_at", "printed_at")
