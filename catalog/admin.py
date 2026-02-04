from django.contrib import admin
from django import forms
from core.models import Branch
from catalog.models import BranchMenuSet
from .models import MenuSet, Category, Item, ItemCategory
from core.models import Restaurant
from django.contrib.admin.views.autocomplete import AutocompleteJsonView
from django.db.models import Prefetch
from core.models import Branch
from .models import BranchMenuSet


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
    list_display = ("id", "restaurant", "name", "is_active", "created_at")
    list_filter = ("restaurant", "is_active")
    search_fields = ("name", "restaurant__name_ru", "restaurant__slug")
    inlines = (CategoryInline,)



@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    search_fields = ("name_ru", "name_ky", "name_en")
    inlines = (ItemCategoryInline,) 
    
    def get_search_results(self, request, queryset, search_term):
        qs, use_distinct = super().get_search_results(request, queryset, search_term)

        branch_id = request.GET.get("branch_id")
        if not branch_id:
            return qs, use_distinct

        try:
            branch = Branch.objects.select_related("restaurant").get(pk=branch_id)
        except Branch.DoesNotExist:
            return qs, use_distinct

        # 1) только блюда ресторана этого филиала
        qs = qs.filter(restaurant=branch.restaurant)

        # 2) только блюда, которые входят в активные MenuSet филиала
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
            # если в филиале нет активных меню-сетов — можно показывать пусто (чтобы не ошибались)
            qs = qs.none()

        return qs, use_distinct
