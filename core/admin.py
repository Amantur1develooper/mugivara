from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django import forms

from .models import Restaurant, Branch, Membership

from catalog.models import MenuSet, Item, BranchMenuSet, BranchItem
from catalog.services import sync_branch_menu, ensure_links_for_branch_item

from integrations.admin import BranchTelegramLinkInline



class BranchMenuSetInline(admin.TabularInline):
    model = BranchMenuSet
    extra = 0
    fields = ("menu_set", "is_active")
    autocomplete_fields = ("menu_set",)

    def get_formset(self, request, obj=None, **kwargs):
        fs = super().get_formset(request, obj, **kwargs)
        if obj is not None:
            fs.form.base_fields["menu_set"].queryset = MenuSet.objects.filter(restaurant=obj.restaurant)
        return fs


class BranchItemForm(forms.ModelForm):
    class Meta:
        model = BranchItem
        fields = ("item", "price", "is_available", "sort_order")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # запретим менять item у существующих строк
        if self.instance and self.instance.pk:
            self.fields["item"].disabled = True


class BranchItemInline(admin.TabularInline):
    model = BranchItem
    form = BranchItemForm
    extra = 1
    fields = ("item", "price", "is_available", "sort_order")
    autocomplete_fields = ("item",)

    def get_formset(self, request, obj=None, **kwargs):
        fs = super().get_formset(request, obj, **kwargs)
        if obj is not None:
            fs.form.base_fields["item"].queryset = Item.objects.filter(restaurant=obj.restaurant)
        return fs


@admin.action(description="Синхронизировать меню (создать категории/блюда/связи)")
def sync_menu_action(modeladmin, request, queryset):
    for branch in queryset:
        stats = sync_branch_menu(branch)
        modeladmin.message_user(
            request,
            f"{branch.name_ru}: MenuSet={stats['menu_sets']}, Категории+{stats['branch_categories']}, "
            f"Блюда+{stats['branch_items']}, Связи+{stats['links']}",
            level=messages.SUCCESS
        )


    # остальное как у тебя
@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurant", "name_ru", "is_active", "delivery_enabled", "min_order_amount", "delivery_fee")
    list_filter = ("restaurant", "is_active", "delivery_enabled")
    search_fields = ("name_ru", "name_ky", "name_en", "address", "phone")
    inlines = (BranchMenuSetInline, BranchTelegramLinkInline, BranchItemInline)
    actions = (sync_menu_action,)
  
    change_form_template = "admin/core/branch/change_form.html"

    def save_formset(self, request, form, formset, change):
        # Сохраняем inline как обычно
        super().save_formset(request, form, formset, change)

        # Если это inline BranchItem — делаем автосвязи категорий для новых блюд
        if formset.model is BranchItem:
            for obj in getattr(formset, "new_objects", []):
                ensure_links_for_branch_item(obj)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/sync-menu/",
                self.admin_site.admin_view(self.sync_menu_view),
                name="core_branch_sync_menu",
            ),
        ]
        return custom + urls

    def sync_menu_view(self, request, object_id):
        branch = self.get_object(request, object_id)
        stats = sync_branch_menu(branch)
        self.message_user(
            request,
            f"Готово: MenuSet={stats['menu_sets']}, Категории+{stats['branch_categories']}, "
            f"Блюда+{stats['branch_items']}, Связи+{stats['links']}",
            level=messages.SUCCESS,
        )
        return redirect(request.META.get("HTTP_REFERER", "../"))


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("id", "name_ru", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name_ru", "slug")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "restaurant", "branch", "role", "created_at")
    list_filter = ("role", "restaurant", "branch")
    search_fields = ("user__username", "restaurant__name_ru", "branch__name_ru")
