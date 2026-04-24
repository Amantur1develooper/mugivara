from django.contrib import admin

from .models import Order, OrderItem, ConstructorOrderItem
from integrations.tasks import notify_order_status


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ("item", "qty", "price_snapshot", "line_total", "created_at")


class ConstructorOrderItemInline(admin.TabularInline):
    model = ConstructorOrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        "constructor", "constructor_name_snapshot",
        "qty", "unit_price", "line_total", "ingredients_snapshot",
    )


def _set_status_with_notify(queryset, new_status: str):
    for order in queryset:
        old = order.status
        if old == new_status:
            continue
        order.status = new_status
        order.save(update_fields=["status"])
        notify_order_status.delay(order.id, old, new_status)


@admin.action(description="✅ Статус: Принят")
def mark_accepted(modeladmin, request, queryset):
    _set_status_with_notify(queryset, Order.Status.ACCEPTED)


@admin.action(description="👨‍🍳 Статус: Готовится")
def mark_cooking(modeladmin, request, queryset):
    _set_status_with_notify(queryset, Order.Status.COOKING)


@admin.action(description="🔔 Статус: Готов")
def mark_ready(modeladmin, request, queryset):
    _set_status_with_notify(queryset, Order.Status.READY)


@admin.action(description="🔒 Статус: Закрыт")
def mark_closed(modeladmin, request, queryset):
    _set_status_with_notify(queryset, Order.Status.CLOSED)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id", "branch", "type", "status",
        "customer_name", "customer_phone",
        "payment_method", "payment_status",
        "total_amount", "created_at",
    )
    list_filter   = ("status", "type", "payment_method", "payment_status", "branch__restaurant", "branch")
    search_fields = ("id", "customer_phone", "customer_name", "delivery_address")
    date_hierarchy      = "created_at"
    list_per_page       = 30
    list_select_related = ("branch", "branch__restaurant")
    save_on_top         = True
    inlines = (OrderItemInline, ConstructorOrderItemInline)
    actions = (mark_accepted, mark_cooking, mark_ready, mark_closed)
    readonly_fields = ("total_amount", "created_at", "updated_at")

    fieldsets = (
        ("Заказ", {
            "fields": ("branch", "type", "status", "total_amount", "created_at", "updated_at"),
        }),
        ("Клиент", {
            "fields": ("customer_name", "customer_phone", "delivery_address", "comment"),
        }),
        ("Оплата", {
            "fields": ("payment_method", "payment_status"),
        }),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display  = ("id", "order", "item", "qty", "price_snapshot", "line_total")
    list_filter   = ("order__branch__restaurant", "order__branch")
    search_fields = ("item__name_ru", "order__customer_name", "order__customer_phone")
    list_per_page       = 50
    list_select_related = ("order", "order__branch", "item")
    readonly_fields = ("order", "item", "qty", "price_snapshot", "line_total", "created_at")
