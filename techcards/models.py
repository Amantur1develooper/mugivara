from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()


class Ingredient(models.Model):
    UNIT_KG   = "kg"
    UNIT_GR   = "gr"
    UNIT_L    = "l"
    UNIT_ML   = "ml"
    UNIT_PCS  = "pcs"
    UNIT_PKG  = "pkg"
    UNIT_TBSP = "tbsp"
    UNIT_TSP  = "tsp"
    UNIT_CHOICES = [
        (UNIT_KG,   "кг"),
        (UNIT_GR,   "г"),
        (UNIT_L,    "л"),
        (UNIT_ML,   "мл"),
        (UNIT_PCS,  "шт"),
        (UNIT_PKG,  "уп"),
        (UNIT_TBSP, "ст.л."),
        (UNIT_TSP,  "ч.л."),
    ]

    restaurant = models.ForeignKey(
        "core.Restaurant", on_delete=models.CASCADE, related_name="ingredients"
    )
    name_ru    = models.CharField("Название", max_length=200)
    unit       = models.CharField("Ед. изм.", max_length=10, choices=UNIT_CHOICES, default=UNIT_GR)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name_ru"]
        verbose_name = "Ингредиент"
        verbose_name_plural = "Ингредиенты"

    def __str__(self):
        return f"{self.name_ru} ({self.get_unit_display()})"

    def stock_for(self, branch):
        return self.stocks.filter(branch=branch).first()


class IngredientStock(models.Model):
    branch       = models.ForeignKey("core.Branch", on_delete=models.CASCADE, related_name="ingredient_stocks")
    ingredient   = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name="stocks")
    qty          = models.DecimalField("Остаток", max_digits=12, decimal_places=3, default=Decimal("0"))
    cost_per_unit = models.DecimalField("Цена за ед.", max_digits=10, decimal_places=2, default=Decimal("0"))
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("branch", "ingredient")
        verbose_name = "Остаток ингредиента"
        verbose_name_plural = "Остатки ингредиентов"

    def __str__(self):
        return f"{self.ingredient.name_ru} @ {self.branch.name_ru}: {self.qty} {self.ingredient.get_unit_display()}"

    @property
    def total_value(self):
        return self.qty * self.cost_per_unit


class TechCard(models.Model):
    item   = models.ForeignKey("catalog.Item",   on_delete=models.CASCADE, related_name="tech_cards")
    branch = models.ForeignKey("core.Branch",    on_delete=models.CASCADE, related_name="tech_cards")
    yield_qty     = models.DecimalField("Выход (кол-во порций)", max_digits=8, decimal_places=2, default=Decimal("1"))
    cooking_time  = models.PositiveSmallIntegerField("Время приготовления (мин)", default=0)
    notes         = models.TextField("Примечания/описание", blank=True)
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("item", "branch")
        verbose_name = "Технологическая карта"
        verbose_name_plural = "Технологические карты"

    def __str__(self):
        return f"Техкарта: {self.item.name_ru} @ {self.branch.name_ru}"

    @property
    def cost_price(self):
        """Total cost for yield_qty portions."""
        total = Decimal("0")
        for line in self.ingredients.select_related("ingredient").all():
            total += line.line_cost
        return total

    @property
    def cost_per_serving(self):
        if self.yield_qty and self.yield_qty > 0:
            return self.cost_price / self.yield_qty
        return Decimal("0")

    def selling_price(self, branch=None):
        b = branch or self.branch
        bi = self.item.branch_items.filter(branch=b).first()
        return bi.price if bi else Decimal("0")

    def margin(self, branch=None):
        price = self.selling_price(branch)
        cost  = self.cost_per_serving
        if price > 0:
            return ((price - cost) / price * 100).quantize(Decimal("0.1"))
        return Decimal("0")

    def markup(self, branch=None):
        price = self.selling_price(branch)
        cost  = self.cost_per_serving
        if cost > 0:
            return ((price - cost) / cost * 100).quantize(Decimal("0.1"))
        return Decimal("0")


