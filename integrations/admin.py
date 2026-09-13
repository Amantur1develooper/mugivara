from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import TelegramRecipient

@admin.register(TelegramRecipient)
class TelegramRecipientAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "kind", "chat_id", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("title", "chat_id")
    # integrations/admin.py
from django.contrib import admin
from .models import TelegramRecipient, BranchTelegramLink, ShopTelegramRecipient

class BranchTelegramLinkInline(admin.TabularInline):
    model = BranchTelegramLink
    extra = 0
    autocomplete_fields = ("recipient",)
    fields = ("recipient", "notify_orders", "notify_bookings")


@admin.register(ShopTelegramRecipient)
class ShopTelegramRecipientAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "title", "kind", "chat_id", "is_active", "notify_new_orders")
    list_filter = ("kind", "is_active")
    search_fields = ("title", "chat_id", "branch__name_ru")
    autocomplete_fields = ("branch",)



