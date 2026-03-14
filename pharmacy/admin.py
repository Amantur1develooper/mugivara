from django.contrib import admin, messages
from django.urls import path
from django.shortcuts import get_object_or_404, redirect

from .models import Pharmacy, PharmacyBranch, DrugCategory, Drug, DrugInCategory, BranchDrug
from .services import sync_branch_catalog


class BranchDrugInline(admin.TabularInline):
    model = BranchDrug
    extra = 0
    autocomplete_fields = ("drug",)
    fields = ("drug", "price", "is_available", "sort_order")
    ordering = ("sort_order", "id")


@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display = ("id", "name_ru", "slug", "is_active", "created_at")
    search_fields = ("name_ru", "name_ky", "name_en", "slug")
    list_filter = ("is_active",)


@admin.register(Drug)
class DrugAdmin(admin.ModelAdmin):
    search_fields = ("name_ru", "name_ky", "name_en")
    list_filter = ("pharmacy", "is_active")
    autocomplete_fields = ("pharmacy",)


@admin.register(DrugCategory)
class DrugCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "pharmacy", "name_ru", "sort_order", "is_active")
    list_filter = ("pharmacy", "is_active")
    search_fields = ("name_ru", "name_ky", "name_en", "slug")
    ordering = ("pharmacy", "sort_order", "id")


@admin.register(DrugInCategory)
class DrugInCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "drug", "sort_order")
    list_filter = ("category__pharmacy", "category")
    search_fields = ("drug__name_ru", "category__name_ru")
    ordering = ("category", "sort_order", "id")


@admin.register(PharmacyBranch)
class PharmacyBranchAdmin(admin.ModelAdmin):
    list_display = ("id", "pharmacy", "name_ru", "is_active")
    list_filter = ("pharmacy", "is_active")
    search_fields = ("name_ru", "name_ky", "name_en", "address", "phone")
    inlines = (BranchDrugInline,)
    actions = ("sync_selected_branches",)

    @admin.action(description="Синхронизировать ассортимент (создать недостающие позиции)")
    def sync_selected_branches(self, request, queryset):
        total_created = 0
        for branch in queryset:
            res = sync_branch_catalog(branch, default_price=0, default_available=True, disable_removed=False)
            total_created += res.created
        self.message_user(request, f"Синхронизация завершена. Создано позиций: {total_created}", level=messages.SUCCESS)

    # ---- Кнопка на странице филиала (object-tools)
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("<int:branch_id>/sync/", self.admin_site.admin_view(self.sync_one_branch), name="pharmacybranch_sync"),
        ]
        return custom + urls

    def sync_one_branch(self, request, branch_id: int):
        branch = get_object_or_404(PharmacyBranch, id=branch_id)
        res = sync_branch_catalog(branch, default_price=0, default_available=True, disable_removed=False)
        self.message_user(
            request,
            f"Синхронизировано: создано {res.created}, уже было {res.existed}.",
            level=messages.SUCCESS,
        )
        return redirect(f"../")  # назад на change page