class TechCardIngredient(models.Model):
    tech_card    = models.ForeignKey(TechCard, on_delete=models.CASCADE, related_name="ingredients")
    ingredient   = models.ForeignKey(Ingredient, on_delete=models.SET_NULL, null=True, blank=True, related_name="tc_lines")
    semi_finished = models.ForeignKey(TechCard, on_delete=models.SET_NULL, null=True, blank=True, related_name="used_as_semi")
    gross_qty    = models.DecimalField("Брутто (кол-во)", max_digits=10, decimal_places=3, default=Decimal("0"))
    waste_pct    = models.DecimalField("Отходы/потери %", max_digits=5, decimal_places=2, default=Decimal("0"))
    unit         = models.CharField("Ед. изм.", max_length=10, choices=Ingredient.UNIT_CHOICES, default="gr")
    sort_order   = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Ингредиент техкарты"
        verbose_name_plural = "Ингредиенты техкарты"

    @property
    def net_qty(self):
        """Quantity after waste/loss."""
        factor = Decimal("1") - self.waste_pct / Decimal("100")
        return (self.gross_qty * factor).quantize(Decimal("0.001"))

    @property
    def cost_per_unit(self):
        if self.ingredient:
            stock = self.ingredient.stocks.filter(branch=self.tech_card.branch).first()
            return stock.cost_per_unit if stock else Decimal("0")
        if self.semi_finished:
            return self.semi_finished.cost_per_serving
        return Decimal("0")

    @property
    def line_cost(self):
        return (self.net_qty * self.cost_per_unit).quantize(Decimal("0.01"))

    def display_name(self):
        if self.ingredient:
            return self.ingredient.name_ru
        if self.semi_finished:
            return f"п/ф: {self.semi_finished.item.name_ru}"
        return "—"


class TechCardStep(models.Model):
    tech_card   = models.ForeignKey(TechCard, on_delete=models.CASCADE, related_name="steps")
    step_number = models.PositiveSmallIntegerField(default=1)
    description = models.TextField("Описание шага")

    class Meta:
        ordering = ["step_number"]
        verbose_name = "Шаг приготовления"
        verbose_name_plural = "Шаги приготовления"


class TechCardVersion(models.Model):
    tech_card      = models.ForeignKey(TechCard, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField(default=1)
    snapshot       = models.JSONField("Снимок карты")
    changed_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Версия техкарты"
        verbose_name_plural = "Версии техкарты"


class StockMovement(models.Model):
    TYPE_PURCHASE   = "purchase"
    TYPE_SALE       = "sale"
    TYPE_WRITEOFF   = "writeoff"
    TYPE_MANUAL_ADD = "manual_add"
    TYPE_MANUAL_SUB = "manual_sub"
    TYPE_RETURN     = "return"
    TYPE_CHOICES = [
        (TYPE_PURCHASE,   "Закупка"),
        (TYPE_SALE,       "Продажа"),
        (TYPE_WRITEOFF,   "Списание"),
        (TYPE_MANUAL_ADD, "Инвентаризация (+)"),
        (TYPE_MANUAL_SUB, "Инвентаризация (−)"),
        (TYPE_RETURN,     "Возврат"),
    ]

    branch       = models.ForeignKey("core.Branch", on_delete=models.CASCADE, related_name="stock_movements")
    ingredient   = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name="movements")
    qty          = models.DecimalField("Количество", max_digits=12, decimal_places=3)
    move_type    = models.CharField("Тип", max_length=20, choices=TYPE_CHOICES)
    cost_per_unit = models.DecimalField("Цена за ед.", max_digits=10, decimal_places=2, null=True, blank=True)
    order        = models.ForeignKey("orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_movements")
    note         = models.TextField("Примечание", blank=True)
    created_by   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Движение склада"
        verbose_name_plural = "Движения склада"

    @property
    def total_cost(self):
        if self.cost_per_unit:
            return (abs(self.qty) * self.cost_per_unit).quantize(Decimal("0.01"))
        return None
