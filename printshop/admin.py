from django.contrib import admin

from .models import (
    PrintCenter, PrintBranch, PrintCategory, PrintProduct, PrintProductPhoto,
    PrintProductVariant, PrintOptionGroup, PrintOptionValue,
    PrintMembership, PrintPromoCode, PrintOrder, PrintOrderItem,
)


class PrintBranchInline(admin.StackedInline):
    model = PrintBranch
    extra = 0


@admin.register(PrintCenter)
class PrintCenterAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "slug", "is_active")
    search_fields = ("name_ru", "name_ky", "name_en", "slug")
    prepopulated_fields = {"slug": ("name_ru",)}
    inlines = (PrintBranchInline,)


@admin.register(PrintBranch)
class PrintBranchAdmin(admin.ModelAdmin):
    list_display = ("center", "name_ru", "phone", "is_active", "min_order_amount", "free_delivery_from")
    list_filter = ("center", "is_active")
    search_fields = ("name_ru", "address", "phone")


@admin.register(PrintCategory)
class PrintCategoryAdmin(admin.ModelAdmin):
    list_display = ("center", "name_ru", "sort_order", "is_active")
    list_filter = ("center", "is_active")
    ordering = ("center", "sort_order", "id")


class PrintProductPhotoInline(admin.TabularInline):
    model = PrintProductPhoto
    extra = 0
    max_num = 5


class PrintProductVariantInline(admin.TabularInline):
    model = PrintProductVariant
    extra = 0


class PrintOptionValueInline(admin.TabularInline):
    model = PrintOptionValue
    extra = 0


class PrintOptionGroupInline(admin.StackedInline):
    model = PrintOptionGroup
    extra = 0
    show_change_link = True


@admin.register(PrintProduct)
class PrintProductAdmin(admin.ModelAdmin):
    list_display = (
        "center", "name_ru", "category", "base_price",
        "is_available", "is_new", "is_popular", "is_promo", "sort_order",
    )
    list_filter = ("center", "category", "is_available", "is_new", "is_popular", "is_promo")
    search_fields = ("name_ru", "sku")
    inlines = (PrintProductPhotoInline, PrintProductVariantInline, PrintOptionGroupInline)


@admin.register(PrintOptionGroup)
class PrintOptionGroupAdmin(admin.ModelAdmin):
    list_display = ("product", "name", "is_required", "allow_multiple", "sort_order")
    list_filter = ("is_required", "allow_multiple")
    inlines = (PrintOptionValueInline,)


@admin.register(PrintMembership)
class PrintMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "center", "role")
    list_filter = ("role", "center")
    search_fields = ("user__username", "center__name_ru")


@admin.register(PrintPromoCode)
class PrintPromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "branch", "discount_type", "discount_value", "valid_until", "is_active", "used_count", "max_uses")
    list_filter = ("discount_type", "is_active", "branch__center")
    search_fields = ("code",)


class PrintOrderItemInline(admin.TabularInline):
    model = PrintOrderItem
    extra = 0
    readonly_fields = (
        "product", "product_name_snapshot", "qty", "unit_price",
        "line_total", "selection_snapshot", "comment",
    )


@admin.register(PrintOrder)
class PrintOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "branch", "status", "phone", "total", "created_at")
    list_filter = ("status", "branch__center", "branch")
    search_fields = ("phone", "name")
    inlines = (PrintOrderItemInline,)
