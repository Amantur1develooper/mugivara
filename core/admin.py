from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django import forms
from django.contrib.admin.widgets import AutocompleteSelect
from .models import Restaurant, Branch, Membership
from catalog.models import MenuSet, Item, BranchMenuSet, BranchItem
from catalog.services import sync_branch_menu, ensure_links_for_branch_item
from integrations.admin import BranchTelegramLinkInline
from django.contrib.admin.widgets import AutocompleteSelect
from catalog.models import BranchItem as CatalogBranchItem

from django.contrib.admin.widgets import AutocompleteSelect
from catalog.models import BranchItem as CatalogBranchItem

class BranchItemItemSelect(AutocompleteSelect):
    def __init__(self, field, admin_site, branch_id, attrs=None):
        self.branch_id = str(branch_id)
        super().__init__(field, admin_site, attrs)

    def url_parameters(self):
        params = super().url_parameters()
        params["branch_id"] = self.branch_id
        return params




class BranchMenuSetInline(admin.TabularInline):
    model = BranchMenuSet
    extra = 0
    fields = ("menu_set", "is_active")
    autocomplete_fields = ("menu_set",)

  


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

    fields = ("item", "menusets", "price", "is_available", "sort_order")
    readonly_fields = ("menusets",)
    autocomplete_fields = ("item",)

    @admin.display(description="Меню-сеты")
    def menusets(self, obj):
        if not obj.pk or not obj.item_id:
            return "—"
        sets = []
        seen = set()
        for ic in obj.item.item_categories.all():
            ms = ic.category.menu_set.name
            if ms not in seen:
                seen.add(ms)
                sets.append(ms)
        if not sets:
            return "—"
        s = ", ".join(sets[:2])
        return s + ("…" if len(sets) > 2 else "")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("item").prefetch_related(
            "item__item_categories__category__menu_set"
        )

    def get_formset(self, request, obj=None, **kwargs):
        fs = super().get_formset(request, obj, **kwargs)
        if obj is not None:
            # queryset “на всякий случай”, если отключишь autocomplete
            fs.form.base_fields["item"].queryset = Item.objects.filter(restaurant=obj.restaurant)

            # ВАЖНО: передаём ПОЛЕ BranchItem.item (а не remote_field!)
            db_field = CatalogBranchItem._meta.get_field("item")
            fs.form.base_fields["item"].widget = BranchItemItemSelect(db_field, self.admin_site, obj.pk)

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
    list_display = ("id", "name_ru", "slug", "is_active")
    search_fields = ("name_ru", "slug")
    list_filter = ("is_active",)

    fieldsets = (
        (None, {"fields": ("name_ru","name_ky","name_en","slug","logo","is_active")}),
        ("О нас", {"fields": ("about_ru","about_ky","about_en")}),
    )



@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "restaurant", "branch", "role", "created_at")
    list_filter = ("role", "restaurant", "branch")
    search_fields = ("user__username", "restaurant__name_ru", "branch__name_ru")
