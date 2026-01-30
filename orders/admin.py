from django.contrib import admin

from integrations.models import TelegramRecipient
from .models import Order, OrderItem
from integrations.tasks import notify_order_status

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("item", "qty", "price_snapshot", "line_total", "created_at")

@admin.action(description="Статус: Принят")
def mark_accepted(modeladmin, request, queryset):
    queryset.update(status=Order.Status.ACCEPTED)

@admin.action(description="Статус: Готовится")
def mark_cooking(modeladmin, request, queryset):
    queryset.update(status=Order.Status.COOKING)

@admin.action(description="Статус: Готов")
def mark_ready(modeladmin, request, queryset):
    queryset.update(status=Order.Status.READY)

@admin.action(description="Статус: Закрыт")
def mark_closed(modeladmin, request, queryset):
    queryset.update(status=Order.Status.CLOSED)

# @admin.register(Order)
# class OrderAdmin(admin.ModelAdmin):
#     list_display = ("id", "branch", "type", "status", "total_amount", "created_at")
#     list_filter = ("status", "type", "branch__restaurant", "branch")
#     search_fields = ("id", "customer_phone", "customer_name", "delivery_address")
#     inlines = (OrderItemInline,)
#     actions = (mark_accepted, mark_cooking, mark_ready, mark_closed)

# @admin.register(OrderItem)
# class OrderItemAdmin(admin.ModelAdmin):
#     list_display = ("id", "order", "item", "qty", "price_snapshot", "line_total")
#     list_filter = ("order__branch__restaurant", "order__branch")
#     search_fields = ("item__name",)




def _set_status_with_notify(queryset, new_status: str):
    for order in queryset:
        old = order.status
        if old == new_status:
            continue
        order.status = new_status
        order.save(update_fields=["status"])
        notify_order_status.delay(order.id, old, new_status)

@admin.action(description="Статус: Принят")
def mark_accepted(modeladmin, request, queryset):
    _set_status_with_notify(queryset, Order.Status.ACCEPTED)

@admin.action(description="Статус: Готовится")
def mark_cooking(modeladmin, request, queryset):
    _set_status_with_notify(queryset, Order.Status.COOKING)

@admin.action(description="Статус: Готов")
def mark_ready(modeladmin, request, queryset):
    _set_status_with_notify(queryset, Order.Status.READY)

@admin.action(description="Статус: Закрыт")
def mark_closed(modeladmin, request, queryset):
    _set_status_with_notify(queryset, Order.Status.CLOSED)

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id","branch","type","status","payment_method","payment_status","total_amount","created_at")
    list_filter = ("status","type","payment_method","payment_status","branch__restaurant","branch")
    search_fields = ("id","customer_phone","customer_name","delivery_address")
    inlines = (OrderItemInline,)
    actions = (mark_accepted, mark_cooking, mark_ready, mark_closed)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id","order","item","qty","price_snapshot","line_total")
class TelegramRecipientInline(admin.TabularInline):
    model = TelegramRecipient
    extra = 0
    fields = ("kind", "title", "chat_id", "is_active", "message_thread_id", "notify_new_orders", "notify_status_changes")
