from django.contrib import admin
from django import forms
from django.contrib.admin.views.autocomplete import AutocompleteJsonView
from core.models import Branch, Restaurant
from catalog.models import BranchMenuSet
from .models import (
    MenuSet, Category, Item, ItemCategory, BranchItem,
    DishConstructor, ConstructorGroup, ConstructorIngredient,
)


class ItemAutocompleteJsonView(AutocompleteJsonView):
    def serialize_result(self, obj, to_field_name):
        return {
            "id": str(getattr(obj, to_field_name)),
            "text": self.model_admin.autocomplete_label(obj),
        }


# ---------- Inlines

class CategoryInline(admin.TabularInline):
    model = Category
    extra = 0
    fields = ("name_ru", "name_ky", "name_en")
    show_change_link = True


class ItemCategoryInlineForm(forms.ModelForm):
    class Meta:
        model = ItemCategory
        fields = ("category", "sort_order")


class ItemCategoryInline(admin.TabularInline):
    model = ItemCategory
    form = ItemCategoryInlineForm
    extra = 1
    fields = ("category", "sort_order")

    def get_formset(self, request, obj=None, **kwargs):
        fs = super().get_formset(request, obj, **kwargs)
        if obj is not None:
            fs.form.base_fields["category"].queryset = Category.objects.filter(
                menu_set__restaurant=obj.restaurant
            ).select_related("menu_set")
        return fs


# ---------- Admin

@admin.register(MenuSet)
class MenuSetAdmin(admin.ModelAdmin):
    list_display        = ("id", "restaurant", "name", "is_active", "created_at")
    list_filter         = ("restaurant", "is_active")
    list_select_related = ("restaurant",)
    list_per_page       = 30
    search_fields       = ("name", "restaurant__name_ru", "restaurant__slug")
    inlines             = (CategoryInline,)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display        = ("id", "name_ru", "restaurant", "rating", "order_count", "base_price")
    list_filter         = ("restaurant",)
    list_select_related = ("restaurant",)
    list_per_page       = 50
    ordering            = ("-rating", "-order_count")
    search_fields       = ("name_ru", "name_ky", "name_en")
    readonly_fields     = ("order_count", "rating")
    inlines             = (ItemCategoryInline,)

    def get_search_results(self, request, queryset, search_term):
        qs, use_distinct = super().get_search_results(request, queryset, search_term)

        branch_id = request.GET.get("branch_id")
        if not branch_id:
            return qs, use_distinct

        try:
            branch = Branch.objects.select_related("restaurant").get(pk=branch_id)
        except Branch.DoesNotExist:
            return qs, use_distinct

        qs = qs.filter(restaurant=branch.restaurant)

        menu_set_ids = list(
            BranchMenuSet.objects.filter(branch=branch, is_active=True, menu_set__is_active=True)
            .values_list("menu_set_id", flat=True)
        )

        if menu_set_ids:
            qs = qs.filter(
                item_categories__category__menu_set_id__in=menu_set_ids
            ).distinct()
            use_distinct = True
        else:
            qs = qs.none()

        return qs, use_distinct


@admin.register(BranchItem)
class BranchItemAdmin(admin.ModelAdmin):
    list_display        = ("id", "branch", "item", "price", "is_available", "sort_order")
    list_filter         = ("branch__restaurant", "branch", "is_available")
    list_select_related = ("branch", "branch__restaurant", "item")
    list_editable       = ("price", "is_available")
    list_per_page       = 50
    search_fields       = ("item__name_ru", "item__name_ky", "branch__name_ru")
    ordering            = ("branch", "sort_order", "item__name_ru")


# ── КОНСТРУКТОР БЛЮД ──────────────────────────────────────────────────────────

class ConstructorIngredientInline(admin.TabularInline):
    model               = ConstructorIngredient
    extra               = 1
    fields              = ("branch_item", "name", "description", "price", "photo",
                           "warehouse_ingredient", "write_off_qty", "is_active", "sort_order")
    autocomplete_fields = ("branch_item", "warehouse_ingredient")


class ConstructorGroupInline(admin.TabularInline):
    model  = ConstructorGroup
    extra  = 1
    fields = ("name", "min_select", "max_select", "sort_order")
    show_change_link = True


@admin.register(DishConstructor)
class DishConstructorAdmin(admin.ModelAdmin):
    list_display        = ("id", "branch", "name", "base_price", "is_active", "sort_order")
    list_filter         = ("branch__restaurant", "is_active")
    list_select_related = ("branch", "branch__restaurant")
    list_per_page       = 30
    search_fields       = ("name", "branch__name_ru")
    ordering            = ("branch", "sort_order", "id")
    inlines             = (ConstructorGroupInline,)


@admin.register(ConstructorGroup)
class ConstructorGroupAdmin(admin.ModelAdmin):
    list_display        = ("id", "constructor", "name", "min_select", "max_select", "sort_order")
    list_filter         = ("constructor__branch__restaurant",)
    list_select_related = ("constructor", "constructor__branch")
    list_per_page       = 50
    search_fields       = ("name", "constructor__name")
    inlines             = (ConstructorIngredientInline,)
