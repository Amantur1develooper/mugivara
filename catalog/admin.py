from django.contrib import admin
from django import forms

from .models import MenuSet, Category, Item, ItemCategory
from core.models import Restaurant



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
    extra = 0
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
    list_display = ("id", "restaurant", "name", "is_active", "created_at")
    list_filter = ("restaurant", "is_active")
    search_fields = ("name", "restaurant__name_ru", "restaurant__slug")
    inlines = (CategoryInline,)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurant", "name_ru", "base_price", "created_at")
    list_filter = ("restaurant",)
    search_fields = ("name_ru", "name_ky", "name_en", "restaurant__name_ru", "restaurant__slug")
    inlines = (ItemCategoryInline,)
    autocomplete_fields = ("restaurant",)
