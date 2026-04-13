from django.contrib import admin
from django.shortcuts import redirect, render
from django.urls import path
from django import forms
from django.db import transaction
from django.contrib import messages

from .models import Store, StoreBranch, StoreCategory, StoreProduct, StoreStock, StoreMembership


@admin.register(StoreMembership)
class StoreMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "store", "role")
    list_filter  = ("role", "store")
    search_fields = ("user__username", "store__name_ru")


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "slug", "is_active")
    search_fields = ("name_ru", "name_ky", "name_en", "slug")
    prepopulated_fields = {"slug": ("name_ru",)}


@admin.register(StoreBranch)
class StoreBranchAdmin(admin.ModelAdmin):
    list_display = ("store", "name_ru", "phone", "is_active")
    list_filter = ("store", "is_active")
    search_fields = ("name_ru", "address", "phone")
    change_form_template = "admin/shops/storebranch/change_form.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/duplicate/",
                self.admin_site.admin_view(self.duplicate_view),
                name="shops_storebranch_duplicate",
            ),
        ]
        return custom + urls

    def duplicate_view(self, request, object_id):
        original = self.get_object(request, object_id)
        if original is None:
            self.message_user(request, "Филиал не найден.", level=messages.ERROR)
            return redirect("..")

        if not request.user.is_superuser:
            self.message_user(request, "Только суперпользователи могут дублировать.", level=messages.ERROR)
            return redirect("..")

        stock_count = original.stocks.count()

        class DuplicateForm(forms.Form):
            name_ru  = forms.CharField(label="Название (рус)", max_length=200,
                                       initial=original.name_ru + " (копия)")
            name_ky  = forms.CharField(label="Название (кыргызча)", max_length=200,
                                       required=False, initial=original.name_ky)
            name_en  = forms.CharField(label="Название (eng)", max_length=200,
                                       required=False, initial=original.name_en)
            address  = forms.CharField(label="Адрес", max_length=255,
                                       required=False, initial=original.address)
            phone    = forms.CharField(label="Телефон", max_length=32,
                                       required=False, initial=original.phone)
            map_url  = forms.URLField(label="Ссылка на карту", required=False,
                                      initial=original.map_url)
            copy_stock = forms.BooleanField(
                label="Скопировать остатки (если не отмечено — qty будет 0)",
                required=False, initial=True,
            )

        if request.method == "POST":
            form = DuplicateForm(request.POST)
            if form.is_valid():
                d = form.cleaned_data
                with transaction.atomic():
                    new_branch = StoreBranch.objects.create(
                        store=original.store,
                        name_ru=d["name_ru"],
                        name_ky=d["name_ky"],
                        name_en=d["name_en"],
                        address=d["address"],
                        phone=d["phone"],
                        map_url=d["map_url"],
                        cover_photo=original.cover_photo,
                        delivery_enabled=original.delivery_enabled,
                        min_order_amount=original.min_order_amount,
                        delivery_fee=original.delivery_fee,
                        is_active=original.is_active,
                    )

                    copied = 0
                    for stock in original.stocks.select_related("product").all():
                        StoreStock.objects.create(
                            branch=new_branch,
                            product=stock.product,
                            qty=stock.qty if d["copy_stock"] else 0,
                        )
                        copied += 1

                self.message_user(
                    request,
                    f"Филиал «{new_branch.name_ru}» создан! Скопировано позиций: {copied}.",
                    level=messages.SUCCESS,
                )
                return redirect(f"../../{new_branch.id}/change/")
        else:
            form = DuplicateForm()

        context = {
            **self.admin_site.each_context(request),
            "title": f"Дублировать филиал: {original}",
            "original": original,
            "stock_count": stock_count,
            "form": form,
            "opts": self.model._meta,
        }
        return render(request, "admin/shops/storebranch/duplicate.html", context)


@admin.register(StoreCategory)
class StoreCategoryAdmin(admin.ModelAdmin):
    list_display = ("store", "name_ru", "sort_order", "is_active")
    list_filter = ("store", "is_active")
    ordering = ("store", "sort_order", "id")


@admin.register(StoreProduct)
class StoreProductAdmin(admin.ModelAdmin):
    list_display = ("store", "name_ru", "category", "unit", "price", "is_active")
    list_filter = ("store", "category", "unit", "is_active")
    search_fields = ("name_ru", "name_ky", "name_en")


@admin.register(StoreStock)
class StoreStockAdmin(admin.ModelAdmin):
    list_display = ("branch", "product", "qty")
    list_filter = ("branch", "branch__store")
    search_fields = ("product__name_ru", "branch__name_ru")
