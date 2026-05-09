from django.contrib import admin
from .models import Ingredient, IngredientStock, TechCard, TechCardIngredient, TechCardStep, StockMovement


class TechCardIngredientInline(admin.TabularInline):
    model = TechCardIngredient
    fk_name = "tech_card"
    extra = 0


class TechCardStepInline(admin.TabularInline):
    model = TechCardStep
    extra = 0


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ["name_ru", "unit", "restaurant", "is_active"]
    list_filter  = ["restaurant", "unit", "is_active"]
    search_fields = ["name_ru"]


@admin.register(IngredientStock)
class IngredientStockAdmin(admin.ModelAdmin):
    list_display = ["ingredient", "branch", "qty", "cost_per_unit"]
    list_filter  = ["branch"]


@admin.register(TechCard)
class TechCardAdmin(admin.ModelAdmin):
    list_display = ["item", "branch", "yield_qty", "is_active"]
    list_filter  = ["branch", "is_active"]
    inlines = [TechCardIngredientInline, TechCardStepInline]


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ["ingredient", "branch", "qty", "move_type", "created_at"]
    list_filter  = ["branch", "move_type"]
    readonly_fields = ["created_at"]
